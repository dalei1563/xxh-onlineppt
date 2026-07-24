"""独立 AI 语音对话服务入口。

该进程只负责 GLM-Realtime 会话和配套前端，不依赖 PPT 的数据库、
演示状态或 WebSocket。PPT 仅通过 iframe 和 postMessage 接入。
"""
import json
import mimetypes
import os
import sys
import uuid
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv


SERVICE_DIR = Path(__file__).resolve().parent
REPO_DIR = SERVICE_DIR.parent
SERVICE_ENV = SERVICE_DIR / ".env"

# 独立部署优先读取服务自己的 .env；仓库内迁移阶段兼容根目录现有配置。
if SERVICE_ENV.is_file():
    load_dotenv(SERVICE_ENV)
else:
    load_dotenv(REPO_DIR / ".env")

sys.path.insert(0, str(SERVICE_DIR))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from realtime import realtime_manager


STATIC_DIR = SERVICE_DIR / "static"
MAX_WS_MESSAGE_BYTES = int(os.getenv("AI_VOICE_MAX_WS_MESSAGE_BYTES", "131072"))

# Windows 的 MIME 注册表可能把 .js 识别成 text/plain；配合 nosniff 会导致浏览器拒绝执行。
mimetypes.add_type("application/javascript", ".js", strict=True)
mimetypes.add_type("text/css", ".css", strict=True)


def _configured() -> bool:
    value = os.getenv("ZHIPU_API_KEY", "").strip().lower()
    return bool(value) and "your_zhipu_api_key" not in value


def _frame_ancestors() -> str:
    configured = os.getenv(
        "AI_VOICE_ALLOWED_PARENT_ORIGINS",
        "http://127.0.0.1:8000 http://localhost:8000",
    )
    origins = [
        value.strip()
        for value in configured.replace(",", " ").split()
        if value.strip()
    ]
    return " ".join(origins) or "'none'"


def _websocket_origin_allowed(websocket: WebSocket) -> bool:
    """只允许同源页面或显式白名单页面使用会话 WebSocket。"""
    origin = (websocket.headers.get("origin") or "").rstrip("/")
    if not origin:
        # 非浏览器健康检查/运维客户端可能不发送 Origin。
        return True
    origin_host = urlparse(origin).netloc.lower()
    request_host = (websocket.headers.get("host") or "").lower()
    if origin_host and origin_host == request_host:
        return True
    configured = os.getenv("AI_VOICE_ALLOWED_CLIENT_ORIGINS", "")
    allowed = {
        value.strip().rstrip("/")
        for value in configured.replace(",", " ").split()
        if value.strip()
    }
    return origin in allowed


app = FastAPI(
    title="GSP AI Voice Service",
    version="1.0.0",
    description="可通过 iframe 接入的独立 GLM-Realtime 语音对话服务",
)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "media-src 'self'; "
        "connect-src 'self' ws: wss:; "
        f"frame-ancestors {_frame_ancestors()}"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


@app.get("/")
async def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "ai-voice",
        "version": 1,
        "configured": _configured(),
        "active_sessions": realtime_manager.active_count,
    }


async def _send_json(websocket: WebSocket, message: dict):
    await websocket.send_json(message)


async def _route_message(websocket: WebSocket, client_id: str, data: dict):
    message_type = data.get("type")

    async def send_to_client(message: dict):
        await _send_json(websocket, message)

    if message_type == "ai_realtime_start":
        await realtime_manager.start(
            client_id,
            send_to_client,
            audio_enabled=bool(data.get("audio", True)),
            turn_mode=data.get("mode", "realtime"),
        )
    elif message_type == "ai_realtime_audio_append":
        if not await realtime_manager.append_audio(client_id, data.get("audio")):
            await _send_json(websocket, {
                "type": "error",
                "message": "实时会话不可用，请重新开始对话",
            })
    elif message_type == "ai_realtime_audio_commit":
        if not await realtime_manager.commit_audio(client_id):
            await _send_json(websocket, {
                "type": "error",
                "message": "实时会话不可用，请重新开始对话",
            })
    elif message_type == "ai_realtime_text":
        if not await realtime_manager.send_text(client_id, data.get("text")):
            await _send_json(websocket, {
                "type": "error",
                "message": "实时会话不可用，请重新开始对话",
            })
    elif message_type == "ai_realtime_cancel":
        await realtime_manager.cancel(client_id)
    elif message_type == "ai_realtime_clear":
        await realtime_manager.close(client_id)
        await realtime_manager.start(
            client_id,
            send_to_client,
            audio_enabled=bool(data.get("audio", True)),
            turn_mode=data.get("mode", "realtime"),
        )
    else:
        await _send_json(websocket, {
            "type": "error",
            "message": f"不支持的消息类型: {message_type or '(empty)'}",
        })


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    if not _websocket_origin_allowed(websocket):
        await websocket.close(code=1008, reason="origin not allowed")
        return
    await websocket.accept()
    client_id = uuid.uuid4().hex
    try:
        while True:
            raw = await websocket.receive_text()
            if len(raw.encode("utf-8")) > MAX_WS_MESSAGE_BYTES:
                await websocket.close(code=1009, reason="message too large")
                break
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await _send_json(websocket, {
                    "type": "error",
                    "message": "消息不是有效的 JSON",
                })
                continue
            await _route_message(websocket, client_id, data)
    except WebSocketDisconnect:
        pass
    finally:
        await realtime_manager.close(client_id)


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("AI_VOICE_HOST", "0.0.0.0")
    port = int(os.getenv("AI_VOICE_PORT", "8100"))
    uvicorn.run(app, host=host, port=port)
