"""The primary Tornado application"""

from tornado import web
import asyncio
import secrets
import logging
import time

from . import oauth

LOG = logging.Logger(__name__)

class OAuthRedirectHandler(web.RequestHandler):
    _callback_manager: oauth.OAuthCallbackManager

    def initialize(self, callback_manager: oauth.OAuthCallbackManager) -> None:
        self._callback_manager = callback_manager

    def get(self) -> None:
        state = self.get_argument('state')
        code = self.get_argument('code')
        asyncio.create_task(self._callback_manager.complete(state, code))

class StartAccountCreateHandler(web.RequestHandler):
    _callback_manager: oauth.OAuthCallbackManager
    _creation_manager: oauth.AccountCreationManager

    def initialize(self, callback_manager: oauth.OAuthCallbackManager, creation_manager: oauth.AccountCreationManager) -> None:
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
    _creation_manager: oauth.AccountCreationManager

    def initialize(self, creation_manager: oauth.AccountCreationManager) -> None:
        self._creation_manager = creation_manager

    async def post(self) -> None:
        state_token = self.get_argument('state_token')
        result = await self._creation_manager.wait_result(state_token)
        LOG.error(result)
        token = result.TryGet(oauth.Timestamp(int(time.time())))
        assert token is not None
        self.write(token)

class HelloWorldHandler(web.RequestHandler):
    def get(self) -> None:
        value = self.get_argument('name', default=None)
        if value is not None:
            self.write("Hello, %s!" % value)
        else:
            self.write("Hello, World!")
        self.finish()

def CreateApp(provider: oauth.OAuthProvider) -> web.Application:
    """Creates the minibot server application."""
    callbacks = oauth.OAuthCallbackManager(provider)
    creations = oauth.AccountCreationManager()
    return web.Application([
        (r'/callback', OAuthRedirectHandler, dict(callback_manager=callbacks)),
        (r'/account/create', StartAccountCreateHandler, dict(callback_manager=callbacks, creation_manager=creations)),
        (r'/account/complete', CompleteAccountCreateHandler, dict(creation_manager=creations)),
    ])