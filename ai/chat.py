"""
AI Chat service - 使用智谱 GLM-4.7 API 实现智能对话。
支持对话历史管理、TTS 语音播报输出。
"""
import os
import json
from typing import Optional, List, Dict, Any
import httpx
from dotenv import load_dotenv

load_dotenv()


class AIChatManager:
    """
    AI 对话管理器
    使用智谱 GLM-4.7 聊天补全 API。
    """

    def __init__(self):
        self.api_key = os.getenv("ZHIPU_API_KEY", "")
        self.api_url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
        self.model = os.getenv("ZHIPU_LLM_MODEL", "glm-4-7b")
        # 代理配置（仅用于调用智谱 API）
        self.proxy = os.getenv("AI_PROXY", "") or None
        self._ready = bool(self.api_key)
        # 系统提示词 - 学习会 AI 主持
        self.system_prompt = (
            "你是GSP学习会的AI主持助手。你的职责是：\n"
            "1. 回答关于学习会内容的问题（纪律、流程、文化等）\n"
            "2. 用热情、专业的语气与参会者互动\n"
            "3. 回答要简洁明了，控制在100字以内\n"
            "4. 适当使用emoji增加亲和力\n"
            "5. 如果不知道答案，就说需要请教现场主持人"
        )

    @property
    def is_ready(self) -> bool:
        return self._ready

    async def chat(
        self,
        message: str,
        history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None,
    ) -> Optional[str]:
        """
        发送对话消息，获取 AI 回复。

        Args:
            message: 用户消息
            history: 对话历史 [{"role": "user"/"assistant", "content": "..."}]
            system_prompt: 可选的系统提示词，覆盖默认值

        Returns:
            AI 回复文本，失败返回 None
        """
        if not self._ready:
            print("[AI Chat] API Key 未配置")
            return "AI 对话服务未配置，请联系管理员设置 API Key。"

        if not message.strip():
            return None

        # 构建消息列表
        messages = []
        if system_prompt or self.system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt or self.system_prompt,
            })

        # 添加历史消息（最多保留最近 10 轮）
        if history:
            messages.extend(history[-20:])

        # 添加当前消息
        messages.append({"role": "user", "content": message})

        try:
            print(f"[AI Chat] Sending to Zhipu API: {message[:50]}...")

            client_kwargs = {}
            if self.proxy:
                client_kwargs["proxies"] = {
                    "http://": self.proxy,
                    "https://": self.proxy,
                }

            async with httpx.AsyncClient(**client_kwargs, timeout=60.0) as client:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "model": self.model,
                    "messages": messages,
                    "temperature": 0.8,
                    "max_tokens": 500,
                    "top_p": 0.9,
                }

                response = await client.post(
                    self.api_url,
                    json=payload,
                    headers=headers,
                )

                if response.status_code == 200:
                    result = response.json()
                    reply = result["choices"][0]["message"]["content"]
                    print(f"[AI Chat] Reply: {reply[:80]}...")
                    return reply
                else:
                    print(f"[AI Chat] API error: status={response.status_code}, body={response.text[:200]}")
                    return f"AI 服务暂时繁忙（错误码：{response.status_code}），请稍后再试。"

        except httpx.TimeoutException:
            print("[AI Chat] Request timeout")
            return "AI 服务响应超时，请检查网络连接后重试。"
        except Exception as e:
            print(f"[AI Chat] Exception: {e}")
            return f"AI 服务出现异常：{str(e)[:50]}"

    async def chat_with_tts(
        self,
        message: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Optional[tuple]:
        """
        发送消息并同时生成 TTS 语音。
        返回 (text_reply, tts_url) 元组。
        """
        from ai.tts import tts_manager

        reply = await self.chat(message, history)
        if not reply:
            return None, None

        # 异步生成 TTS 语音
        tts_url = await tts_manager.synthesize(reply, voice="")
        return reply, tts_url

    async def summarize(self, content: str) -> str:
        """生成总结"""
        return await self.chat(
            f"请对以下内容进行简要总结（50字以内）：\n\n{content}",
            system_prompt="你是一个总结助手，请简洁有力地概括核心内容。",
        )


# 全局单例
ai_chat_manager = AIChatManager()
