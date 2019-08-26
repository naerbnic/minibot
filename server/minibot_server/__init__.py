from .oauth import (AccountCreationManager, OAuthCallbackManager, OAuthClientInfo, TWITCH_PROVIDER, OAuthProvider, OAuthProviderImpl)

from tornado import web, ioloop, httpclient, escape
import asyncio
import secrets
import yaml
import os

from .config import ReadConfig

from typing import Awaitable

class OAuthRedirectHandler(web.RequestHandler):
    _callback_manager: OAuthCallbackManager

    def initialize(self, callback_manager: OAuthCallbackManager) -> None:
        self._callback_manager = callback_manager

    def get(self) -> None:
        state = self.get_argument('state')
        code = self.get_argument('code')
        asyncio.create_task(self._callback_manager.complete(state, code))

class StartAccountCreateHandler(web.RequestHandler):
    _callback_manager: OAuthCallbackManager
    _creation_manager: AccountCreationManager

    def initialize(self, callback_manager: OAuthCallbackManager, creation_manager: AccountCreationManager) -> None:
        self._callback_manager = callback_manager
        self._creation_manager = creation_manager

    async def post(self) -> None:
        token = secrets.token_urlsafe(30)
        (url, callback) = await self._callback_manager.start_auth()
        await self._creation_manager.add_creation(token, callback)
        self.write({
            'state_token': token,
            'auth_url': url,
        })

class CompleteAccountCreateHandler(web.RequestHandler):
    _creation_manager: AccountCreationManager

    def initialize(self, creation_manager: AccountCreationManager) -> None:
        self._creation_manager = creation_manager

    async def post(self) -> None:
        token = self.get_argument('state_token')
        result = await self._creation_manager.wait_result(token)
        self.write(result)

class HelloWorldHandler(web.RequestHandler):
    def get(self) -> None:
        value = self.get_argument('name', default=None)
        if value is not None:
            self.write("Hello, %s!" % value)
        else:
            self.write("Hello, World!")
        self.finish()


def MakeServer() -> web.Application:
    config = ReadConfig()
    client_info = OAuthClientInfo(
        client_id = config.config_doc.twitch_client_id,
        client_secret = config.secret_doc.twitch_client_secret,
        redirect_url = config.config_doc.twitch_redirect_url,
    )
    provider = OAuthProviderImpl(client_info, TWITCH_PROVIDER)
    callbacks = OAuthCallbackManager(provider)
    creations = AccountCreationManager()
    return web.Application([
        (r'/callback', OAuthRedirectHandler, dict(callback_manager=callbacks)),
        (r'/account/create', StartAccountCreateHandler, dict(callback_manager=callbacks, creation_manager=creations)),
        (r'/account/complete', CompleteAccountCreateHandler, dict(creation_manager=creations)),
    ])

async def TestAccountCreateExchange() -> None:
    app = MakeServer()
    app.listen(8080)
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
    config = ReadConfig()
    app = web.Application([
        (r'/', DumbHandler)
    ])
    app.listen(8080)

def main() -> None:
    def loop_start(fut: Awaitable[None]) -> None:
        asyncio.create_task(fut)
    asyncio.get_event_loop().call_soon(loop_start, RunDumbServer())
    asyncio.get_event_loop().run_forever()