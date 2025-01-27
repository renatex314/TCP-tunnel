import asyncio
import socket
from message_exchanger import MessageExchangerServer, MessageExchangerTransport

SERVICE_ADDR = "0.0.0.0"
SERVICE_PORT = 12345
TARGET_ADDR = socket.gethostbyname("www.neverssl.com")
TARGET_PORT = 80

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
    server = MessageExchangerServer(server_transport, TARGET_ADDR, TARGET_PORT)

    print(f"Forwarding connections from {client.getpeername()} to {TARGET_ADDR}:{TARGET_PORT}")

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