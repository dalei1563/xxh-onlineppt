"""
ASR (Automatic Speech Recognition) service - 智谱 API integration.

Uses Zhipu GLM-ASR API to transcribe audio to text.
"""
import os
import json
from typing import Optional
import httpx
from dotenv import load_dotenv

load_dotenv()


class ASRManager:
    """
    ASR 管理器
    使用智谱 GLM-ASR API 将语音转为文字。
    """

    def __init__(self):
        self.api_key = os.getenv("ZHIPU_API_KEY", "")
        self.api_url = "https://open.bigmodel.cn/api/paas/v4/asr"
        self.model = os.getenv("ZHIPU_ASR_MODEL", "glm-asr-2512")
        # 代理配置（仅用于调用智谱 API）
        self.proxy = os.getenv("AI_PROXY", "") or None
        self._ready = bool(self.api_key)

    @property
    def is_ready(self) -> bool:
        return self._ready

    async def transcribe(self, audio_data: bytes, filename: str = "audio.wav") -> Optional[str]:
        """
        将音频数据转为文字。

        Args:
            audio_data: 音频二进制数据
            filename: 文件名（用于 MIME 类型推断）

        Returns:
            识别出的文字，失败返回 None
        """
        if not self._ready:
            print("[ASR] API Key 未配置")
            return None

        try:
            print(f"[ASR] Calling Zhipu ASR API ({len(audio_data)} bytes)...")

            client_kwargs = {}
            if self.proxy:
                client_kwargs["proxies"] = {
                    "http://": self.proxy,
                    "https://": self.proxy,
                }

            async with httpx.AsyncClient(**client_kwargs, timeout=120.0) as client:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                }

                # 确定 MIME 类型
                ext = filename.lower().split(".")[-1] if "." in filename else "wav"
                mime_map = {
                    "wav": "audio/wav",
                    "mp3": "audio/mpeg",
                    "m4a": "audio/mp4",
                    "ogg": "audio/ogg",
                    "webm": "audio/webm",
                    "amr": "audio/amr",
                }
                mime = mime_map.get(ext, "audio/wav")

                files = {
                    "file": (filename, audio_data, mime),
                }
                data = {
                    "model": self.model,
                }

                response = await client.post(
                    self.api_url,
                    headers=headers,
                    data=data,
                    files=files,
                )

                if response.status_code == 200:
                    result = response.json()
                    text = result.get("data", {}).get("text", "")
                    if text:
                        print(f"[ASR] Transcribed: {text[:60]}...")
                    else:
                        print(f"[ASR] Empty result: {result}")
                    return text or None
                else:
                    print(f"[ASR] API error: status={response.status_code}, body={response.text[:300]}")
                    return None

        except httpx.TimeoutException:
            print("[ASR] Request timeout")
            return None
        except Exception as e:
            print(f"[ASR] Exception: {e}")
            return None


# 全局单例
asr_manager = ASRManager()
