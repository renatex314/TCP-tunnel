import asyncio
import socket
from message_exchanger import MessageExchangerServer, MessageExchangerClient, MessageExchangerTransport

TARGET_ADDR = socket.gethostbyname("www.neverssl.com")
TARGET_PORT = 80
LOCAL_ADDR = "0.0.0.0"
LOCAL_PORT = 8080

# Implementation of the transport layer for the message exchanger
class QueueMessageExchangerTransport(MessageExchangerTransport):
    def __init__(self):
        self._queue = asyncio.Queue()
        self._peer: QueueMessageExchangerTransport = None
        self._buffer = b""

    def link(self, peer: "QueueMessageExchangerTransport"):
        self._peer = peer
        peer._peer = self

    async def send(self, payload: bytes):
        await self._peer._queue.put(payload)
    
    async def receive(self, max_length: int) -> bytes:
        while len(self._buffer) < max_length:
            self._buffer += await self._queue.get()

        payload = self._buffer[:max_length]
        self._buffer = self._buffer[max_length:]

        return payload

async def main():
    server_transport = QueueMessageExchangerTransport()
    client_transport = QueueMessageExchangerTransport()
    server_transport.link(client_transport)

    server = MessageExchangerServer(server_transport, TARGET_ADDR, TARGET_PORT)
    client = MessageExchangerClient(client_transport, LOCAL_ADDR, LOCAL_PORT)

    print(f"Forwarding local connections from {LOCAL_ADDR}:{LOCAL_PORT} to {TARGET_ADDR}:{TARGET_PORT}")

    try:
        await asyncio.gather(
            server.start(),
            client.start()
        )
    except KeyboardInterrupt:
        pass

    print("Forwarding finished")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass