"""WebSocket handlers for server-relayed GLM-Realtime conversations."""
import asyncio
from typing import Any

from ai.realtime import realtime_manager
from ws.protocol import ErrorMsg


async def handle_realtime_start(manager: Any, data: dict, client_id: int):
    """Create a private upstream Realtime session for this browser client."""
    audio_enabled = bool(data.get("audio", True))
    turn_mode = data.get("mode", "realtime")

    async def send_to_client(message: dict):
        await manager.send_to_client(client_id, message)

    await realtime_manager.start(client_id, send_to_client, audio_enabled=audio_enabled, turn_mode=turn_mode)


async def handle_realtime_audio_append(manager: Any, data: dict, client_id: int):
    if not await realtime_manager.append_audio(client_id, data.get("audio")):
        await manager.send_to_client(
            client_id,
            ErrorMsg(message="实时会话不可用，请重新开始对话").model_dump(),
        )


async def handle_realtime_audio_commit(manager: Any, data: dict, client_id: int):
    if not await realtime_manager.commit_audio(client_id):
        await manager.send_to_client(
            client_id,
            ErrorMsg(message="实时会话不可用，请重新开始对话").model_dump(),
        )


async def handle_realtime_text(manager: Any, data: dict, client_id: int):
    if not await realtime_manager.send_text(client_id, data.get("text")):
        await manager.send_to_client(
            client_id,
            ErrorMsg(message="实时会话不可用，请重新开始对话").model_dump(),
        )


async def handle_realtime_cancel(manager: Any, data: dict, client_id: int):
    await realtime_manager.cancel(client_id)


async def handle_realtime_clear(manager: Any, data: dict, client_id: int):
    """Discard upstream conversation memory by creating a fresh session."""
    await realtime_manager.close(client_id)
    await handle_realtime_start(manager, data, client_id)


def _on_client_disconnect(client_id: int):
    """The connection manager has a synchronous callback interface."""
    asyncio.create_task(realtime_manager.close(client_id))


def register_ai_disconnect_handler(manager):
    manager.register_disconnect_callback(_on_client_disconnect)


def register_ai_handlers(router):
    router.register("ai_realtime_start", handle_realtime_start)
    router.register("ai_realtime_audio_append", handle_realtime_audio_append)
    router.register("ai_realtime_audio_commit", handle_realtime_audio_commit)
    router.register("ai_realtime_text", handle_realtime_text)
    router.register("ai_realtime_cancel", handle_realtime_cancel)
    router.register("ai_realtime_clear", handle_realtime_clear)
