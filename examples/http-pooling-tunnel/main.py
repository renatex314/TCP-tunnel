import asyncio
import aiohttp
import socket
import sys
from message_exchanger import (
    MessageExchangerClient,
    MessageExchangerServer,
    MessageExchangerTransport,
)

TARGET_ADDR = "127.0.0.1"
TARGET_PORT = 22
LOCAL_ADDR = "0.0.0.0"
LOCAL_PORT = 8080

SERVER_HOST = "127.0.0.1"
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
        self._running = True

        # Start the pooling tasks
        asyncio.create_task(self.pool())

    async def pool(self):
        await asyncio.gather(
            self.pool_send(),
            self.pool_receive(),
        )

    async def pool_send(self):
        while self._running:
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
        while self._running:
            async with aiohttp.ClientSession() as session:
                # counter = -1

                # async with session.get(
                #     f"http://{SERVER_HOST}:{SERVER_PORT}/packet/counter/{self._client_id}"
                # ) as response:
                #     if response.status == 200:
                #         counter = await response.json()
                #     else:
                #         print(f"Failed to get counter: {response.status}")

                # print("counter", counter, self._receive_counter)
                # if counter >= self._receive_counter:
                async with session.get(
                    f"http://{SERVER_HOST}:{SERVER_PORT}/packet/get/{self._client_id}"
                ) as response:
                    if response.status == 200:
                        payload = await response.read()

                        await self._receive_queue.put(payload)
                        # if len(payload) > 0:
                        # self._receive_counter += 1
                    else:
                        print(f"Failed to receive packet: {response.status}")

                # async with session.post(
                #     f"http://{SERVER_HOST}:{SERVER_PORT}/packet/ack/{self._client_id}"
                # ) as ack_response:
                #     if ack_response.status != 200:
                #         print(f"Failed to acknowledge packet: {ack_response.status}")

            await asyncio.sleep(self.POOLING_RATE)

    async def send(self, payload: bytes):
        print(
            f"Sending payload: {payload}",
            f"Timestamp : {asyncio.get_event_loop().time()}",
        )

        await self._send_queue.put(payload)

    async def receive(self, max_length: int) -> bytes:
        while len(self._buffer) < max_length:
            self._buffer += await self._receive_queue.get()

        payload = self._buffer[:max_length]
        self._buffer = self._buffer[max_length:]

        print(
            f"Received payload: {payload}",
            f"Timestamp : {asyncio.get_event_loop().time()}",
        )

        return payload

    async def stop(self):
        self._running = False

        await self._send_queue.put(b"")  # Ensure the send task exits


async def main(mode: str = "server"):
    my_id = "server" if mode == "server" else "client"
    peer_id = "client" if mode == "server" else "server"

    print(f"Starting {mode} with ID: {my_id}, Peer ID: {peer_id}")

    # print(f"Connecting to server at {SERVER_HOST}:{SERVER_PORT} for registration...")
    # async with aiohttp.ClientSession() as session:
    #     async with session.put(
    #         f"http://{SERVER_HOST}:{SERVER_PORT}/packet/register/{my_id}"
    #     ) as response:
    #         if response.status != 200:
    #             print(f"Failed to register client: {response.status}")

    #             return

    # print(f"Registered {my_id} with peer {peer_id}.")
    transport = PoolingMessageExchangerTransport(my_id, peer_id)

    if mode == "server":
        server = MessageExchangerServer(
            transport,
            TARGET_ADDR,
            TARGET_PORT,
        )
        await server.start()
    elif mode == "client":
        client = MessageExchangerClient(transport, LOCAL_ADDR, LOCAL_PORT)

        await client.start()
    else:
        raise ValueError("Invalid mode. Use 'server' or 'client'.")

    await transport.stop()


if __name__ == "__main__":
    try:
        if len(sys.argv) > 1 and sys.argv[1] == "client":
            asyncio.run(main("client"))
        else:
            asyncio.run(main("server"))
    except KeyboardInterrupt:
        pass
