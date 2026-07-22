"""
WebSocket handler for TTS (Text-to-Speech) messages.
"""
import asyncio
import os
from typing import Any

from ai.tts import tts_manager
from ws.protocol import TtsFileMsg, TtsBrowserMsg, TtsStopMsgOut


MAX_TTS_TEXT_LENGTH = int(os.getenv("MAX_TTS_TEXT_LENGTH", "2000"))


async def _generate_and_broadcast(manager: Any, text: str, voice: str = ""):
    """异步生成 TTS 音频并广播给所有客户端"""
    audio_url = await tts_manager.synthesize(text, voice)
    if audio_url:
        await manager.broadcast(
            TtsFileMsg(url=audio_url, text=text).model_dump()
        )
    else:
        # TTS 暂不可用（API 未配置），使用浏览器 TTS 作为降级
        await manager.broadcast(
            TtsBrowserMsg(text=text).model_dump()
        )


async def speak(manager: Any, text: str, voice: str = ""):
    """
    TTS 公共入口：触发异步生成并广播 TtsFileMsg / TtsBrowserMsg。
    供积分自动播报、AI 回复等"系统侧"调用使用，避免重复实现。
    """
    if not text:
        return
    asyncio.create_task(_generate_and_broadcast(manager, text, voice))


async def handle_tts_speak(manager: Any, data: dict, client_id: int):
    text = data.get("text", "")
    voice = data.get("voice", "")
    if not isinstance(text, str) or not text or len(text) > MAX_TTS_TEXT_LENGTH:
        return
    print(f"[TTS] Speak requested: {text[:50]}... (client={client_id})")
    await speak(manager, text, voice)


async def handle_tts_stop(manager: Any, data: dict, client_id: int):
    await manager.broadcast(TtsStopMsgOut().model_dump())
    print(f"[TTS] Stop requested (client={client_id})")


async def handle_tts_request(manager: Any, data: dict, client_id: int):
    """内部触发的 TTS 请求（如积分变化自动播报）"""
    text = data.get("text", "")
    if text:
        print(f"[TTS] Internal TTS request: {text[:50]}...")
        await speak(manager, text, "")


def register_tts_handlers(router):
    """向路由器注册所有 TTS 消息"""
    router.register("tts_speak", handle_tts_speak)
    router.register("tts_stop", handle_tts_stop)
    router.register("tts_request", handle_tts_request)
