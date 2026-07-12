"""
TTS (Text-to-Speech) service - 智谱 API integration.

!!! 注意: 这是智谱 TTS 的骨架代码，需要在获取到 API 文档后完善 !!!
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
    当前为骨架实现，待接入智谱 TTS API 后完善。
    """

    def __init__(self):
        self.api_key = os.getenv("ZHIPU_API_KEY", "")
        self.api_url = "https://open.bigmodel.cn/api/paas/v4/tts"  # 占位 URL，需要根据文档调整
        self.model = os.getenv("ZHIPU_TTS_MODEL", "glm-4-voice")
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

        待实现：调用智谱 TTS API 生成语音
        """
        # 检查缓存
        cache_path = self._get_cache_path(text, voice)
        cache_url = f"/audio/{os.path.basename(cache_path)}"

        if os.path.exists(cache_path):
            return cache_url

        if not self._ready:
            print("[TTS] API Key 未配置，无法生成语音")
            return None

        # TODO: 根据智谱 TTS API 文档实现
        # 参考结构：
        # async with httpx.AsyncClient() as client:
        #     headers = {
        #         "Authorization": f"Bearer {self.api_key}",
        #         "Content-Type": "application/json",
        #     }
        #     payload = {
        #         "model": self.model,
        #         "input": text,
        #         "voice": voice or "default",
        #         "response_format": "mp3",
        #     }
        #     response = await client.post(self.api_url, json=payload, headers=headers)
        #     if response.status_code == 200:
        #         with open(cache_path, "wb") as f:
        #             f.write(response.content)
        #         return cache_url

        print(f"[TTS] 待接入智谱 API - 文本: {text[:30]}...")
        return None

    async def generate_score_announcement(self, team_name: str, delta: int, new_score: int) -> Optional[str]:
        """生成积分变化播报语音"""
        action = "加" if delta > 0 else "减"
        abs_delta = abs(delta)
        text = f"{team_name}{action}{abs_delta}分，当前{team_name}{new_score}分"
        return await self.synthesize(text, voice="announcement")


# 全局单例
tts_manager = TTSManager()
