from tornado import httpclient
from tornado import web
from urllib import parse
from typing import List, Union, Any, Dict, Awaitable, Tuple
import asyncio
import json
import secrets

class Error(BaseException):
    pass

class OAuthClientInfo:
    client_id: str
    client_secret: str
    redirect_uri: str

    def __init__(self, client_id: str, client_secret: str, redirect_url: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_url = redirect_url

class OAuthProviderInfo:
    authz_endpoint: str
    token_endpoint: str
    jwks_url: str

    def __init__(self, authz_endpoint: str, token_endpoint: str, jwks_url: str):
        self.authz_endpoint = authz_endpoint
        self.token_endpoint = token_endpoint
        self.jwks_url = jwks_url

class OAuthProvider:
    client: OAuthClientInfo
    provider: OAuthProviderInfo

    def __init__(self, client: OAuthClientInfo, provider: OAuthProviderInfo):
        self.client = client
        self.provider = provider

    def auth_url(self, *, state_token: str, scopes: List[str], nonce: Union[str, None] = None) -> str:
        params = {
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

    async def exchange_code(self, client: httpclient.AsyncHTTPClient, code: str) -> Any:
        params = parse.urlencode({
            'client_id': self.client.client_id,
            'client_secret': self.client.client_secret,
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_url': self.client.redirect_uri,
        })

        exchange_url = "%s?%s" %(self.provider.token_endpoint, params)
        request = httpclient.HTTPRequest(url = exchange_url, method = 'POST')
        response = await client.fetch(request)
        if response.headers['Content-Type'] != 'application/json; charset=utf8':
            raise Error()

        return json.loads(response.body.decode('utf-8'))

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
    _client: httpclient.AsyncHTTPClient

    def __init__(self, provider: OAuthProvider):
        self._lock = asyncio.Lock()
        self._callbacks = {}
        self._result = {}
        self._provider = provider
        self._client = httpclient.AsyncHTTPClient()

    async def start_auth(self) -> Tuple[str, Awaitable[Any]]:
        token = secrets.token_urlsafe(30)
        auth_url = self._provider.auth_url(
            state_token = token,
            scopes = ['oidc'])

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

    async def complete(self, state, code) -> None:
        async with self._lock:
            result = await self._provider.exchange_code(self._client, code)
            event = self._callbacks[state]
            self._result[state] = result
            event.set()


class AccountCreationManager:
    _lock: asyncio.Lock = asyncio.Lock()
    _pending_creates: Dict[str, Awaitable[Any]] = {}

    def __init__(self):
        pass

    async def add_creation(self, token: str, callback: Awaitable[Any]) -> None:
        async with self._lock:
            self._pending_creates[token] = callback

    async def wait_result(self, token: str) -> Any:
        async with self._lock:
            callback = self._pending_creates[token]
            del self._pending_creates[token]
        return await callback

