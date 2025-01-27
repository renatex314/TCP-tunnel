# Reverse TCP Tunnel Example

This example demonstrates how to use common sockets as a transport layer for TCP tunneling. It showcases a basic setup where incoming TCP connections are forwarded to a to a remote destination through a `Socket` connection used as a `MessageExchangerTransport`. It's very similar to the [TCP Tunnel Example](../websocket-tunnel/README.md), but using the `client.py` as the one who forwards the connections of the `server.py` instead of the `server.py` forwarding the connections of the `client.py`.

## Getting Started

- Clone this repository
- Run the server.py script with `python server.py`
- Run the client.py script with `python client.py`
