# Security and Authentication

This document talks about the general security design of the app, and what issues and decisions we have made.

## Accunt Creation

The steps in the account creation flow from the native client:

1. The client app POSTs to the account creation endpoint.

   We perform all of these actions over HTTPS to ensure that any data set over this channel cannot be eavesdropped by a third party.

   We probably want to use an XSRF key to prevent even accidental multiPOSTing

2. Server responds with a document providing a temporary state key and a URL to send the user to in a local web-browser.

   We can encode the state key itself into the state field of the oauth2 request URL, so we may not even have to keep any internal storage. We can encrypt/HMAC the state to ensure that the relationship cannot be spoofed elsewhere.

3. User proceeds through the OAuth2 login using the URL.

   When the flow completes, the server keeps the auth token and id token in storage keyed by the state key returned in step 2.

4. The client app POSTs to the login completion endpoint with the state key.

   This connection will hang if done before the OAuth2 login completes.

5. The server responds with an error (if there was a problem logging in) or by creating the account and returning the id token in the POST response.

   We don't want to be responsible for keeping passwords for users if we can avoid it. OpenID provides us a way for a client to get an authentication token which when provided to the server can prove a number of things:

   - Prove which user obtained the token
   - Prove which service provider obtained the token
   - Prove which client ID the token was obtained for.
   - Prove when the token was created
   - Prove when the token should expire

   These can be validated without having to use an API endpoint on the authentication server.

   This token is secret to the user and the server, and should be protected by any reasonable means.

   The state key provided at the start is discarded.

### Alternatives

#### Client OID Token

Have the user obtain their own OID token through a native-app conforming provider and use that key to proceed through the account creation flow.

This may seem to be more secure at first, but is in fact no more so than this version of the flow. The user would still obtain their OID token as part of the process, which can be spoofed as easily by a third party as this process. The disadvantages is that we must keep track of a small amount of state (the state key and login state) on our server, vs. using a the authentication provider's server. As this is primarily used for login events only, and can have a short term expiry, this shouldn't be a bit problem.

Attacker approach in above flow:

1. Attacker binary on users desktop POSTs an account creation request

2. Attacker binary opens a web browser with URL, convincing user that the unrelated login screen is the correct one.

3. Attacker binary POSTs the account creation completion endpoint, obtaining the user's credentials.

4. Attacker binary uses Minibot API for its purposes.

Attacker approach in this alternative flow:

1. Attacker binary obtains client-id and/or secret from real binary

2. Attacker binary crafts OpenID authentication request URL, and proceeds through authentication.

3. Attacker binary starts account creation flow using OID token on server.

4. Attacker opens account authorization flow URL for user.

5. Attacker has user credentials and a new account.

The only advantage is in doing it in two phases (also doable with current Twitch OpenID) there are multiple chances for the service to be caught. These approches are equivalent, just that this alternative makes the security more complex.

As mentioned, we can likely encode the state information into the oauth2 state key itself (encrypted symmetrically) so that we don't have to save any state at all.

#### Redirect to local HTTP Server

Suggest the following protocol:

1. Client opens a local HTTP Server on a loopback device (either `127.0.0.1` for IPv4, or `[::1]` for IPv6). These may bind to an arbitrary port. Note that this _does not_ use HTTPS.

   The order here is important. By setting up the web address first, we can be sure that no other process binds a socket to the port we report to the server.

2. Client `POST`s to a server endpoint with the IP address and port selected for the server. They also send a code challenge which is a hash of some data the client only knows.

3. Server verifies that the IP address is a valid loopback address (for either IPv4 or IPv6).

4. Server registers the IP/port/challenge combination to a secure random token.

5. Server replies to the client's `POST` with a authorization URL including the random token as the state field.

6. Client directs the user to the authorization URL via a local user agent (e.g. web browser).

7. User proceeds through the OAuth process. On success, the user agent redirects to the server's OAuth callback address.

8. The server recieves the code via the callback address, finds the IP/port/challenge combo. It registers the code challenge and oauth code to a new secure random token.

9. Server redirects the user agent to the IP/port, along with the new token.

   We assume this token may be intercepted, as it's transferred in plaintext, even if it's on the same machine.

10. Client recieves the HTTP request with the token.

11. Client `POST`s the token and the challenge verifier (the unhashed data) via HTTPS to the server.

12. The server verifies that the hash of the verifier matches the challenge stored for the token.

13. The server performs the OAuth code exchange, and creates the user's account. It returns a login auth token to the client.

This process is more complex than that of the basic POST authorization. It is intended to prevent an attacker from being able to create an account without any kind of local control over the user's machine. This protocol requires that an attacker open up a webserver locally on the client's machine and convince that same user to through the OAuth authentication process on that machine. This can only realistically happen if the user runs a malicious binary on their computer, which is a level of compromised that we can't have much control over.

This approach is a variant on the recommendations for [OAuth 2.0 for Native Apps](https://tools.ietf.org/html/rfc8252). Some specific observations:

- The user must provide an IP address, not the literal domain `localhost` as that can potentially be rebound by malicious code. This doesn't prevent attacks entirely, but reduces the attack surface.

## Twitch Account Authorization

Once a user has an account, he has to authorize his streamer account and a bot account with his minibot account to let the server control those accounts during a stream.

The short version is that we'll use the WebSocket connection (authenticated via OID token against) in order to go through the flow. The native client will send a request message to authorize a streamer/bot account. The server will respond with a message providing a URL that it should direct a local browser to. The server will proceed with the typical OAuth2 flow to obtain the expected scopes for streamer/bot accounts, then send another message on the websocket indicating that the process completed successfully (if it did).

Security wise, the security of this process is based on the secrecy of the valid OID token.

*FIXME: Add detailed twitch account authorization flow*