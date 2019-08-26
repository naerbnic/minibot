from __future__ import annotations

from tornado.httpclient import AsyncHTTPClient, HTTPRequest
from tornado import web
from urllib import parse
from typing import (
    List, Union, Any, Dict, Awaitable, Tuple, NamedTuple, Optional, NewType,
    TypeVar, Type, Generic
)
from dataclasses import dataclass
import asyncio
import json
import secrets

import time
from serde import Model, fields
from abc import ABC, abstractmethod, abstractclassmethod
import attr

class Error(BaseException):
    pass

class AuthToken:
    _type: str
    _token: str

    @staticmethod
    def Bearer(token: str) -> AuthToken:
        return AuthToken("Bearer", token)

    def __init__(self, type: str, token: str):
        self._type = type
        self._token = token

    def HeaderValue(self) -> str:
        return f"{self._type} {self._token}"

T = TypeVar("T")
MT = TypeVar("MT", bound=Model)
MS = TypeVar("MS", bound=Model)

@attr.s(auto_attribs=True)
class RequestBody:
    content_type: str
    content: bytes

def SerdeJsonRequest(data: MT) -> RequestBody:
    content = data.to_json().encode()
    return RequestBody(content_type='application/json', content=content)

class ResponseParser(Generic[T]):
    def ExpectedType(self) -> Optional[str]:
        return None

    @abstractmethod
    def ParseResponseBody(self, content_type: Optional[str], body: bytes) -> T:
        pass

class SerdeJsonResponseParser(ResponseParser[MS]):
    _body_type: Type[MS]

    def __init__(self, body_type: Type[MS]):
        self._body_type = body_type

    def ExpectedType(self) -> Optional[str]:
        return 'application/json'

    def ParseResponseBody(self, content_type: Optional[str], body: bytes) -> MS:
        if content_type is None or content_type != 'application/json':
            raise ValueError()
        return self._body_type.from_json(body.decode())


class BaseSimpleHttpClient(ABC):
    pass

class SimpleHttpClient(BaseSimpleHttpClient):
    _base_url: str
    _http_client: AsyncHTTPClient

    def __init__(self, base_url: str):
        self._base_url = base_url
        self._http_client = AsyncHTTPClient()

    async def Request(self,
            path: str,
            *,
            method: str = "GET",
            auth: Optional[AuthToken] = None,
            query: Optional[Dict[str, str]] = None,
            body: Optional[RequestBody] = None,
            resp_parser: Optional[ResponseParser[T]] = None) -> Optional[T]:
        full_url = parse.urljoin(self._base_url, path)
        if query is not None:
            full_url = f"{full_url}?{parse.urlencode(query)}"
        headers = {}
        if auth is not None:
            headers['Authentication'] = auth.HeaderValue()
        if body is not None:
            headers['Content-Type'] = body.content_type
        if resp_parser is not None:
            expected_type = resp_parser.ExpectedType()
            if expected_type is not None:
                headers['Accept'] = expected_type

        req_args: Dict[str, Any] = {}

        if body is not None:
            req_args['body'] = body.content

        req = HTTPRequest(full_url, method=method, headers=headers, **req_args)
        resp = await self._http_client.fetch(req, raise_error=True)

        if resp_parser is not None:
            # Reqire Content-Type headers
            content_type = resp.headers.get('Content-Type', None)
            return resp_parser.ParseResponseBody(content_type, resp.body)
        else:
            return None


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

class CodeExchangeResponse(Model):
    access_token: str = fields.Str()
    refresh_token: str = fields.Str()
    expires_in: int = fields.Int()
    scopes: List[str] = fields.List(fields.Str())

class TokenRefreshResponse(Model):
    access_token: str = fields.Str()
    refresh_token: str = fields.Str()
    expires_in: int = fields.Int()

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

class OAuthProvider(ABC):
    @abstractmethod
    def AuthUrl(self, *, state_token: str, scopes: List[str], nonce: Optional[str] = None) -> str:
        pass

    @abstractmethod
    def ExchangeCode(self, current_time: Timestamp, code: str) -> Awaitable[RefreshableToken]:
        pass

    @abstractmethod
    async def GetTokenFromRefresh(self, refresh_token: str) -> RefreshResult:
        pass

class OAuthProviderImpl(OAuthProvider):
    http_client: SimpleHttpClient
    client: OAuthClientInfo
    provider: OAuthProviderInfo

    def __init__(self, client: OAuthClientInfo, provider: OAuthProviderInfo):
        self.http_client = SimpleHttpClient(provider.token_endpoint)
        self.client = client
        self.provider = provider

    def AuthUrl(self, *, state_token: str, scopes: List[str], nonce: Union[str, None] = None) -> str:
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

    async def ExchangeCode(self, current_time: Timestamp, code: str) -> RefreshableToken:
        params: Dict[str, str] = {
            'client_id': self.client.client_id,
            'client_secret': self.client.client_secret,
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': self.client.redirect_url,
        }

        contents = await self.http_client.Request('',
            query = params,
            resp_parser = SerdeJsonResponseParser(CodeExchangeResponse))

        assert contents is not None

        expires: Optional[Timestamp] = None
        if contents.expires_in is not None:
            expires = Timestamp(contents.expires_in + current_time)

        access_token = AccessToken(
            token = OAuthToken(contents.access_token),
            expires = expires,
        )

        return RefreshableToken(
            access_token = access_token,
            refresh_token = OAuthToken(contents.refresh_token)
        )

    async def GetTokenFromRefresh(self, refresh_token: str) -> RefreshResult:
        params: Dict[str, str] = dict(
            client_id = self.client.client_id,
            client_secret = self.client.client_secret,
            grant_type = 'refresh_token',
            refresh_token = refresh_token,
        )

        contents = await self.http_client.Request('',
            method='POST', query=params, resp_parser=SerdeJsonResponseParser(TokenRefreshResponse))

        assert contents is not None

        return RefreshResult(
            access_token = OAuthToken(contents.access_token),
            refresh_token = OAuthToken(contents.refresh_token),
            expires_in = contents.expires_in,
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
        auth_url = self._provider.AuthUrl(
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
            result = await self._provider.ExchangeCode(Timestamp(int(time.time())), code)
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

