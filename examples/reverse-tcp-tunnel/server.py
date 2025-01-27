import asyncio
import socket
from message_exchanger import MessageExchangerClient, MessageExchangerTransport

SERVICE_ADDR = "0.0.0.0"
SERVICE_PORT = 12345
LOCAL_ADDR = "127.0.0.1"
LOCAL_PORT = 8080

# Implementation of the transport layer for the message exchanger
class SocketMessageExchangerTransport(MessageExchangerTransport):
    def __init__(self, socket: socket.socket):
        self._socket = socket

    async def send(self, payload: bytes):
        loop = asyncio.get_event_loop()

        await loop.sock_sendall(self._socket, payload)

    async def receive(self, length: int) -> bytes:
        loop = asyncio.get_event_loop()

        payload = await loop.sock_recv(self._socket, length)

        return payload

async def main():
    loop = asyncio.get_event_loop()

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((SERVICE_ADDR, SERVICE_PORT))
    s.listen(5)
    s.setblocking(False)

    print(f"Listening on {SERVICE_ADDR}:{SERVICE_PORT}")
    client, _ = await loop.sock_accept(s)

    server_transport = SocketMessageExchangerTransport(client)
    server = MessageExchangerClient(server_transport, LOCAL_ADDR, LOCAL_PORT)

    print(f"Forwarding local connections from {LOCAL_ADDR}:{LOCAL_PORT}")

    try:
        await server.start()
    except KeyboardInterrupt:
        pass

    print("Connection closed")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass