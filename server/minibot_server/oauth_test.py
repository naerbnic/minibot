from tornado.testing import AsyncHTTPTestCase, gen_test
from tornado.web import Application, RequestHandler

class OauthTest(AsyncHTTPTestCase):
    def get_app(self):
        return Application()

    @gen_test
    async def testNothing(self):
        pass