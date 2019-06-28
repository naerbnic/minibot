# Bot Architecture

To keep this bot as simple as possible, we push as much of the implementation of the bot itself to a client's (i.e. streamer's) local machine. We provide a service to be an endpoint for OAuth2 requests, to handle webhooks, and provide a consistent message channel to connected clients.

## Server Architecture

As is common, servers often have a lot of moving parts. Here are the parts I believe we'll need.

### Custom Message Broker

This is the component that we implement ourselves, and that communicates with the Twitch API and with the native client.

For the current version, we will likely use SQLite in order to avoid adding more components (such as a separate process database) to the server.

### NGINX Frontend

With the assumption that implementing SSL/HTTPS is something we don't want to have to reimplement, we use an NGINX frontend to act as a reverse HTTPS proxy. It must have access to the SSL certs that are created from Let's Encrypt.

### Let's Encrypt Fetcher

To provide an HTTPS endpoing for OAuth2 and clients, we need to set up a Let's Encrypt process to keep present SSL certs. This has to run about once a month.