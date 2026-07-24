"""
GSP 学习会在线演示系统 - 主入口

FastAPI 服务器，提供：
- HTTP 静态文件服务（slides.html, controller.html, editor.html）
- REST API（幻灯片管理）
- WebSocket 实时通信（翻页控制、幻灯片同步、TTS 播报等）
"""
import os
import sys
import asyncio
from contextlib import suppress
from pathlib import Path

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

from db.database import init_db, SessionLocal
from services.slide_service import slide_service
from services.thumbnail_service import thumbnail_service
from state.presentation import presentation_state
from ws.handler import manager as ws_manager

# API 路由
from api import slides
from editor.templates import get_all_templates_for_ui


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # ---- startup ----
    init_db()
    print("[DB] Database initialized")

    thumbnail_task = None
    db = SessionLocal()
    try:
        slide_service.seed_slides(db)
        print("[Editor] Slides metadata seeded")

        migrated_videos = slide_service.migrate_legacy_video_slides(db)
        if migrated_videos:
            print(f"[Migration] Unified {migrated_videos} legacy video slides")

        migrated_ai_slides = slide_service.migrate_ai_chat_slides(db)
        if migrated_ai_slides:
            print(
                f"[Migration] Converted {migrated_ai_slides} embedded AI slides "
                "to external service frames"
            )

        # 初始化演示权威状态
        order = slide_service.get_slide_order(db)
        presentation_state.set_slide_order(order)
        if order:
            presentation_state.goto_slide(order[0])
        print(f"[State] Presentation state initialized: {presentation_state.total_slides} slides")

        if os.getenv("THUMBNAIL_WARMUP", "true").lower() in {"1", "true", "yes"}:
            thumbnail_slides = slide_service.get_all_slides(db)
            port = int(os.getenv("SERVER_PORT", "8000"))
            thumbnail_task = asyncio.create_task(
                thumbnail_service.warm_cache(
                    thumbnail_slides,
                    f"http://127.0.0.1:{port}",
                )
            )
    finally:
        db.close()

    print("=" * 50)
    print("GSP 学习会在线演示系统 v3")
    print("=" * 50)
    print(f"Slides:     http://localhost:8000/slides.html")
    print(f"Controller: http://localhost:8000/controller.html")
    print(f"Editor:     http://localhost:8000/editor.html")
    print(f"WebSocket:  ws://localhost:8000/ws")
    print("=" * 50)

    yield

    # ---- shutdown ----
    if thumbnail_task:
        thumbnail_task.cancel()
        with suppress(asyncio.CancelledError):
            await thumbnail_task
    print("[Server] Shutting down...")


# FastAPI 应用
app = FastAPI(
    title="GSP 学习会在线演示系统",
    version="3.0.0",
    description="线下学习会交互式演示系统，支持远程控制、在线编辑、外部服务页与语音播报",
    lifespan=lifespan,
)

# ---- 静态文件服务 ----
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)

# 挂载 /audio 用于访问生成的 TTS 音频文件
audio_dir = Path(__file__).parent / "audio"
audio_dir.mkdir(exist_ok=True)
app.mount("/audio", StaticFiles(directory=str(audio_dir)), name="audio")

# 挂载静态文件目录
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# ---- HTTP 页面路由 ----

@app.get("/")
async def index():
    """根路径重定向到演示页面"""
    return FileResponse(str(static_dir / "slides.html"))


@app.get("/slides.html")
async def slides_page():
    """主演示页面"""
    return FileResponse(str(static_dir / "slides.html"))


@app.get("/controller.html")
async def controller_page():
    """远程控制页面"""
    return FileResponse(str(static_dir / "controller.html"))


@app.get("/editor.html")
async def editor_page():
    """幻灯片编辑器页面"""
    return FileResponse(str(static_dir / "editor.html"))


@app.get("/favicon.ico")
async def favicon():
    """图标"""
    return FileResponse(str(static_dir / "favicon.ico"))


# ---- REST API 路由 ----
@app.get("/api/templates")
async def get_templates():
    """获取所有可用的幻灯片模板"""
    return get_all_templates_for_ui()

app.include_router(slides.router)


# ---- WebSocket 路由 ----

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 连接端点"""
    client_id = await ws_manager.connect(websocket)
    try:
        while True:
            message = await websocket.receive_text()
            await ws_manager.handle_message(client_id, message)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[WS] Error for client {client_id}: {e}")
    finally:
        await ws_manager.disconnect(client_id)


# ---- 直接运行 ----

if __name__ == "__main__":
    import uvicorn

    host = os.getenv("SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("SERVER_PORT", "8000"))
    # 热重载会启动父/子两个进程；活动现场应默认单进程运行，避免重启后
    # 遗留子进程继续占用 8000 端口。开发时可显式设置 SERVER_RELOAD=true。
    reload_enabled = os.getenv("SERVER_RELOAD", "false").lower() in {"1", "true", "yes"}

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=reload_enabled,
        log_level="info",
    )
