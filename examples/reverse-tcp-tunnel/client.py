import asyncio
import socket
from message_exchanger import MessageExchangerServer, MessageExchangerTransport

SERVICE_ADDR = "127.0.0.1"
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
    s.setblocking(False)
    await loop.sock_connect(s, (SERVICE_ADDR, SERVICE_PORT))

    client_transport = SocketMessageExchangerTransport(s)
    client = MessageExchangerServer(client_transport, TARGET_ADDR, TARGET_PORT)

    print(f"Connected to {SERVICE_ADDR}:{SERVICE_PORT} and forwarding connections to {TARGET_ADDR}:{TARGET_PORT}")

    try:
        await client.start()
    except KeyboardInterrupt:
        pass

    print("Connection closed")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
