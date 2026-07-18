"""
WebSocket handler for AI voice conversation.
文本提问 -> LLM -> TTS -> 广播文字与语音。
"""
import asyncio
from typing import Any, Dict, List

from ai.chat import ai_chat_manager
from ai.tts import tts_manager
from ws.protocol import AiVoiceStatusMsg, AiAnswerMsg, TtsFileMsg, TtsBrowserMsg


# 每个客户端的对话历史
_conversation_history: Dict[int, List[dict]] = {}


async def _generate_tts_and_broadcast(manager: Any, text: str):
    """异步生成 TTS 音频并广播"""
    if not text:
        return
    audio_url = await tts_manager.synthesize(text, voice="")
    if audio_url:
        await manager.broadcast(TtsFileMsg(url=audio_url, text=text).model_dump())
    else:
        await manager.broadcast(TtsBrowserMsg(text=text).model_dump())


async def handle_ai_question(manager: Any, data: dict, client_id: int):
    question = data.get("text", "")
    if not question:
        return

    print(f"[AI Voice] Question from client {client_id}: {question[:50]}...")

    history = _conversation_history.get(client_id, [])
    if len(history) > 30:
        history = history[-30:]

    await manager.send_to_client(
        client_id,
        AiVoiceStatusMsg(status="thinking").model_dump(),
    )

    reply = await ai_chat_manager.chat(question, history)

    if reply:
        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": reply})
        _conversation_history[client_id] = history

        asyncio.create_task(_generate_tts_and_broadcast(manager, reply))

        await manager.broadcast(
            AiAnswerMsg(text=reply, client_id=client_id).model_dump()
        )
    else:
        await manager.send_to_client(
            client_id,
            AiAnswerMsg(text="抱歉，我暂时无法回答这个问题，请稍后再试。").model_dump(),
        )


async def handle_ai_voice_audio(manager: Any, data: dict, client_id: int):
    """音频输入功能暂通过 REST 实现，WS 通道提示用户先用文字"""
    await manager.send_to_client(
        client_id,
        AiVoiceStatusMsg(
            status="error",
            message="音频输入功能正在完善中，请先使用文字输入。",
        ).model_dump(),
    )


async def handle_ai_voice_clear(manager: Any, data: dict, client_id: int):
    if client_id in _conversation_history:
        del _conversation_history[client_id]
    await manager.send_to_client(
        client_id,
        AiVoiceStatusMsg(status="cleared", message="对话历史已清除").model_dump(),
    )


async def handle_ai_voice_start(manager: Any, data: dict, client_id: int):
    await manager.send_to_client(
        client_id,
        AiVoiceStatusMsg(
            status="ready",
            message="AI 语音对话已就绪，请输入您的问题",
        ).model_dump(),
    )


def register_ai_handlers(router):
    """向路由器注册所有 AI 语音消息"""
    router.register("ai_question", handle_ai_question)
    router.register("ai_voice_audio", handle_ai_voice_audio)
    router.register("ai_voice_clear", handle_ai_voice_clear)
    router.register("ai_voice_start", handle_ai_voice_start)
