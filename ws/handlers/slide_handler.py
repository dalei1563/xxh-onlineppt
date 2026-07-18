"""
WebSocket handler for slide control (翻页/跳转/全屏/视频重播)。
所有翻页行为都以 state/presentation.py 的权威状态为准。
"""
from typing import Any

from state.presentation import presentation_state
from ws.protocol import GotoSlideMsgOut, FullscreenMsgOut, ReplayVideoMsgOut


async def handle_next(manager: Any, data: dict, client_id: int):
    slide_id = presentation_state.next_slide()
    if slide_id:
        await manager.broadcast(GotoSlideMsgOut(slide=slide_id, source=client_id).model_dump())
        print(f"[Slide] Next -> {slide_id} (client={client_id})")


async def handle_prev(manager: Any, data: dict, client_id: int):
    slide_id = presentation_state.prev_slide()
    if slide_id:
        await manager.broadcast(GotoSlideMsgOut(slide=slide_id, source=client_id).model_dump())
        print(f"[Slide] Prev -> {slide_id} (client={client_id})")


async def handle_first(manager: Any, data: dict, client_id: int):
    slide_id = presentation_state.first_slide()
    if slide_id:
        await manager.broadcast(GotoSlideMsgOut(slide=slide_id, source=client_id).model_dump())
        print(f"[Slide] First -> {slide_id} (client={client_id})")


async def handle_last(manager: Any, data: dict, client_id: int):
    slide_id = presentation_state.last_slide()
    if slide_id:
        await manager.broadcast(GotoSlideMsgOut(slide=slide_id, source=client_id).model_dump())
        print(f"[Slide] Last -> {slide_id} (client={client_id})")


async def handle_goto(manager: Any, data: dict, client_id: int):
    slide_id = str(data.get("slide", ""))
    if presentation_state.goto_slide(slide_id):
        await manager.broadcast(GotoSlideMsgOut(slide=slide_id, source=client_id).model_dump())
        print(f"[Slide] Goto -> {slide_id} (client={client_id})")


async def handle_sync(manager: Any, data: dict, client_id: int):
    slide_id = str(data.get("slide", ""))
    presentation_state.goto_slide(slide_id)
    await manager.broadcast(
        GotoSlideMsgOut(slide=slide_id, source=client_id).model_dump(),
        exclude=[client_id],
    )
    print(f"[Slide] Sync -> {slide_id} (client={client_id})")


async def handle_fullscreen(manager: Any, data: dict, client_id: int):
    await manager.broadcast(FullscreenMsgOut(source=client_id).model_dump())
    print(f"[Slide] Toggle fullscreen (client={client_id})")


async def handle_replay_video(manager: Any, data: dict, client_id: int):
    await manager.broadcast(ReplayVideoMsgOut(source=client_id).model_dump())
    print(f"[Slide] Replay video (client={client_id})")


def register_slide_handlers(router):
    """向路由器注册所有幻灯片控制消息"""
    router.register("next", handle_next)
    router.register("prev", handle_prev)
    router.register("first", handle_first)
    router.register("last", handle_last)
    router.register("goto", handle_goto)
    router.register("sync", handle_sync)
    router.register("fullscreen", handle_fullscreen)
    router.register("replay_video", handle_replay_video)
