from tornado.httpclient import AsyncHTTPClient, HTTPRequest
from tornado import web
from urllib import parse
from typing import List, Union, Any, Dict, Awaitable, Tuple, NamedTuple, Optional, NewType
from dataclasses import dataclass
import asyncio
import json
import secrets
import time

class Error(BaseException):
    pass

@dataclass
class OAuthClientInfo:
    client_id: str
    client_secret: str
    redirect_url: str

@dataclass
class OAuthProviderInfo:
    authz_endpoint: str
    token_endpoint: str
    jwks_url: str


OAuthToken = NewType("OAuthToken", str)
Timestamp = NewType("Timestamp", int)


class AccessToken:
    _token: OAuthToken
    _expires: Optional[Timestamp]

    def __init__(self, token: OAuthToken, expires: Optional[Timestamp] = None):
        self._token = token
        self._expires = expires

    def Get(self, current_time: Timestamp) -> Optional[OAuthToken]:
        if self._expires is not None and self._expires < current_time:
            return None
        return self._token

class RefreshResult(NamedTuple):
    access_token: OAuthToken
    refresh_token: Optional[OAuthToken]
    expires_in: Optional[int]

class RefreshableToken:
    _access_token: AccessToken
    _refresh_token: OAuthToken

    def __init__(self, access_token: AccessToken, refresh_token: OAuthToken):
        self._access_token = access_token
        self._refresh_token = refresh_token

    def TryGet(self, current_time: Timestamp) -> Optional[OAuthToken]:
        return self._access_token.Get(current_time)

    async def Refresh(self, current_time: Timestamp, provider: "OAuthProvider") -> None:
        result = await provider.GetTokenFromRefresh(self._refresh_token)
        expires = None
        if result.expires_in is not None:
            expires = Timestamp(result.expires_in + current_time)
        self._access_token = AccessToken(
            token = result.access_token,
            expires = expires
        )
        if result.refresh_token is not None:
            self._refresh_token = result.refresh_token


    async def Get(self, current_time: Timestamp, provider: "OAuthProvider") -> OAuthToken:
        token = self._access_token.Get(current_time)
        if token is None:
            await self.Refresh(current_time, provider)
            token = self._access_token.Get(current_time)
            assert token is not None
        return token

class OAuthProvider:
    http_client: AsyncHTTPClient
    client: OAuthClientInfo
    provider: OAuthProviderInfo

    def __init__(self, client: OAuthClientInfo, provider: OAuthProviderInfo, http_client: Optional[AsyncHTTPClient] = None):
        if http_client is None:
            http_client = AsyncHTTPClient()
        self.client = client
        self.provider = provider

    def auth_url(self, *, state_token: str, scopes: List[str], nonce: Union[str, None] = None) -> str:
        params: Dict[str, str] = {
            'client_id': self.client.client_id,
            'redirect_uri': self.client.redirect_url,
            'response_type': 'code',
            'scope': ' '.join(scopes),
            'state': state_token,
        }

        if nonce is not None:
            params['nonce'] = nonce

        query_str = parse.urlencode(params)

        return "%s?%s" % (self.provider.authz_endpoint, query_str)

    async def exchange_code(self, current_time: Timestamp, code: str) -> RefreshableToken:
        params = parse.urlencode({
            'client_id': self.client.client_id,
            'client_secret': self.client.client_secret,
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': self.client.redirect_url,
        })

        exchange_url = "%s?%s" %(self.provider.token_endpoint, params)
        request = HTTPRequest(url = exchange_url, method = 'POST', body = "")
        response = await self.http_client.fetch(request)
        if response.headers['Content-Type'] != 'application/json':
            print(response.headers['Content-Type'])
            raise Error()

        contents = json.loads(response.body.decode('utf-8'))

        expires = None
        if 'expires_in' in contents:
            expires = contents['expires_in'] + current_time

        access_token = AccessToken(
            token = contents['access_token'],
            expires = expires,
        )

        return RefreshableToken(
            access_token = access_token,
            refresh_token = contents['refresh_token']
        )

    async def GetTokenFromRefresh(self, refresh_token: str) -> RefreshResult:
        params = parse.urlencode(dict(
            client_id = self.client.client_id,
            client_secret = self.client.client_secret,
            grant_type = 'refresh_token',
            refresh_token = refresh_token,
        ))

        exchange_url = "%s?%s" % (self.provider.token_endpoint, params)
        request = HTTPRequest(url = exchange_url, method = 'POST', body = "")
        response = await self.http_client.fetch(request)

        contents = json.loads(response.body.decode('utf-8'))

        return RefreshResult(
            access_token = contents['access_token'],
            refresh_token = contents.get('refresh_token', None),
            expires_in = contents.get('expires_in', None),
        )


TWITCH_PROVIDER = OAuthProviderInfo(
    authz_endpoint = 'https://id.twitch.tv/oauth2/authorize',
    token_endpoint = 'https://id.twitch.tv/oauth2/token',
    jwks_url = 'https://id.twitch.tv/oauth2/keys',
)

class OAuthCallbackManager:
    _lock: asyncio.Lock
    _callbacks: Dict[str, asyncio.Event]
    _result: Dict[str, Any]
    _provider: OAuthProvider

    def __init__(self, provider: OAuthProvider):
        self._lock = asyncio.Lock()
        self._callbacks = {}
        self._result = {}
        self._provider = provider

    async def start_auth(self) -> Tuple[str, Awaitable[Any]]:
        token = secrets.token_urlsafe(30)
        auth_url = self._provider.auth_url(
            state_token = token,
            scopes = ['openid', 'user:edit'])

        event = asyncio.Event()

        async with self._lock:
            self._callbacks[token] = event

        async def Inner() -> Any:
            await event.wait()
            async with self._lock:
                result = self._result[token]
                del self._callbacks[token]
                del self._result[token]
                return result

        return (auth_url, Inner())

    async def complete(self, state: str, code: str) -> None:
        async with self._lock:
            result = await self._provider.exchange_code(Timestamp(int(time.time())), code)
            event = self._callbacks[state]
            self._result[state] = result
            event.set()


class AccountCreationManager:
    _lock: asyncio.Lock = asyncio.Lock()
    _pending_creates: Dict[str, Awaitable[Any]] = {}

    async def add_creation(self, token: str, callback: Awaitable[Any]) -> None:
        async with self._lock:
            self._pending_creates[token] = callback

    async def wait_result(self, token: str) -> Any:
        async with self._lock:
            callback = self._pending_creates[token]
            del self._pending_creates[token]
        return await callback

