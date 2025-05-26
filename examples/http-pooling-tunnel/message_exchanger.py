import asyncio
import socket
import time
from typing import Awaitable, Callable, List, TypedDict, Dict, Literal
from abc import ABC, abstractmethod
from uuid import uuid4


class MessageExchangerTransport(ABC):

    @abstractmethod
    async def send(payload: bytes) -> Awaitable[None]:
        pass

    @abstractmethod
    async def receive(max_length: int) -> Awaitable[bytes]:
        pass


MessageExchangerPayloadType = Literal["accept", "send", "close", "ping", "pong"]


class MessageExchangerTransportPayload(TypedDict):
    id: str
    type: MessageExchangerPayloadType
    data: bytes


class MessageExchangerTransportHandler:
    PAYLOAD_DATA_MAX_SIZE = 10240
    HEARTBEAT_TIMEOUT = 10

    def __init__(self, transport: MessageExchangerTransport):
        self._transport = transport
        self._connections: Dict[
            str, asyncio.Queue[MessageExchangerTransportPayload]
        ] = {}
        self._connection_events: asyncio.Queue[MessageExchangerTransportPayload] = (
            asyncio.Queue()
        )
        self._running: bool = False
        self._main_task: asyncio.Task | None = None
        self._heartbeat_task: asyncio.Task | None = None
        self._last_time_since_waiting_pong: float | None = None
        self._on_transport_down: Callable | None = None

    def set_on_transport_down(self, on_transport_down: Callable):
        self._on_transport_down = on_transport_down

    def _get_message_queue(
        self, id: str
    ) -> asyncio.Queue[MessageExchangerTransportPayload]:
        message_queue = self._connections.get(id, None)

        if message_queue is None:
            message_queue = asyncio.Queue()

            self._connections[id] = message_queue

        return message_queue

    def _convert_payload_type_to_code(self, type: MessageExchangerPayloadType) -> int:
        type_mapping: Dict[MessageExchangerPayloadType, int] = {
            "accept": 1,
            "close": 2,
            "send": 3,
            "ping": 4,
            "pong": 5,
        }

        return type_mapping[type]

    def _build_payload(self, message: MessageExchangerTransportPayload) -> List[bytes]:
        data = message.get("data", b"")
        type = message.get("type", "send")
        id = message.get("id", "")

        data_slices = [
            data[i : i + self.PAYLOAD_DATA_MAX_SIZE]
            for i in range(0, len(data), self.PAYLOAD_DATA_MAX_SIZE)
        ]

        raw_payloads: List[bytes] = []

        if len(data_slices) == 0:
            data_slices.append(b"")

        for slice in data_slices:
            payload = b""
            payload += (
                f"{self._convert_payload_type_to_code(type):<2}".encode()
            )  # Payload type
            payload += f"{id:<36}".encode()  # Connection ID
            payload += f"{len(slice):<10}".encode()  # Data length
            payload += slice + bytes(
                b" " for _ in range(len(slice) - self.PAYLOAD_DATA_MAX_SIZE)
            )  # Data
            payload = f"{len(payload):<10}".encode() + payload  # Payload total length

            raw_payloads.append(payload)

        return raw_payloads

    def _parse_payload(self, payload: bytes) -> MessageExchangerTransportPayload:
        type_mapping: Dict[int, MessageExchangerPayloadType] = {
            1: "accept",
            2: "close",
            3: "send",
            4: "ping",
            5: "pong",
        }

        type = type_mapping[int(payload[:2])]
        id = payload[2:38].strip().decode()
        data_length = int(payload[38:48])
        data = payload[48 : 48 + data_length]

        return {"id": id, "type": type, "data": data}

    async def _heartbeat(self):
        while self._running:
            if self._last_time_since_waiting_pong is not None:
                time_elapsed_since_waiting_pong = (
                    time.time() - self._last_time_since_waiting_pong
                )

                await asyncio.sleep(
                    self.HEARTBEAT_TIMEOUT - time_elapsed_since_waiting_pong
                )

                if self._last_time_since_waiting_pong is not None:
                    if self._on_transport_down is not None:
                        try:
                            self._on_transport_down()
                        except Exception as e:
                            pass

                    break

            await self.send_event("", "ping")
            self._last_time_since_waiting_pong = time.time()

    async def _start(self):
        self._running = True

        self._heartbeat_task = asyncio.create_task(self._heartbeat())
        while self._running:
            try:
                try:
                    payload_counter = int(await self._transport.receive(10))
                    payload = await self._transport.receive(payload_counter)
                except:
                    break

                found_errors = False
                while len(payload) != payload_counter:
                    try:
                        payload += await self._transport.receive(
                            payload_counter - len(payload)
                        )
                    except:
                        found_errors = True

                        break

                if found_errors:
                    break

                message = self._parse_payload(payload)

                # print(message)

                if message["type"] == "send":
                    message_queue = self._get_message_queue(message["id"])
                    message_queue.put_nowait(message)

                if message["type"] == "accept":
                    self._connection_events.put_nowait(message)

                if message["type"] == "ping":
                    await self.send_event("", "pong")

                if message["type"] == "pong":
                    self._last_time_since_waiting_pong = None
            except InterruptedError:
                break
            except Exception as e:
                if e.__class__ != asyncio.TimeoutError:
                    print(e)

                continue

        for key, queue in self._connections.items():
            await queue.put({"id": key, "type": "close", "data": b""})

        if self._on_transport_down is not None:
            self._on_transport_down()

    async def start(self):
        self._main_task = asyncio.create_task(self._start())

        await self._main_task

    async def receive_event(self) -> Awaitable[MessageExchangerTransportPayload]:
        return await self._connection_events.get()

    async def receive(self, id: str) -> Awaitable[MessageExchangerTransportPayload]:
        message_queue = self._get_message_queue(id)

        message = await message_queue.get()

        return message

    async def send(self, id: str, message: bytes) -> Awaitable[None]:
        payload_list = self._build_payload({"id": id, "type": "send", "data": message})

        for payload in payload_list:
            await self._transport.send(payload)

    async def send_event(
        self, id: str, event_type: MessageExchangerPayloadType
    ) -> Awaitable[None]:
        payload_list = self._build_payload({"id": id, "type": event_type, "data": b""})

        for payload in payload_list:
            await self._transport.send(payload)

    def stop(self):
        self._running = False

        if self._main_task is not None:
            self._main_task.cancel()

        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()


