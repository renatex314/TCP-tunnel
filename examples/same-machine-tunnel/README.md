# Port Forwarding Example

This example demonstrates how to use python `queues` as a transport layer for TCP tunneling. It showcases a basic setup where incoming TCP connections are forwarded to a to a remote destination through a `asyncio.Queue` structure used as a `MessageExchangerTransport`. It acts as a port forwarder in the same machine.

## Getting Started

- Clone this repository
- Run the main.py script with `python main.py`
