from tornado.testing import AsyncHTTPTestCase, gen_test
from tornado import web
from minibot_server import oauth

class OauthTest(AsyncHTTPTestCase):
    def get_app(self) -> web.Application:
        return web.Application()

    @gen_test
    async def testNothing(self) -> None:
        pass