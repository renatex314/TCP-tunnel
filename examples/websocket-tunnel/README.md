# WebSocket TCP Tunnel Example

This example demonstrates how to use WebSockets as a transport layer for TCP tunneling. It showcases a basic setup where incoming TCP connections are forwarded to a to a remote destination through a `WebSocket` connection used as a `MessageExchangerTransport`.

## Getting Started

- Clone this repository
- Install dependencies
- set a environment variable `JWT_SECRET_KEY` with a secret key for the JWT token
- Run the server.py script with `fastapi run server.py`
- Run the client.py script with `python client.py`
