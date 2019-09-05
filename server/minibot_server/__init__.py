from .oauth import (AccountCreationManager, OAuthCallbackManager, OAuthClientInfo, TWITCH_PROVIDER, OAuthProvider, OAuthProviderImpl)

from tornado import web, ioloop, httpclient, escape
import asyncio

from .config import (ReadConfig, MinibotConfig)
from . import app

from typing import Awaitable

def MakeRealOAuthProvider(config: MinibotConfig) -> OAuthProvider:
    config = ReadConfig()
    client_info = OAuthClientInfo(
        client_id = config.config_doc.twitch_client_id,
        client_secret = config.secret_doc.twitch_client_secret,
        redirect_url = config.config_doc.twitch_redirect_url,
    )
    return OAuthProviderImpl(client_info, TWITCH_PROVIDER)

async def TestAccountCreateExchange() -> None:
    config = ReadConfig()
    provider = MakeRealOAuthProvider(config)
    http_app = app.CreateApp(provider)
    http_app.listen(8080)
    client = httpclient.AsyncHTTPClient()
    async def inner() -> None:
        first_response = await client.fetch("http://localhost:8080/account/create", method = "POST", body = "")
        response_body = escape.json_decode(first_response.body)
        state_token = response_body['state_token']
        url = response_body['auth_url']
        print("Go to Authorization URL: {}".format(url))
        second_response = await client.fetch("http://localhost:8080/account/complete?state_token={}".format(state_token), method = "POST", body = "")
        response_body = escape.json_decode(second_response.body)
        print("Response body: {}".format(response_body))

    await asyncio.create_task(inner())

class DumbHandler(web.RequestHandler):
    def get(self) -> None:
        self.finish(f'Hello, World!\nHeaders: {dict(self.request.headers)}')

async def RunDumbServer() -> None:
    http_app = web.Application([
        (r'/', DumbHandler)
    ])
    http_app.listen(8080)

def main() -> None:
    def loop_start(fut: Awaitable[None]) -> None:
        asyncio.create_task(fut)
    asyncio.get_event_loop().call_soon(loop_start, RunDumbServer())
    asyncio.get_event_loop().run_forever()