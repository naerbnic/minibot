from tornado.testing import AsyncHTTPTestCase, gen_test
from tornado import web
from tornado import httpclient as hc
import json
import logging
import urllib

from minibot_server import oauth, app
from minibot_server.testing import oauth as oauth_testing

LOG = logging.Logger(__name__)

class OauthTest(AsyncHTTPTestCase):
    provider: oauth_testing.FakeOAuthProvider

    def get_app(self) -> web.Application:
        self.provider = oauth_testing.FakeOAuthProvider()
        return app.CreateApp(self.provider)

    @gen_test
    async def testAccountCreate(self) -> None:
        client = hc.AsyncHTTPClient()
        resp = await client.fetch(self.get_url('/account/create'), method='POST', body='')
        body = json.loads(resp.body)
        LOG.error(body)
        state_token = body['state_token']
        auth_url = body['auth_url']
        await self.provider.AcceptAuth(self.get_url('/callback'), auth_url)
        base_url = self.get_url('/account/complete')
        complete_url = f'''{base_url}?{urllib.parse.urlencode({
            'state_token': state_token
        })}'''
        resp = await client.fetch(complete_url, method='POST', body='')

