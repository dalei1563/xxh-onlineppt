"""
WebSocket message handler for TTS (Text-to-Speech) messages.
"""
import asyncio
from typing import Any
from ai.tts import tts_manager


async def handle_tts_message(handler: Any, data: dict, client_id: int):
    """处理 TTS 语音播报相关消息"""
    msg_type = data.get("type", "")

    if msg_type == "tts_speak":
        """手动触发 TTS 播报"""
        text = data.get("text", "")
        voice = data.get("voice", "")

        if not text:
            return

        print(f"[TTS] Speak requested: {text[:50]}... (client={client_id})")

        # 异步生成语音（不阻塞当前消息处理）
        asyncio.create_task(_generate_and_broadcast(handler, text, voice))

    elif msg_type == "tts_stop":
        """停止 TTS 播报"""
        await handler.broadcast({"type": "tts_stop"})
        print(f"[TTS] Stop requested (client={client_id})")

    elif msg_type == "tts_request":
        """内部触发的 TTS 请求（如积分变化自动播报）"""
        text = data.get("text", "")
        if text:
            print(f"[TTS] Internal TTS request: {text[:50]}...")
            asyncio.create_task(_generate_and_broadcast(handler, text, ""))


async def _generate_and_broadcast(handler: Any, text: str, voice: str = ""):
    """异步生成 TTS 音频并广播给所有客户端"""
    audio_url = await tts_manager.synthesize(text, voice)
    if audio_url:
        await handler.broadcast({
            "type": "tts_file",
            "url": audio_url,
            "text": text,
        })
    else:
        # TTS 暂不可用（API 未配置），使用客户端浏览器 TTS 作为降级
        await handler.broadcast({
            "type": "tts_browser",
            "text": text,
        })
