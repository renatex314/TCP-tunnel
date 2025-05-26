import asyncio
import aiohttp
import socket
import sys
from message_exchanger import (
    MessageExchangerClient,
    MessageExchangerServer,
    MessageExchangerTransport,
)

TARGET_ADDR = socket.gethostbyname("www.neverssl.com")
TARGET_PORT = 80
LOCAL_ADDR = "0.0.0.0"
LOCAL_PORT = 8080

SERVER_HOST = "localhost"
SERVER_PORT = 8000


class PoolingMessageExchangerTransport(MessageExchangerTransport):
    POOLING_RATE = 0.1

    def __init__(self, client_id: str, peer_client_id: str):
        self._receive_counter = 0
        self._send_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._receive_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._client_id = client_id
        self._peer_client_id = peer_client_id
        self._buffer = b""

    async def pool_send(self):
        while True:
            if not self._send_queue.empty():
                payload = await self._send_queue.get()

                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"http://{SERVER_HOST}:{SERVER_PORT}/packet/send/{self._peer_client_id}",
                        data=payload,
                    ) as response:
                        if response.status != 200:
                            print(f"Failed to send packet: {response.status}")

            await asyncio.sleep(self.POOLING_RATE)

    async def pool_receive(self):
        while True:
            async with aiohttp.ClientSession() as session:
                counter = -1

                async with session.get(
                    f"http://{SERVER_HOST}:{SERVER_PORT}/packet/counter/{self._client_id}"
                ) as response:
                    if response.status == 200:
                        counter = await response.json()
                    else:
                        print(f"Failed to get counter: {response.status}")

                if counter == self._receive_counter:
                    async with session.get(
                        f"http://{SERVER_HOST}:{SERVER_PORT}/packet/receive/{self._client_id}"
                    ) as response:
                        if response.status == 200:
                            payload = await response.read()

                            await self._receive_queue.put(payload)
                            self._receive_counter += 1
                        else:
                            print(f"Failed to receive packet: {response.status}")

                async with session.get(
                    f"http://{SERVER_HOST}:{SERVER_PORT}/packet/ack/{self._client_id}"
                ) as ack_response:
                    if ack_response.status != 200:
                        print(f"Failed to acknowledge packet: {ack_response.status}")

            await asyncio.sleep(self.POOLING_RATE)

    async def send(self, payload: bytes):
        await self._send_queue.put(payload)

    async def receive(self, max_length: int) -> bytes:
        while len(self._buffer) < max_length:
            self._buffer += await self._receive_queue.get()

        payload = self._buffer[:max_length]
        self._buffer = self._buffer[max_length:]

        return payload


async def main(mode: str = "server"):
    my_id = "server" if mode == "server" else "client"
    peer_id = "client" if mode == "server" else "server"

    transport = PoolingMessageExchangerTransport(my_id, peer_id)

    if mode == "server":
        server = MessageExchangerServer(
            host=TARGET_ADDR,
            port=TARGET_PORT,
            transport=transport,
        )
        await server.start()
    elif mode == "client":
        client = MessageExchangerClient(transport, LOCAL_ADDR, LOCAL_PORT)

        await client.start()
    else:
        raise ValueError("Invalid mode. Use 'server' or 'client'.")

    # Keep the event loop running
    await asyncio.Event().wait()  # This will block forever, simulating a long-running process.


if __name__ == "__main__":
    try:
        if len(sys.argv) > 1 and sys.argv[1] == "client":
            asyncio.run(main("client"))
        else:
            asyncio.run(main("server"))
    except KeyboardInterrupt:
        pass
