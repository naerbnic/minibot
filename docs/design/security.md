# Security and Authentication

This document talks about the general security design of the app, and what issues and decisions we have made.

## Accunt Creation

The steps in the account creation flow from the native client:

1. User obtains an OpenID Token from an authorization (authn) provider via the native app.

   We don't want to be responsible for keeping passwords for users if we can avoid it. OpenID provides us a way for a client to get an authentication token which when provided to the server can prove a number of things:

   - Prove which user obtained the token
   - Prove which service provider obtained the token
   - Prove which client ID the token was obtained for.
   - Prove when the token was created
   - Prove when the token should expire

   This can be obtained from the native app independent of a server via the process recommended in [RFC 8252](https://tools.ietf.org/html/rfc8252). This must include the ability to redirect to a `localhost` HTTP server, and the usage of [PKCE](https://tools.ietf.org/html/rfc7636). Unfortunately, this requires us to use an authentication provider which provides these capabilities. I believe that Google's OpenID Connect implementation does follow this (at least for `http://127.0.0.1/` URLs). While Twitch provides OpenID Connect support, it does not allow for these features, so we have to use a secondary authn provider.

   This token is secret to the user and the server, and should be protected by any reasonable means.

2. User sends their OID Token to the server as part of an endpoint to create an account via a POST.

   Should probably follow the spec about the authentication header, and treat the token as a bearer token.

3. The server validates the token and it's properties ("claims") against the login policy. Rejects the request if it fails (401 Unauthorized)

   This can include checking the token against revocation (e.g. a marked time before which we won't accept tokens), checking our own expiration policty, etc.

4. Create a new account with parameters from POST.

   We use the `sub` (subscriber) claim from the OID token as the login key stored in the user database. Note that we don't store the token itself, which prevents a database compromise from being able to log into our service without third-party authn.

   We may be able to get an email address from the OID token as well.

## Twitch Account Authorization

Once a user has an account, he has to authorize his streamer account and a bot account with his minibot account to let the server control those accounts during a stream.

The short version is that we'll use the WebSocket connection (authenticated via OID token against) in order to go through the flow. The native client will send a request message to authorize a streamer/bot account. The server will respond with a message providing a URL that it should direct a local browser to. The server will proceed with the typical OAuth2 flow to obtain the expected scopes for streamer/bot accounts, then send another message on the websocket indicating that the process completed successfully (if it did).

Security wise, the security of this process is based on the secrecy of the valid OID token.

*FIXME: Add detailed twitch account authorization flow*