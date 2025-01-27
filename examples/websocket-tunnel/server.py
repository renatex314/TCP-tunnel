import os
import jwt
from typing import Awaitable
from fastapi import FastAPI, WebSocket
from message_exchanger import (
    MessageExchangerTransport,
    MessageExchangerServer,
)
from models import ConnectionMetadata

JWT_SECRET_KEY = os.environ["JWT_SECRET_KEY"]


class WebsocketMessageExchangerTransport(MessageExchangerTransport):

    def __init__(self, ws: WebSocket):
        self._ws = ws
        self._buffer = b""

    async def send(self, payload: bytes) -> Awaitable[None]:
        await self._ws.send_bytes(payload)

    async def receive(self, max_length: int) -> Awaitable[bytes]:
        while len(self._buffer) < max_length:
            self._buffer += await self._ws.receive_bytes()

        payload = self._buffer[:max_length]
        self._buffer = self._buffer[max_length:]

        return payload


app = FastAPI()


@app.get("/")
def hello_world():
    return {"message": "Hello Tunnel!"}


@app.websocket("/tunnel")
async def tunnel_websocket(ws: WebSocket):
    await ws.accept()

    token = await ws.receive_text()

    try:
        metadata: ConnectionMetadata = jwt.decode(
            token, JWT_SECRET_KEY, algorithms=["HS256"]
        )
    except Exception as e:
        print(e)

        await ws.send_text("Invalid token")

        return

    if "host" not in metadata or "port" not in metadata:
        await ws.send_text("Invalid metadata")
        await ws.close()

        return

    transport = WebsocketMessageExchangerTransport(ws)
    server = MessageExchangerServer(transport, metadata["host"], metadata["port"])

    print(f'Starting a tunnel to {metadata["host"]}:{metadata["port"]}')

    await server.start()

    print(f'Tunnel to {metadata["host"]}:{metadata["port"]} closed')
