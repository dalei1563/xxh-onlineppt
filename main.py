"""
GSP 学习会 AI 主持演示系统 - 主入口

FastAPI 服务器，提供：
- HTTP 静态文件服务（slides.html, controller.html 等）
- WebSocket 实时通信（翻页控制、游戏积分、TTS 播报等）
"""
import os
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from contextlib import asynccontextmanager
from typing import List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

from db.database import init_db, SessionLocal, get_db
from db.models import TeamScore
from game.manager import game_manager
from game.models import TeamInfo, ScoreUpdate, ScoreSet, GameControl
from ws.handler import manager as ws_manager
from editor.manager import slide_manager
from editor.models import SlideReorder, SlideUpdate
from fastapi.responses import HTMLResponse
from fastapi import Body, Request


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # ---- startup ----
    init_db()
    print("[DB] Database initialized")

    db = SessionLocal()
    try:
        game_manager.init_teams(db)
        teams = game_manager.get_all_teams(db)
        print(f"[Game] Teams initialized: {[t.team_name for t in teams]}")

        slide_manager.seed_slides(db)
        print(f"[Editor] Slides metadata seeded")
    finally:
        db.close()

    print("=" * 50)
    print("GSP 学习会 AI 主持演示系统 v2")
    print("=" * 50)
    print(f"Slides:     http://localhost:8000/slides.html")
    print(f"Controller: http://localhost:8000/controller.html")
    print(f"WebSocket:  ws://localhost:8000/ws")
    print("=" * 50)

    yield

    # ---- shutdown ----
    print("[Server] Shutting down...")


