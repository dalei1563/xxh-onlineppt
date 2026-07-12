"""
WebSocket message handler for slide control (翻页/跳转/全屏).
Keeps original behavior for backward compatibility.
"""
from typing import Any


async def handle_slide_message(handler: Any, data: dict, client_id: int):
    """处理幻灯片控制相关消息"""
    msg_type = data.get("type", "")

    if msg_type == "next":
        await handler.broadcast({"type": "next", "source": client_id})
        print(f"[Slide] Next slide (client={client_id})")

    elif msg_type == "prev":
        await handler.broadcast({"type": "prev", "source": client_id})
        print(f"[Slide] Previous slide (client={client_id})")

    elif msg_type == "first":
        handler.current_slide = "1"
        await handler.broadcast({"type": "first", "source": client_id})
        print(f"[Slide] Go to first (client={client_id})")

    elif msg_type == "last":
        handler.current_slide = "66"
        await handler.broadcast({"type": "last", "source": client_id})
        print(f"[Slide] Go to last (client={client_id})")

    elif msg_type == "goto":
        slide = data.get("slide", "1")
        handler.current_slide = slide
        await handler.broadcast({"type": "goto", "slide": slide, "source": client_id})
        print(f"[Slide] Go to slide: {slide} (client={client_id})")

    elif msg_type == "sync":
        slide = data.get("slide", handler.current_slide)
        handler.current_slide = slide
        await handler.broadcast({"type": "sync", "slide": slide, "source": client_id}, exclude=[client_id])
        print(f"[Slide] Sync slide: {slide} (client={client_id})")

    elif msg_type == "fullscreen":
        await handler.broadcast({"type": "fullscreen", "source": client_id})
        print(f"[Slide] Toggle fullscreen (client={client_id})")

    elif msg_type == "replay_video":
        await handler.broadcast({"type": "replay_video", "source": client_id})
        print(f"[Slide] Replay video (client={client_id})")
