"""
WebSocket message handler for AI voice conversation (预留接口).

!!! 注意: 此文件为骨架预留，待后续实现 AI 实时语音对话功能 !!!
"""
from typing import Any


async def handle_ai_voice_message(handler: Any, data: dict, client_id: int):
    """
    处理 AI 语音对话相关消息（预留）

    后续实现的功能：
    - ai_voice_start: 开始 AI 语音对话
    - ai_voice_stop: 结束 AI 语音对话
    - ai_voice_audio: 传输音频数据
    - ai_question: 文字提问
    - ai_answer: AI 回复
    """
    msg_type = data.get("type", "")

    if msg_type == "ai_voice_start":
        await handler.send_to_client(client_id, {
            "type": "ai_voice_status",
            "status": "not_implemented",
            "message": "AI 语音对话功能暂未接入，敬请期待",
        })

    elif msg_type == "ai_question":
        question = data.get("text", "")
        await handler.send_to_client(client_id, {
            "type": "ai_answer",
            "text": f"[AI 对话功能待接入] 您的问题是：{question}",
        })

    print(f"[AI Voice] Received unimplemented message type: {msg_type}")
