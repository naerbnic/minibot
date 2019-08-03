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
- Get all followers for channel
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

All messages on the WebSocket will be text JSON documents.

### RPC format

All RPCs are calls from the client to the server. Each call has a response from the server.

Each message has a "type" field that identifies the type of message being sent, and the other expected fields are based on that type.

#### Hello Message (Server -> Client)

This is the first message sent to the client from the server. This message has info that may be useful for the client. This has type "hello". The other fields are:

- **streamer_name**: The literal name of the streamer's account. This will be the name as seen in IRC, and as such will be all lowercase.
- **bot_name**: The literal name of the bot's account.

The client does not need to wait for the hello message before calling RPCs, although they will not be responded to until the hello message is sent.

#### Call Message (Client -> Server)

Call messages have the literal type "call". The other fields are as follows:

- **id**: An integer that will be used to identify the response. IDs should be in the 32-bit unsigned integer range. IDs can be reused, but IDs should not be used while there are still pending RPCs to avoid confusion.
- **method**: A string indicating which RPC method is being called.
- **params**: A JSON value that is passed as a parameter. What value depends on the method being called.

```json
{
    "type": "call",
    "id": 1,
    "method": "sendmsg",
    "params": {
        "text": "foobar!",
    }
}
```

#### Response Message (Server -> Client)

Response messages have the literal type "resp". The other fields are as follows:

- **id**: An integer that was taken from the call message this is a response to.
- **result**: A JSON object indicating the result of the call. Note that this includes any method-specific errors (as opposed to protocol errors).

#### Event Message (Server -> Client)

Through RPCs, the client may establish it is interested in events from the server. The server sends event messages using messages with the "event" type. The other fields are as follows:

- **id**: An ID established in the RPC to identify the event stream. This is a different ID namespace than those used for "call" or "resp" events.
- **evts**: A JSON list of event objects. This allows the server to batch multiple events if needed.

Event objects have the field "type" to indicate what type of event it is, and the other fields depend on that type.

#### Error Message (Server -> Client)

There may be errors that the client needs to know about. These are generally about the general state of the current websocket session, and not simply a response to an RPC. Error messages have a field "type" of value "error". Other fields are:

- **error_type**: A string that unformly identifies the type of this error. This can be used by the client to identify actions necessary, if any.
- **description**: A human-readable string that describes the error more thoroughly. These may be useful to add to a log on the client side.
- **data**: Optional structured data about the error.

### RPC Methods

These are the different RPC methods the client can call on the server.

#### `get_chat_users`

Get the list of users who are currently in the chat room.

**Params**: An empty object

**Result**: An object with the following fields:

- **users**: A string list, where each string is a username of people currently in the streamer's chat. This may be incomplete if there are sufficient users.
- **num_users**: An integer of the number of users in chat.

#### `get_subscribers`

#### `get_followers`

#### `chat_msg`

#### `whisper_msg`

#### `chat_clear`

#### `ban`

#### `unban`

#### `marker`

#### `clip`

#### `listen`

Start listening to one or more event messages.

Params: Object with the following fields

- **event_id**: A unsigned 32-bit integer value that will be used as an event stream ID. Should not be the same as any current event stream.
- **event_types**: A list of strings with the types of events that the user wants to listen to.

Response: Object with the following fields:

- **success**: A boolean if the listening was valid.
- **registered_types**: A list of strings with the events that will be sent to the user.

Event messages will be sent with the given **event_id** for the listened to events.

#### `unlisten`

Stop listening to an event stream.

### Event Messages

#### `user_chat_join`

#### `user_chat_leave`

#### `user_follow`

#### `user_unfollow`

#### `user_subscribe`

#### `gift_subscribe`

#### `user_unsubscribe`

#### `user_subscribe_notify`

#### `user_chat_command`

#### `bot_whisper`

#### `user_host`

#### `user_unhost`

#### `user_cheer`
