"""Server-side relay for Zhipu GLM-Realtime sessions.

Browser clients never receive the ZHIPU_API_KEY.  Each browser WebSocket gets
one short-lived upstream Realtime session that streams PCM audio and text back
through the application's existing WebSocket channel.
"""
import asyncio
import json
import os
import time
import uuid
from typing import Any, Awaitable, Callable, Dict, Optional

import websockets


REALTIME_URL = "wss://open.bigmodel.cn/api/paas/v4/realtime"
MAX_AUDIO_CHUNK_CHARS = int(os.getenv("MAX_REALTIME_AUDIO_CHUNK_CHARS", "65536"))
SendToClient = Callable[[dict], Awaitable[None]]


def _has_real_api_key(api_key: str) -> bool:
    """Reject the placeholder copied from .env.example before opening a socket."""
    normalized = api_key.strip().lower()
    return bool(normalized) and "your_zhipu_api_key" not in normalized


def _event(event_type: str, **fields: Any) -> dict:
    return {
        "event_id": str(uuid.uuid4()),
        "client_timestamp": int(time.time() * 1000),
        "type": event_type,
        **fields,
    }


class RealtimeSession:
    """One upstream GLM-Realtime connection for one browser client."""

    def __init__(self, send_to_client: SendToClient, audio_enabled: bool = True, turn_mode: str = "realtime"):
        self._send_to_client = send_to_client
        self._audio_enabled = audio_enabled
        self._turn_mode = turn_mode if turn_mode in {"realtime", "manual"} else "realtime"
        self._api_key = os.getenv("ZHIPU_API_KEY", "")
        self._model = os.getenv("ZHIPU_REALTIME_MODEL", "glm-realtime-flash")
        self._voice = os.getenv("ZHIPU_REALTIME_VOICE", "tongtong")
        self._socket: Any = None
        self._receiver_task: Optional[asyncio.Task] = None
        self._created = asyncio.Event()
        self._closed = False
        self._send_lock = asyncio.Lock()

    @property
    def ready(self) -> bool:
        return bool(self._socket and not self._closed)

    async def start(self):
        if not _has_real_api_key(self._api_key):
            await self._status(
                "error",
                "未配置有效的 ZHIPU_API_KEY：请在 .env 中替换示例占位符后重启服务",
            )
            return False

        await self._status("connecting", "正在连接实时语音服务…")
        try:
            self._socket = await websockets.connect(
                REALTIME_URL,
                # GLM-Realtime 服务端连接使用 Bearer API Key；浏览器侧不能
                # 自定义 WebSocket 鉴权头，因此密钥只在该中继连接中使用。
                additional_headers={"Authorization": f"Bearer {self._api_key}"},
                max_size=None,
                ping_interval=20,
                ping_timeout=20,
            )
            self._receiver_task = asyncio.create_task(self._receive_loop())
            await asyncio.wait_for(self._created.wait(), timeout=10)
            await self._send_upstream(_event("session.update", session=self._session_config()))
            await self._status("ready", "实时对话已就绪，点击开始说话")
            return True
        except Exception as exc:
            await self._status("error", f"实时服务连接失败：{str(exc)[:80]}")
            await self.close()
            return False

    def _session_config(self) -> dict:
        # Audio responses expose their captions through response.audio_transcript.*.
        # Requesting only audio here keeps the browser from receiving two parallel
        # assistant transcripts (response.text and audio transcript) for one turn.
        modalities = ["audio"] if self._audio_enabled else ["text"]
        return {
            "model": self._model,
            "modalities": modalities,
            "instructions": (
                "你是 GSP 学习会的 AI 主持助手。只回答与学习会的纪律、流程、文化和"
                "现场互动有关的问题。语气热情、专业、简洁；每次回复不超过 100 个汉字。"
                "不确定时请建议向现场主持人确认。"
            ),
            "voice": self._voice,
            "input_audio_format": "pcm16",
            "output_audio_format": "pcm",
            "input_audio_noise_reduction": {"type": "far_field"},
            "turn_detection": {
                "type": "server_vad" if self._turn_mode == "realtime" else "client_vad",
                "create_response": self._turn_mode == "realtime",
                "interrupt_response": True,
            },
            "temperature": 0.4,
            "max_response_output_tokens": "256",
            "beta_fields": {"chat_mode": "audio", "tts_source": "e2e"},
        }

    async def append_audio(self, audio: Any) -> bool:
        if not isinstance(audio, str) or not audio or len(audio) > MAX_AUDIO_CHUNK_CHARS:
            await self._status("error", "音频分片无效或过大")
            return False
        if not self.ready:
            await self._status("error", "实时会话尚未准备好")
            return False
        await self._send_upstream(_event("input_audio_buffer.append", audio=audio))
        return True

    async def commit_audio(self) -> bool:
        """Finish a client-VAD turn and explicitly request one model response."""
        if not self.ready:
            await self._status("error", "实时会话尚未准备好")
            return False
        await self._send_upstream(_event("input_audio_buffer.commit"))
        await self._send_upstream(_event("response.create"))
        await self._status("thinking", "正在理解你的问题")
        return True

    async def send_text(self, text: Any) -> bool:
        if not isinstance(text, str) or not text.strip() or len(text) > 2000:
            await self._status("error", "问题不能为空且不能超过 2000 个字符")
            return False
        if not self.ready:
            await self._status("error", "实时会话尚未准备好")
            return False
        await self._send_upstream(_event(
            "conversation.item.create",
            item={
                "type": "message",
                "object": "realtime.item",
                "role": "user",
                "content": [{"type": "input_text", "text": text.strip()}],
            },
        ))
        await self._send_upstream(_event("response.create"))
        return True

    async def cancel(self):
        if self.ready:
            await self._send_upstream(_event("response.cancel"))

    async def _send_upstream(self, payload: dict):
        async with self._send_lock:
            if self._socket and not self._closed:
                await self._socket.send(json.dumps(payload, ensure_ascii=False))

    async def _receive_loop(self):
        try:
            async for raw in self._socket:
                try:
                    event = json.loads(raw)
                except (TypeError, json.JSONDecodeError):
                    continue
                await self._handle_upstream_event(event)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if not self._closed:
                await self._status("error", f"实时会话已断开：{str(exc)[:80]}")

    async def _handle_upstream_event(self, event: dict):
        event_type = event.get("type", "")
        if event_type == "session.created":
            self._created.set()
        elif event_type == "input_audio_buffer.speech_started":
            await self._status("listening", "正在聆听…")
        elif event_type == "input_audio_buffer.speech_stopped":
            await self._status("thinking", "正在思考…")
        elif event_type == "conversation.item.input_audio_transcription.completed":
            await self._send_to_client({
                "type": "ai_realtime_user_transcript",
                "text": event.get("transcript", ""),
            })
        elif event_type == "response.text.delta" and not self._audio_enabled:
            await self._send_to_client({"type": "ai_realtime_text_delta", "delta": event.get("delta", "")})
        elif event_type == "response.text.done" and not self._audio_enabled:
            await self._send_to_client({
                "type": "ai_realtime_text_done",
                "text": event.get("text", ""),
            })
        elif event_type == "response.audio_transcript.delta" and self._audio_enabled:
            await self._send_to_client({"type": "ai_realtime_text_delta", "delta": event.get("delta", "")})
        elif event_type == "response.audio_transcript.done" and self._audio_enabled:
            await self._send_to_client({"type": "ai_realtime_text_done", "text": event.get("transcript", "")})
        elif event_type == "response.audio.delta":
            await self._send_to_client({
                "type": "ai_realtime_audio_delta",
                "audio": event.get("delta", ""),
                "sample_rate": 24000,
            })
        elif event_type == "response.done":
            # A cancelled/short audio response may not include a separate *.done
            # transcript event. Finishing an empty client bubble is harmless and
            # prevents a live caption from being left in its highlighted state.
            await self._send_to_client({"type": "ai_realtime_text_done", "text": ""})
            await self._status("ready", "点击开始说话")
        elif event_type == "error":
            error = event.get("error") or {}
            await self._status("error", error.get("message", "实时服务返回错误"))

    async def _status(self, status: str, message: str):
        await self._send_to_client({"type": "ai_realtime_status", "status": status, "message": message})

    async def close(self):
        self._closed = True
        task = self._receiver_task
        if task and task is not asyncio.current_task():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        if self._socket:
            try:
                await self._socket.close()
            except Exception:
                pass
        self._socket = None


class RealtimeSessionManager:
    def __init__(self):
        self._sessions: Dict[int, RealtimeSession] = {}

    async def start(
        self,
        client_id: int,
        send_to_client: SendToClient,
        audio_enabled: bool = True,
        turn_mode: str = "realtime",
    ):
        await self.close(client_id)
        session = RealtimeSession(send_to_client, audio_enabled=audio_enabled, turn_mode=turn_mode)
        self._sessions[client_id] = session
        started = await session.start()
        if not started:
            self._sessions.pop(client_id, None)
        return started

    async def append_audio(self, client_id: int, audio: Any):
        session = self._sessions.get(client_id)
        return await session.append_audio(audio) if session else False

    async def commit_audio(self, client_id: int):
        session = self._sessions.get(client_id)
        return await session.commit_audio() if session else False

    async def send_text(self, client_id: int, text: Any):
        session = self._sessions.get(client_id)
        return await session.send_text(text) if session else False

    async def cancel(self, client_id: int):
        session = self._sessions.get(client_id)
        if session:
            await session.cancel()

    async def close(self, client_id: int):
        session = self._sessions.pop(client_id, None)
        if session:
            await session.close()


realtime_manager = RealtimeSessionManager()
