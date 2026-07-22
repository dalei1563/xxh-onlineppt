"""
AI Chat service - 使用智谱 GLM-4-Voice 音视频模型实现智能对话。
支持文本和语音输入，返回文本和语音输出。
"""
import asyncio
import os
import base64
import wave
import hashlib
import array
from typing import Optional, List, Dict, Any, Tuple
from zai import ZhipuAiClient
from dotenv import load_dotenv

load_dotenv()

# 音频缓存目录
AUDIO_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "audio")
os.makedirs(AUDIO_DIR, exist_ok=True)


class AIChatManager:
    """
    AI 对话管理器
    使用智谱 GLM-4-Voice 音视频模型。
    支持文本/语音输入，返回文本+语音。
    """

    def __init__(self):
        self.api_key = os.getenv("ZHIPU_API_KEY", "")
        self.model = "glm-4-voice"
        self._client = None
        self._ready = bool(self.api_key)
        if self._ready:
            self._client = ZhipuAiClient(api_key=self.api_key)
        # 系统提示词
        self.system_prompt = (
            "你是GSP学习会的AI主持助手。你的职责是：\n"
            "1. 回答关于学习会内容的问题（纪律、流程、文化等）\n"
            "2. 用热情、专业的语气与参会者互动\n"
            "3. 回答要简洁明了，控制在100字以内\n"
            "4. 适当使用emoji增加亲和力\n"
            "5. 如果不知道答案，就说需要请教现场主持人\n"
            "6. 当用户通过语音输入时，请在回复开头简短复述用户的问题（用引号括起来），然后再回答"
        )

    @property
    def is_ready(self) -> bool:
        return self._ready

    def _trim_audio_head(self, filepath: str, trim_seconds: float = 0.15):
        """裁剪音频开头的嘟嘟声"""
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
                with wave.open(filepath, 'wb') as out:
                    out.setnchannels(params.nchannels)
                    out.setsampwidth(params.sampwidth)
                    out.setframerate(params.framerate)
                    out.writeframes(trimmed.tobytes())
                print(f"[AI Chat] Trimmed {trim_seconds}s from audio head")
        except Exception as e:
            print(f"[AI Chat] Trim failed: {e}")

    def _get_cache_path(self, text: str) -> str:
        """根据文本生成缓存文件名"""
        hash_str = hashlib.md5(text.encode("utf-8")).hexdigest()
        return os.path.join(AUDIO_DIR, f"voice_{hash_str}.wav")

    def _save_audio_from_base64(self, audio_b64: str, filepath: str, trim: bool = True) -> bool:
        """保存 base64 音频为 WAV 文件，并裁剪开头嘟嘟声"""
        try:
            decoded_data = base64.b64decode(audio_b64)
            with wave.open(filepath, 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(44100)
                wav_file.writeframes(decoded_data)
            # 裁剪开头
            if trim:
                self._trim_audio_head(filepath, trim_seconds=0.15)
            return True
        except Exception as e:
            print(f"[AI Chat] Save audio error: {e}")
            return False

    def _get_base64_from_wav(self, wav_path: str) -> str:
        """将 WAV 文件转为 Base64"""
        with open(wav_path, "rb") as f:
            audio_bytes = f.read()
        return base64.b64encode(audio_bytes).decode("utf-8")

    async def chat(
        self,
        message: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Optional[str]:
        """
        文本对话，返回文本回复。
        """
        if not self._ready or not self._client:
            print("[AI Chat] API Key 未配置")
            return "AI 对话服务未配置，请联系管理员设置 API Key。"

        if not message.strip():
            return None

        # 构建消息（GLM-4-Voice 要求 content 是 list 格式）
        messages = [{"role": "system", "content": self.system_prompt}]
        if history:
            messages.extend(history[-20:])
        messages.append({
            "role": "user",
            "content": [{"type": "text", "text": message}]
        })

        try:
            print(f"[AI Chat] GLM-4-Voice text chat: {message[:50]}...")

            response = await asyncio.to_thread(
                self._client.chat.completions.create,
                model=self.model,
                messages=messages,
                stream=False,
            )

            reply = response.choices[0].message.content
            print(f"[AI Chat] Reply: {reply[:80]}...")
            return reply

        except Exception as e:
            print(f"[AI Chat] Exception: {e}")
            return f"AI 服务出现异常：{str(e)[:50]}"

    async def chat_with_voice(
        self,
        audio_b64: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        语音对话：接收语音输入，返回 (文本回复, 语音文件URL)。

        Args:
            audio_b64: base64 编码的 WAV 音频
            history: 对话历史

        Returns:
            (text_reply, audio_url) 元组
        """
        if not self._ready or not self._client:
            return "AI 对话服务未配置", None

        # 构建消息（包含语音）
        messages = [{"role": "system", "content": self.system_prompt}]
        if history:
            # 语音历史需要特殊处理，这里简化处理
            for msg in history[-10:]:
                messages.append({"role": msg["role"], "content": msg["content"]})

        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": "请回复我的语音消息"},
                {
                    "type": "input_audio",
                    "input_audio": {
                        "data": audio_b64,
                        "format": "wav"
                    }
                }
            ]
        })

        try:
            print(f"[AI Chat] GLM-4-Voice voice chat...")

            response = await asyncio.to_thread(
                self._client.chat.completions.create,
                model=self.model,
                messages=messages,
                stream=False,
            )

            # 获取文本回复
            text_reply = response.choices[0].message.content or ""

            # 获取语音回复
            audio_url = None
            try:
                audio_data = response.choices[0].message.audio
                if audio_data and audio_data.get('data'):
                    # 生成缓存路径
                    cache_path = self._get_cache_path(text_reply)
                    cache_url = f"/audio/{os.path.basename(cache_path)}"

                    if os.path.exists(cache_path):
                        audio_url = cache_url
                    elif self._save_audio_from_base64(audio_data['data'], cache_path):
                        audio_url = cache_url
                        print(f"[AI Chat] Voice saved: {cache_path}")
            except Exception as e:
                print(f"[AI Chat] Voice parse error: {e}")

            print(f"[AI Chat] Reply: {text_reply[:80]}...")
            return text_reply, audio_url

        except Exception as e:
            print(f"[AI Chat] Exception: {e}")
            return f"AI 服务出现异常：{str(e)[:50]}", None

    async def chat_with_tts(
        self,
        message: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        文本对话并生成语音。
        """
        reply = await self.chat(message, history)
        if not reply:
            return None, None

        # 用 GLM-4-Voice 生成语音
        try:
            messages = [
                {"role": "system", "content": "请用语音回复以下内容"},
                {"role": "user", "content": reply}
            ]
            response = await asyncio.to_thread(
                self._client.chat.completions.create,
                model=self.model,
                messages=messages,
                stream=False,
            )

            audio_data = response.choices[0].message.audio
            if audio_data and audio_data.get('data'):
                cache_path = self._get_cache_path(reply)
                cache_url = f"/audio/{os.path.basename(cache_path)}"
                if not os.path.exists(cache_path):
                    self._save_audio_from_base64(audio_data['data'], cache_path)
                return reply, cache_url
        except Exception as e:
            print(f"[AI Chat] TTS error: {e}")

        return reply, None


# 全局单例
ai_chat_manager = AIChatManager()