# FastAPI 应用
app = FastAPI(
    title="GSP 学习会 AI 主持演示系统",
    version="2.0.0",
    description="线下学习会交互式演示系统，支持远程控制、游戏积分、TTS 语音播报",
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


# ---- HTTP 路由 ----

@app.get("/")
async def index():
    """根路径重定向到演示页面"""
    return FileResponse(str(static_dir / "slides.html"))


@app.get("/slides.html")
async def slides():
    """主演示页面"""
    return FileResponse(str(static_dir / "slides.html"))


@app.get("/controller.html")
async def controller():
    """远程控制页面"""
    return FileResponse(str(static_dir / "controller.html"))


@app.get("/favicon.ico")
async def favicon():
    """图标"""
    return FileResponse(str(static_dir / "favicon.ico"))


@app.get("/slide-edit.html")
async def slide_edit():
    """幻灯片可视化编辑器（GrapeJS）"""
    return FileResponse(str(static_dir / "slide-edit.html"))


@app.get("/editor.html")
async def editor():
    """幻灯片编辑器页面"""
    return FileResponse(str(static_dir / "editor.html"))


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


# ---- REST API ----

@app.get("/api/teams", response_model=List[TeamInfo])
async def get_teams(db: Session = Depends(get_db)):
    """获取所有队伍及其积分"""
    return game_manager.get_all_teams(db)


@app.get("/api/leaderboard", response_model=List[TeamInfo])
async def get_leaderboard(db: Session = Depends(get_db)):
    """获取排行榜（按积分降序）"""
    return game_manager.get_leaderboard(db)


@app.post("/api/teams/score")
async def update_team_score(data: ScoreUpdate, db: Session = Depends(get_db)):
    """更新队伍积分"""
    result = game_manager.update_score(db, data.team_name, data.delta)
    if not result:
        raise HTTPException(status_code=404, detail=f"未找到队伍: {data.team_name}")
    # 通过 WS 广播积分更新
    await ws_manager.broadcast({
        "type": "score_update",
        "team_name": result.team_name,
        "score": result.score,
        "delta": data.delta,
    })
    return result


@app.post("/api/teams/score/set")
async def set_team_score(data: ScoreSet, db: Session = Depends(get_db)):
    """直接设置队伍积分"""
    result = game_manager.set_score(db, data.team_name, data.score)
    if not result:
        raise HTTPException(status_code=404, detail=f"未找到队伍: {data.team_name}")
    await ws_manager.broadcast({
        "type": "score_set",
        "team_name": result.team_name,
        "score": result.score,
    })
    return result


@app.post("/api/teams/reset")
async def reset_scores(db: Session = Depends(get_db)):
    """重置所有队伍积分"""
    game_manager.reset_all_scores(db)
    teams = game_manager.get_all_teams(db)
    await ws_manager.broadcast({
        "type": "score_reset",
        "teams": [t.model_dump() for t in teams],
    })
    return {"message": "所有积分已重置", "teams": teams}


@app.post("/api/game/control")
async def game_control(control: GameControl):
    """控制游戏环节"""
    if control.action == "start":
        game_manager.start_game(control.round_name or "")
        await ws_manager.broadcast({
            "type": "game_control",
            "action": "started",
            "round_name": control.round_name or "",
        })
        return {"message": f"游戏环节已开始: {control.round_name}"}

    elif control.action == "end":
        game_manager.end_game()
        await ws_manager.broadcast({"type": "game_control", "action": "ended"})
        return {"message": "游戏环节已结束"}

    elif control.action == "reset":
        db = SessionLocal()
        try:
            game_manager.reset_game(db)
            await ws_manager.broadcast({"type": "game_control", "action": "reset"})
            return {"message": "游戏已重置"}
        finally:
            db.close()

    raise HTTPException(status_code=400, detail=f"不支持的动作: {control.action}")


# ---- 编辑器 API ----

@app.get("/api/slides")
async def get_slides(db: Session = Depends(get_db)):
    """获取所有幻灯片元数据"""
    return [s.model_dump() for s in slide_manager.get_all_slides(db)]


@app.get("/api/slides/order")
async def get_slide_order(db: Session = Depends(get_db)):
    """获取当前幻灯片排序（slide_id 数组）"""
    return slide_manager.get_slide_order(db)


@app.put("/api/slides/reorder")
async def reorder_slides(data: SlideReorder, db: Session = Depends(get_db)):
    """保存幻灯片新排序"""
    slide_manager.reorder_slides(db, data.order)
    await ws_manager.broadcast({
        "type": "slides_reorder",
        "order": data.order,
    })
    return {"message": "排序已保存", "order": data.order}


@app.put("/api/slides/{slide_id}")
async def update_slide(slide_id: str, data: SlideUpdate, db: Session = Depends(get_db)):
    """更新单个幻灯片的内容"""
    result = slide_manager.update_slide(db, slide_id, title=data.title, content_json=data.content_json)
    if not result:
        raise HTTPException(status_code=404, detail=f"未找到幻灯片: {slide_id}")
    await ws_manager.broadcast({
        "type": "slide_updated",
        "slide_id": slide_id,
    })
    return result.model_dump()


# ---- 幻灯片预览 ----

@app.get("/api/slides/{slide_id}/preview")
async def slide_preview(slide_id: str):
    """
    返回单个幻灯片的纯 HTML 预览（无视频播放、无 WebSocket、无控制栏）
    """
    slides_path = static_dir / "slides.html"
    if not slides_path.exists():
        return HTMLResponse("<html><body><p>Slides file not found</p></body></html>")

    # 0. 检查是否有自定义 HTML
    db = SessionLocal()
    try:
        custom = slide_manager.get_custom_html(db, slide_id)
    finally:
        db.close()

    import re
    content = slides_path.read_text(encoding="utf-8")

    if custom:
        style_match = re.search(r"<style>(.*?)</style>", content, re.DOTALL)
        styles = style_match.group(1) if style_match else ""
        slide_html = custom
        video_placeholder = ""
    else:
        style_match = re.search(r"<style>(.*?)</style>", content, re.DOTALL)
        styles = style_match.group(1) if style_match else ""

        # 提取指定 slide 的 HTML
        pattern = re.compile(
            r'(<div\s+class="slide[^"]*"\s+data-slide="' + re.escape(slide_id) + r'"[^>]*>)',
            re.IGNORECASE
        )
        match = pattern.search(content)
        if not match:
            return HTMLResponse(f"<html><body><p>Slide {slide_id} not found</p></body></html>")
        start = match.start()
        depth = 0
        i = start
        while i < len(content):
            if content[i:i+6] == '</div>':
                depth -= 1
                i += 6
                if depth <= 0:
                    end = i; break
                continue
            if content[i] == '<':
                tag_end = content.find('>', i)
                if tag_end == -1: break
                tc = content[i+1:tag_end].strip()
                if tc.startswith('div') and not tc.startswith('div/') and '!--' not in tc:
                    depth += 1
                i = tag_end + 1
            else:
                i += 1
        else:
            end = len(content)
        slide_html = content[start:end]

        is_video = slide_id == "1"
        video_placeholder = ""
        if is_video:
            video_placeholder = ".slide-01 video { display: none !important; } .slide-01::after { content: '🎬 视频页'; position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); font-size: 60px; opacity: 0.3; }"

    # 4. 组装预览 HTML
    preview_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
{styles}
body {{ margin: 0; overflow: hidden; background: #000; }}
.slide {{
    width: 1920px; height: 1080px;
    transform-origin: top left;
    display: flex !important;
    position: relative;
}}
html {{
    --scale: min(var(--vw, 1vw), var(--vh, 1vh));
}}
{video_placeholder}
</style>
<script>
// 缩放适配视口
function fitSlide() {{
    var w = window.innerWidth;
    var h = window.innerHeight;
    var scale = Math.min(w / 1920, h / 1080);
    document.querySelector('.slide').style.transform = 'scale(' + scale + ')';
    document.querySelector('.slide').style.transformOrigin = 'top left';
}}
window.addEventListener('resize', fitSlide);
window.addEventListener('load', fitSlide);
</script>
</head>
<body>
{slide_html}
</body>
</html>"""
    return HTMLResponse(preview_html)


# ---- 幻灯片 HTML 编辑 API ----

@app.get("/api/slides/{slide_id}/html")
async def get_slide_html(slide_id: str, db: Session = Depends(get_db)):
    """
    获取幻灯片的可编辑 HTML 内容。
    优先返回自定义编辑后的 HTML，否则返回 slides.html 中的原始内容。
    """
    # 1. 检查是否有自定义 HTML
    custom = slide_manager.get_custom_html(db, slide_id)
    if custom:
        return HTMLResponse(custom)

    # 2. 否则从 slides.html 提取
    slides_path = static_dir / "slides.html"
    if not slides_path.exists():
        raise HTTPException(status_code=404)

    import re
    content = slides_path.read_text(encoding="utf-8")
    pattern = re.compile(
        r'<div\s+class="slide[^"]*"\s+data-slide="' + re.escape(slide_id) + r'"[^>]*>',
        re.IGNORECASE
    )
    match = pattern.search(content)
    if not match:
        raise HTTPException(status_code=404, detail=f"Slide {slide_id} not found")

    start = match.start()
    # 匹配嵌套 div
    depth = 0
    i = start
    while i < len(content):
        if content[i:i+6] == '</div>':
            depth -= 1
            i += 6
            if depth <= 0:
                break
            continue
        if content[i] == '<':
            tag_end = content.find('>', i)
            if tag_end == -1:
                break
            tag_content = content[i+1:tag_end].strip()
            if tag_content.startswith('div') and not tag_content.startswith('div/') and '!--' not in tag_content:
                depth += 1
            i = tag_end + 1
        else:
            i += 1
    else:
        i = len(content)

    slide_html = content[start:i]
    return HTMLResponse(slide_html)


@app.put("/api/slides/{slide_id}/html")
async def save_slide_html(slide_id: str, request: Request, db: Session = Depends(get_db)):
    """保存自定义编辑后的 HTML 内容"""
    body = await request.body()
    # 尝试 UTF-8，失败则用 GBK（Windows 默认编码）
    try:
        html_content = body.decode("utf-8")
    except UnicodeDecodeError:
        html_content = body.decode("gbk")
    success = slide_manager.set_custom_html(db, slide_id, html_content)
    if not success:
        raise HTTPException(status_code=404, detail=f"Slide {slide_id} not found")
    return {"message": "HTML saved", "slide_id": slide_id, "size": len(html_content)}


# ---- 直接运行 ----

if __name__ == "__main__":
    import uvicorn

    host = os.getenv("SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("SERVER_PORT", "8000"))

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=True,
        log_level="info",
    )
