from typing import Dict, List, Optional, Awaitable, Set
import attr
import secrets
import urllib
from tornado.httpclient import (AsyncHTTPClient, HTTPRequest)

from ..oauth import (Timestamp, OAuthToken, AccessToken, OAuthProvider, RefreshableToken, RefreshResult)

@attr.s(auto_attribs=True)
class _AuthInfo:
    state: str
    nonce: Optional[str]
    scopes: List[str]

class FakeOAuthProvider(OAuthProvider):
    _client: AsyncHTTPClient
    _pending_auths: Dict[str, _AuthInfo]
    _pending_codes: Dict[str, _AuthInfo]
    _valid_refresh_tokens: Set[str]

    def __init__(self) -> None:
        self._client = AsyncHTTPClient()
        self._pending_auths = {}
        self._pending_codes = {}
        self._valid_refresh_tokens = set()

    async def AcceptAuth(self, redirect_url: str, auth_url: str) -> None:
        parts = urllib.parse.urlsplit(auth_url)
        assert parts.scheme == 'http'
        assert parts.netloc == 'nonexistent.server'
        assert parts.path == '/token/endpoint'
        query = urllib.parse.parse_qs(parts.query)
        (token,) = query['token']
        auth_info = self._pending_auths.pop(token)

        # Make a callback with the OAuth parts expected
        code = secrets.token_urlsafe(10)
        self._pending_codes[code] = auth_info
        callback_args = {
            'code': code,
            'state': auth_info.state
        }
        callback_url = f"{redirect_url}?{urllib.parse.urlencode(callback_args)}"
        req = HTTPRequest(callback_url)
        await self._client.fetch(req)

    # Overrides
    def AuthUrl(self, *, state_token: str, scopes: List[str], nonce: Optional[str] = None) -> str:
        token = secrets.token_urlsafe(10)
        self._pending_auths[token] = _AuthInfo(state = state_token, nonce = nonce, scopes = scopes)
        return urllib.parse.urlunsplit((
            'http',
            'nonexistent.server',
            '/token/endpoint',
            f'token={token}',
            '',
        ))

    async def ExchangeCode(self, current_time: Timestamp, code: str) -> RefreshableToken:
        self._pending_codes.pop(code)
        access_token = AccessToken(OAuthToken(secrets.token_urlsafe(10)))
        refresh_token = OAuthToken(secrets.token_urlsafe(10))
        self._valid_refresh_tokens.add(refresh_token)
        return RefreshableToken(access_token, refresh_token)

    async def GetTokenFromRefresh(self, refresh_token: str) -> RefreshResult:
        self._valid_refresh_tokens.remove(refresh_token)
        refresh_token = OAuthToken(secrets.token_urlsafe(10))
        self._valid_refresh_tokens.add(refresh_token)
        return RefreshResult(
            access_token = OAuthToken(secrets.token_urlsafe(10)),
            refresh_token = None,
            expires_in = None,
        )

