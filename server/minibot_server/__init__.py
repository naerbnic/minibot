from .oauth import (AccountCreationManager, OAuthCallbackManager, OAuthClientInfo, TWITCH_PROVIDER, OAuthProvider)

from tornado import web, ioloop
import asyncio
import secrets
import yaml
import os

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
        result = self._creation_manager.wait_result(token)
        self.write(result)

class HelloWorldHandler(web.RequestHandler):
    def get(self) -> None:
        value = self.get_argument('name', default=None)
        if value is not None:
            self.write("Hello, %s!" % value)
        else:
            self.write("Hello, World!")
        self.finish()


def ReadConfig():
    homedir = os.getenv("HOME")
    if homedir is None:
        raise ValueError()
    yaml_path = os.path.join(homedir, ".config/minibot/config.yaml")
    config_data = yaml.safe_load(open(yaml_path, mode = 'r').read())
    return OAuthClientInfo(
        config_data['client_id'],
        config_data['client_secret'],
        config_data['redirect_url'])


def main():
    print('Starting app at 8080')
    client_info = ReadConfig()
    provider = OAuthProvider(client_info, TWITCH_PROVIDER)
    callbacks = OAuthCallbackManager(provider)
    creations = AccountCreationManager()
    app = web.Application([
        (r'/callback', OAuthRedirectHandler, dict(callback_manager=callbacks)),
        (r'/account/create', StartAccountCreateHandler, dict(callback_manager=callbacks, creation_manager=creations)),
        (r'/account/complete', CompleteAccountCreateHandler, dict(creation_manager=creations)),
    ])
    app.listen(8080)

    ioloop.IOLoop.current().start()