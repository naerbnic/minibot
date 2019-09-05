from tornado.testing import AsyncHTTPTestCase, gen_test
from tornado import web
from tornado import httpclient as hc
from minibot_server import oauth, app
from minibot_server.testing import oauth as oauth_testing

class OauthTest(AsyncHTTPTestCase):
    provider: oauth_testing.FakeOAuthProvider

    def get_app(self) -> web.Application:
        self.provider = oauth_testing.FakeOAuthProvider("/callback")
        return app.CreateApp(self.provider)

    @gen_test
    async def testAccountCreate(self) -> None:
        client = hc.AsyncHTTPClient()
        resp = await client.fetch(self.get_url('/account/create'), method='POST', body='')
