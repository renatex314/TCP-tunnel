from fastapi import FastAPI, Request, Response

app = FastAPI()


class PacketQueue:

    def __init__(self):
        self._counter = 0
        self._queue = []

    def add_packet(self, packet: bytes):
        self._queue.append(packet)

    def get_packet(self) -> bytes:
        return self._queue.pop(0) if self._queue and len(self._queue) > 0 else b""

    def ack_packet(self):
        if self._queue and len(self._queue) > 0:
            self._queue.pop(0)
            self._counter += 1

    def get_counter(self) -> int:
        return self._counter


packet_queues: dict[str, PacketQueue] = {}


# @app.put("/packet/register/{client_id}")
# def register_client(client_id: str):
#     packet_queues[client_id] = PacketQueue()

#     return {"status": "registered", "client_id": client_id}


# @app.get("/packet/counter/{client_id}", response_model=int)
# def get_counter(client_id: str):
#     if client_id not in packet_queues:
#         return {"error": "client not registered"}, 404

#     packet_queue = packet_queues[client_id]
#     return packet_queue.get_counter()


@app.get("/packet/get/{client_id}")
def get_packet(client_id: str):
    if client_id not in packet_queues:
        packet_queues[client_id] = PacketQueue()

    packet_queue = packet_queues[client_id]
    packet = packet_queue.get_packet()

    return Response(content=packet, media_type="application/octet-stream")


# @app.post("/packet/ack/{client_id}")
# def ack_packet(client_id: str):
#     if client_id not in packet_queues:
#         return {"error": "client not registered"}, 404

#     packet_queue = packet_queues[client_id]
#     packet_queue.ack_packet()

#     return {
#         "status": "acknowledged",
#         "client_id": client_id,
#         "counter": packet_queue.get_counter(),
#     }


@app.post("/packet/send/{client_id}")
async def send_packet(client_id: str, request: Request):
    if client_id not in packet_queues:
        packet_queues[client_id] = PacketQueue()

    packet = await request.body()

    if not packet:
        return None

    packet_queue = packet_queues[client_id]
    packet_queue.add_packet(packet)

    return {
        "status": "packet sent",
        "client_id": client_id,
        "counter": packet_queue.get_counter(),
    }


@app.get("/clients")
def get_clients():
    return {"clients": list(packet_queues.keys())}
