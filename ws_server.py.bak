"""
WebSocket Server for GSP Presentation Remote Control
"""
import asyncio
import json
import websockets
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading
import os

WS_PORT = 8765
HTTP_PORT = 8080

clients = set()
current_slide = "1"

async def handler(websocket):
    global current_slide
    clients.add(websocket)
    client_id = id(websocket)
    print(f"New client connected: {client_id} (Total: {len(clients)})")

    try:
        init_msg = json.dumps({"type": "state", "slide": current_slide, "clients": len(clients)})
        await websocket.send(init_msg)
        await broadcast_clients_count()

        async for message in websocket:
            data = json.loads(message)
            msg_type = data.get("type", "")

            if msg_type == "goto":
                current_slide = data["slide"]
                await broadcast({"type": "goto", "slide": current_slide, "source": client_id})
                print(f"Go to slide: {current_slide}")

            elif msg_type == "next":
                await broadcast({"type": "next", "source": client_id})
                print("Next slide")

            elif msg_type == "prev":
                await broadcast({"type": "prev", "source": client_id})
                print("Previous slide")

            elif msg_type == "first":
                current_slide = "1"
                await broadcast({"type": "first", "source": client_id})
                print("Go to first")

            elif msg_type == "last":
                current_slide = "66"
                await broadcast({"type": "last", "source": client_id})
                print("Go to last")

            elif msg_type == "sync":
                current_slide = data["slide"]
                await broadcast({"type": "sync", "slide": current_slide, "source": client_id}, exclude=[client_id])

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        clients.discard(websocket)
        print(f"Client disconnected: {client_id} (Total: {len(clients)})")
        await broadcast_clients_count()

async def broadcast(message, exclude=None):
    if exclude is None:
        exclude = []
    for client in clients.copy():
        if client not in exclude:
            try:
                await client.send(json.dumps(message))
            except:
                clients.discard(client)

async def broadcast_clients_count():
    await broadcast({"type": "clients_count", "count": len(clients)})

def start_http_server():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    handler = SimpleHTTPRequestHandler
    httpd = HTTPServer(("0.0.0.0", HTTP_PORT), handler)
    print(f"HTTP Server started: http://localhost:{HTTP_PORT}")
    httpd.serve_forever()

async def main():
    print("=" * 50)
    print("GSP Presentation Control System")
    print("=" * 50)
    print(f"WebSocket: ws://localhost:{WS_PORT}")
    print(f"Slides: http://localhost:{HTTP_PORT}/slides.html")
    print(f"Controller: http://localhost:{HTTP_PORT}/controller.html")
    print("=" * 50)

    http_thread = threading.Thread(target=start_http_server, daemon=True)
    http_thread.start()

    async with websockets.serve(handler, "0.0.0.0", WS_PORT):
        print("WebSocket server started, waiting for connections...")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