class MessageExchangerConnectionHandler:

    def __init__(
        self,
        transport_handler: MessageExchangerTransportHandler,
        socket: socket.socket,
        connection_id: str = None,
    ):
        self._transport_handler = transport_handler
        self._socket = socket
        self._running = False
        self._id = connection_id if connection_id is not None else str(uuid4())
        self._alive_counter = 2
        self._on_stop: Callable = None

    def set_on_stop(self, on_stop: Callable):
        self._on_stop = on_stop

    def _check_is_running(self):
        if self._alive_counter <= 0:
            self._running = False

    async def _handle_transport_messages(self):
        while self._running:
            try:
                message = await self._transport_handler.receive(self._id)
            except asyncio.TimeoutError:
                continue

            if message["type"] == "close":
                break

            if message["type"] == "send":
                loop = asyncio.get_event_loop()

                try:
                    await loop.sock_sendall(self._socket, message["data"])
                except:
                    break

        try:
            self._socket.shutdown(socket.SHUT_RDWR)
        except:
            pass

        self._alive_counter -= 1
        self._check_is_running()

    async def _handle_socket_messages(self):
        loop = asyncio.get_event_loop()

        while self._running:
            try:
                data = await loop.sock_recv(self._socket, 1024)
            except:
                break

            if not data:
                break

            await self._transport_handler.send(self._id, data)

        await self._transport_handler.send_event(self._id, "close")

        self._alive_counter -= 1
        self._check_is_running()

    async def send_transport_accept(self):
        await self._transport_handler.send_event(self._id, "accept")

    async def _start(self):
        self._running = True
        self._alive_counter = 2

        loop = asyncio.get_event_loop()

        transport_task = loop.create_task(self._handle_transport_messages())
        socket_task = loop.create_task(self._handle_socket_messages())

        await transport_task
        await socket_task

        if self._on_stop is not None:
            self._on_stop()

    async def start(self):
        self._main_task = asyncio.create_task(self._start())

        await self._main_task

    def stop(self):
        self._running = False

        try:
            self._socket.shutdown(socket.SHUT_RDWR)
        except:
            pass

        if self._main_task is not None:
            self._main_task.cancel()


