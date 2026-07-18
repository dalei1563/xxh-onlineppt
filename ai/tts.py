"""
TTS (Text-to-Speech) service - 智谱 API integration.

Uses Zhipu GLM-TTS API to synthesize speech from text.
Supports caching and proxy configuration.
"""
import os
import hashlib
import json
from typing import Optional
import httpx
from dotenv import load_dotenv

load_dotenv()

# 音频缓存目录
AUDIO_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "audio")
os.makedirs(AUDIO_DIR, exist_ok=True)


class TTSManager:
    """
    TTS 管理器
    使用智谱 GLM-TTS API 生成语音。
    """

    def __init__(self):
        self.api_key = os.getenv("ZHIPU_API_KEY", "")
        self.api_url = "https://open.bigmodel.cn/api/paas/v4/tts"
        self.model = os.getenv("ZHIPU_TTS_MODEL", "glm-4-voice")
        # 代理配置（仅用于调用智谱 API）
        self.proxy = os.getenv("AI_PROXY", "") or None
        self._ready = bool(self.api_key)

    @property
    def is_ready(self) -> bool:
        return self._ready

    def _get_cache_path(self, text: str, voice: str = "") -> str:
        """根据文本内容生成缓存文件名"""
        key = f"{text}_{voice}"
        hash_str = hashlib.md5(key.encode("utf-8")).hexdigest()
        return os.path.join(AUDIO_DIR, f"tts_{hash_str}.mp3")

    async def synthesize(self, text: str, voice: str = "") -> Optional[str]:
        """
        合成语音，返回音频文件 URL 路径。
        如果缓存命中，直接返回缓存文件。
        """
        if not text:
            return None

        # 检查缓存
        cache_path = self._get_cache_path(text, voice)
        cache_url = f"/audio/{os.path.basename(cache_path)}"

        if os.path.exists(cache_path):
            print(f"[TTS] Cache hit: {text[:30]}...")
            return cache_url

        if not self._ready:
            print("[TTS] API Key 未配置，使用浏览器 TTS 降级")
            return None

        # 调用智谱 TTS API
        try:
            print(f"[TTS] Calling Zhipu TTS API: {text[:30]}...")

            # 构建客户端（支持代理）
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
                    "input": text,
                    "voice": voice or "",
                    "response_format": "mp3",
                }
                # 移除空 voice 字段
                if not payload["voice"]:
                    del payload["voice"]

                response = await client.post(self.api_url, json=payload, headers=headers)

                if response.status_code == 200:
                    # 保存音频文件
                    with open(cache_path, "wb") as f:
                        f.write(response.content)
                    print(f"[TTS] Audio saved: {cache_path} ({len(response.content)} bytes)")
                    return cache_url
                else:
                    print(f"[TTS] API error: status={response.status_code}, body={response.text[:200]}")
                    return None

        except Exception as e:
            print(f"[TTS] Exception: {e}")
            return None

    async def generate_score_announcement(self, team_name: str, delta: int, new_score: int) -> Optional[str]:
        """生成积分变化播报语音"""
        action = "加" if delta > 0 else "减"
        abs_delta = abs(delta)
        if abs_delta == 0:
            text = f"{team_name}当前{new_score}分"
        else:
            text = f"{team_name}{action}{abs_delta}分，当前{new_score}分"
        return await self.synthesize(text, voice="")

    async def generate_ai_voice(self, text: str) -> Optional[str]:
        """生成 AI 对话回复语音"""
        return await self.synthesize(text, voice="")


# 全局单例
tts_manager = TTSManager()
