"""
ASR (Automatic Speech Recognition) service - 智谱 GLM-ASR API integration.

Uses Zhipu GLM-ASR API to transcribe audio to text.
"""
import os
import tempfile
from typing import Optional
from zai import ZhipuAiClient
from dotenv import load_dotenv

load_dotenv()


class ASRManager:
    """
    ASR 管理器
    使用智谱 GLM-ASR API 将语音转为文字。
    """

    def __init__(self):
        self.api_key = os.getenv("ZHIPU_API_KEY", "")
        self.model = os.getenv("ZHIPU_ASR_MODEL", "glm-asr-2512")
        self._client = None
        self._ready = bool(self.api_key)
        if self._ready:
            self._client = ZhipuAiClient(api_key=self.api_key)

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
        if not self._ready or not self._client:
            print("[ASR] API Key 未配置")
            return None

        try:
            print(f"[ASR] Calling Zhipu ASR API ({len(audio_data)} bytes)...")

            # 确定文件扩展名
            ext = filename.lower().split(".")[-1] if "." in filename else "wav"

            # 写入临时文件
            with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
                tmp.write(audio_data)
                tmp_path = tmp.name

            try:
                # 使用 zai-sdk 调用 ASR
                with open(tmp_path, "rb") as audio_file:
                    response = self._client.audio.transcriptions.create(
                        model=self.model,
                        file=audio_file,
                    )

                # 解析响应 - zai-sdk 返回 Completion 对象
                text = None
                if hasattr(response, 'text'):
                    text = response.text
                elif hasattr(response, 'data') and hasattr(response.data, 'text'):
                    text = response.data.text
                elif isinstance(response, dict):
                    text = response.get("text", "") or response.get("data", {}).get("text", "")

                if text:
                    print(f"[ASR] Transcribed: {text[:60]}...")
                else:
                    print(f"[ASR] Empty result: {response}")
                return text or None

            finally:
                # 清理临时文件
                os.unlink(tmp_path)

        except Exception as e:
            print(f"[ASR] Exception: {e}")
            return None


# 全局单例
asr_manager = ASRManager()
