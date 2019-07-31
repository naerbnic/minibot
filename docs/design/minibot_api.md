# Minibot API

To work with Twitch, the Minibot local client talks to the Minibot Server to perform actions on behalf of the streamer. This API is split into two rough parts: The HTTP API used to create and authenticate a user, and the Websocket protocol used to perform real-time authenticated communication with the server.

## High-Level Overview

Since we push most of the complex operations to the local client, the only operations we require of minibot are those necessary to implement the local functionality.

Operations are generally split into events and commands. Events are things that happen on the Twitch platform that the client may be interested in. Commands are operations the client wants to execute on Twitch.

### Events

- A user arrives in chat
- A user leaves chat
- A user follows
- A user unfollows
- A user subscribes
- A user gifts a subscription
- A user unsubscribes
- A user sends subscribe notification
- A user runs a chat command (starting with "!")
- A user whispers to the ChatBot
- A user hosts the channel
- A user unhosts the channel
- A user cheers bits

### Commands

- Get all users in chat
- Get all subscribers to channel
- Have ChatBot send a message in chat
- Have ChatBot send a message to a user via whisper
- Have ChatBot clear chat
- Have ChatBot ban a user
- Have ChatBot unban a user
- Add a marker to stream
- Add a clip to channel

## HTTP API

Although most of the operations done by Minibot are done through the websocket channel, some steps have to be done before a websocket channel can be established. This primarily consists of operations for account creation, configuration, and authentication.

Note that all operations MUST be performed through HTTPS, in order to preserve the secrecy of the data exchanged over the channel.

We do not provide XSRF token protection for these endpoints, as they're not called by browsers, and their security is not maintained by cookies.

Some endpoints are described as SECURE, meaning they require an authorization token header to be called (or else will fail with a 403 status code). The authorization token must be provided as a bearer token to these calls.

### `POST /accounts/create/start`

This starts the process to create a new Minibot account on the server. This call takes no query or body arguments. It returns a JSON object with the following fields:

- `state_token`: A unique token use to obtain the result of this creation attempt
- `auth_url`: A URL to open a webbrowser to that will allow the client to authorize the account creation attempt.

This by itself does not complete the authorization. The exchange must be completed by the `POST /accounts/complete` endpoint.

### `POST /accounts/create/complete`

This finishes the process to create a new Minibot account on the server. This call takes one query argument:

- `state_token`: A state token obtained from a call to `POST /accounts/create/start`.

This completion will hang until the user has completed their authorization using the provided `auth_url` returned from `POST /accounts/create/start`.

If successful, this will return a JSON object with the following fields:

- `user_name`: A string containing the created user's Twitch username.
- `user_id`: A string representing the created user. This is the primary ID used in Minibot to identify the user across multiple logins.
- `auth_token`: An authorization token used to provide access to secure APIs for Minibot

FIXME: Add description of possible error conditions (e.g. denied authorization, user already exists, etc.)

### `POST /accounts/login/start`

This starts the process of logging in for a user. This assumes a user already exists. This is analogous to `POST /accounts/create/start`, with the addition of a query parameter:

- `change_user`: A boolean (`true`/`false`) parameter. If true, the user will be asked to choose which user they're logging in as. This allows a user to switch accounts.

Otherwise, the result and process is the same as `POST /accounts/create/start`, with the next step being `POST /accounts/login/complete`.

### `POST /accounts/login/complete`

FIXME: Fill in what is needed from the above complete method.

### `POST /accounts/associate-bot/start` (SECURE)

This starts the process for associating a bot with an existing account. The process is like the other `start`/`complete` actions above. This takes no query parameters, and will always explicitly ask for an account. The associated bot will _replace_ any that is already associated.

### `POST /accounts/associate-bot/complete`

FIXME: Same as above, however this needs to report success/failure, and won't report a new auth token.

## Websocket API

The websocket API is accessible on the server at path `/channel/ws`. The client MUST provide an auth token in the initial headers in order to establish this connection. As we require HTTP traffic to go over the HTTPS protocol, we require the websocket to operate on the WSS protocol.

On starting a websocket connection, the Server will start up connections and associations necessary on Twitch to provide the features of the websocket protocol. This includes access to chat, any PubSub endpoints necessary, and starting any Webhook subscriptions necessary. The lifetime of these are all connected to the lifetime of the websocket connection, and will be unregistered if the local client disconnects from the API.

### RPC format

Aside from the "hello" message (sent by the server when first connected) all messages from the server are initiated by the client. The client sends a JSON
object with the general format:

FIXME: Complete this section

