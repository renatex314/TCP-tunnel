import os
import asyncio
import socket
import jwt
from typing import Awaitable
from websockets.asyncio.client import connect, ClientConnection
from message_exchanger import MessageExchangerClient, MessageExchangerTransport
from models import ConnectionMetadata

TUNNEL_URL = "ws://localhost:8000/tunnel"
TUNNELED_SERVICE_HOST = socket.gethostbyname("www.neverssl.com")
TUNNELED_SERVICE_PORT = 80
LOCAL_SERVICE_PORT = 8070

JWT_SECRET_KEY = os.environ["JWT_SECRET_KEY"]

class WebsocketMessageExchangerTransport(MessageExchangerTransport):

    def __init__(self, ws: ClientConnection):
        self._ws = ws
        self._buffer = b""

    async def send(self, payload: bytes) -> Awaitable[None]:
        await self._ws.send(payload, text=False)

    async def receive(self, max_length: int) -> Awaitable[bytes]:
        while len(self._buffer) < max_length:
            self._buffer += await self._ws.recv(decode=False)

        payload = self._buffer[:max_length]
        self._buffer = self._buffer[max_length:]

        return payload


async def main():
    async with connect(TUNNEL_URL) as ws:
        ws: ClientConnection

        metadata = ConnectionMetadata(
            host=TUNNELED_SERVICE_HOST, port=TUNNELED_SERVICE_PORT
        )

        token = jwt.encode(metadata, JWT_SECRET_KEY, algorithm="HS256")
        await ws.send(token)

        transport = WebsocketMessageExchangerTransport(ws)
        client = MessageExchangerClient(
            transport, host="localhost", port=LOCAL_SERVICE_PORT
        )

        print(
            f"Starting a tunnel to {TUNNELED_SERVICE_HOST}:{TUNNELED_SERVICE_PORT} on port {LOCAL_SERVICE_PORT}"
        )

        await client.start()

        print("Tunnel closed")


if __name__ == "__main__":
    asyncio.run(main())
