# Twitch API Usage

The primary reason for having minibot is to allow for interaction with the Twitch API (and perhaps others at a later date). As such, we need to label what resources we use from Twitch, and how we do so.

## Twitch Scopes

For any given user of Minibot, we assume there's a primary account (used for authentication and any streamer services), and a bot account (used for interaction with chat and the like). Each of these needs a different set of scopes to work with.

We intend to use the principle of least permissions, to prevent both ourselves and our users from any mistakes, to avoid a compromise from affecting a user's twitch account more than necessary.

- Streamer Account
    - `channel:read:subscriptions`: To get information about any subscribers for a channel.
        - Get Broadcaster's Subscribers
        - Get Subscription Events
    - `clips:edit`: To be able to create new clips.
    - `user:edit:broadcast`: To be able to do the following operations:
        - Create Stream Marker
        - Get Stream Markers
        - Replace Stream Tags
- Bot Account
    - `channel:moderate`: Allows bot to perform moderation actions in chat
    - `chat:edit`: Allows bot to post messages to stream
    - `chat:read`: Allows bot to read messages from stream
    - `whispers:edit`: Allows bot to whisper to users
    - `whispers:read`: Allows bot to get whispers from users