class MessageExchangerServer:

    def __init__(self, transport: MessageExchangerTransport, host: str, port: int):
        self._transport = transport
        self._transport_handler = MessageExchangerTransportHandler(transport)
        self._transport_handler.set_on_transport_down(self._on_heartbeat_timeout)
        self._connections: List[MessageExchangerConnectionHandler] = []
        self.set_current_target_service(host, port)
        self._main_task: asyncio.Task | None = None
        self._running = False

    def set_current_target_service(self, host: str, port: int):
        self._host = socket.gethostbyname(host)
        self._port = port

    def _on_heartbeat_timeout(self):
        self.stop()
        self._transport_handler.stop()

    def _create_connection_socket(self) -> socket.socket:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setblocking(False)

        return s

    async def _handle_connection_accept(
        self, connection_info: MessageExchangerTransportPayload
    ):
        s = self._create_connection_socket()

        loop = asyncio.get_event_loop()
        await loop.sock_connect(s, (self._host, self._port))

        def remove_connection():
            self._connections.remove(connection_handler)

        connection_handler = MessageExchangerConnectionHandler(
            self._transport_handler, s, connection_id=connection_info["id"]
        )
        connection_handler.set_on_stop(remove_connection)
        asyncio.create_task(connection_handler.start())

        self._connections.append(connection_handler)

    async def _start(self):
        self._running = True

        loop = asyncio.get_event_loop()
        loop.create_task(self._transport_handler.start())

        while self._running:
            try:
                event = await self._transport_handler.receive_event()

                if event["type"] == "accept":
                    asyncio.create_task(self._handle_connection_accept(event))
            except asyncio.CancelledError:
                break
            except asyncio.TimeoutError:
                continue

        self._close_connections()

    async def start(self):
        self._main_task = asyncio.create_task(self._start())

        await self._main_task

    def _close_connections(self):
        [connection.stop() for connection in self._connections]

    def stop(self):
        self._running = False

        if self._main_task is not None:
            self._main_task.cancel()

        self._close_connections()


class MessageExchangerClient:

    def __init__(self, transport: MessageExchangerTransport, host: str, port: int):
        self._transport = transport
        self._transport_handler = MessageExchangerTransportHandler(transport)
        self._transport_handler.set_on_transport_down(self._on_heartbeat_timeout)
        self._connections: List[MessageExchangerConnectionHandler] = []
        self._host = socket.gethostbyname(host)
        self._port = port
        self._main_task: asyncio.Task | None = None
        self._running = True

    def _on_heartbeat_timeout(self):
        self.stop()
        self._transport_handler.stop()

    def _create_service_socket(self) -> socket.socket:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind((self._host, self._port))
        s.listen(10)
        s.setblocking(False)

        return s

    def _handle_connection_accept(self, client: socket.socket):
        connection_handler = MessageExchangerConnectionHandler(
            self._transport_handler, client
        )
        connection_handler.set_on_stop(
            lambda: self._connections.remove(connection_handler)
        )

        asyncio.create_task(connection_handler.send_transport_accept())
        asyncio.create_task(connection_handler.start())

        self._connections.append(connection_handler)

    async def _start(self):
        service_socket: socket.socket = None

        try:
            service_socket = self._create_service_socket()
        except Exception as e:
            print("An error ocurred while creating service socket: ", e)

            return

        loop = asyncio.get_event_loop()
        loop.create_task(self._transport_handler.start())
        while self._running:
            try:
                client, _ = await asyncio.wait_for(
                    loop.sock_accept(service_socket), timeout=1
                )

                self._handle_connection_accept(client)
            except asyncio.CancelledError:
                break
            except asyncio.TimeoutError:
                continue

        service_socket.close()
        self._close_connections()

    async def start(self):
        self._main_task = asyncio.create_task(self._start())

        await self._main_task

    def _close_connections(self):
        [connection.stop() for connection in self._connections]

    def stop(self):
        self._running = False

        if self._main_task is not None:
            self._main_task.cancel()

        self._close_connections()
