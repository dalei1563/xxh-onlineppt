"""
TTS (Text-to-Speech) service - 智谱 GLM-TTS API integration.

Uses Zhipu GLM-TTS API to synthesize speech from text.
Supports caching and proxy configuration.
"""
import asyncio
import os
import hashlib
import wave
import array
from typing import Optional
from zai import ZhipuAiClient
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
        self.model = os.getenv("ZHIPU_TTS_MODEL", "glm-tts")
        self._client = None
        self._ready = bool(self.api_key)
        if self._ready:
            self._client = ZhipuAiClient(api_key=self.api_key)

    @property
    def is_ready(self) -> bool:
        return self._ready

    def _trim_audio_head(self, filepath: str, trim_seconds: float = 0.15):
        """裁剪音频开头的静音/异常部分"""
        try:
            with wave.open(filepath, 'rb') as wav:
                params = wav.getparams()
                skip_samples = int(params.framerate * trim_seconds)

                if skip_samples <= 0:
                    return

                all_frames = wav.readframes(params.nframes)
                samples = array.array('h', all_frames)

                if skip_samples >= len(samples):
                    return

                trimmed = samples[skip_samples:]

                # 保存裁剪后的音频
                with wave.open(filepath, 'wb') as out:
                    out.setnchannels(params.nchannels)
                    out.setsampwidth(params.sampwidth)
                    out.setframerate(params.framerate)
                    out.writeframes(trimmed.tobytes())

                print(f"[TTS] Trimmed {trim_seconds}s from audio head")
        except Exception as e:
            print(f"[TTS] Trim failed: {e}")

    def _get_cache_path(self, text: str, voice: str = "") -> str:
        """根据文本内容生成缓存文件名"""
        key = f"{text}_{voice}"
        hash_str = hashlib.md5(key.encode("utf-8")).hexdigest()
        return os.path.join(AUDIO_DIR, f"tts_{hash_str}.wav")

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

        if not self._ready or not self._client:
            print("[TTS] API Key 未配置，使用浏览器 TTS 降级")
            return None

        # 调用智谱 TTS API
        try:
            print(f"[TTS] Calling Zhipu TTS API: {text[:30]}...")

            response = await asyncio.to_thread(
                self._client.audio.speech,
                model=self.model,
                input=text,
                voice=voice or "female",
                response_format="wav",
                speed=1.0,
                volume=1.0,
            )

            # 保存音频文件
            await asyncio.to_thread(response.stream_to_file, cache_path)

            # 裁剪开头 0.15 秒（消除嘟嘟声）
            await asyncio.to_thread(self._trim_audio_head, cache_path, trim_seconds=0.15)

            print(f"[TTS] Audio saved: {cache_path}")
            return cache_url

        except Exception as e:
            print(f"[TTS] Exception: {e}")
            return None

# 全局单例
tts_manager = TTSManager()
