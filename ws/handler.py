"""
WebSocket connection manager - handles client lifecycle and message routing.
"""
import json
import asyncio
from typing import Dict, Set, Any, Optional, Callable, Awaitable
from fastapi import WebSocket

from ws.slides import handle_slide_message
from ws.game import handle_game_message
from ws.tts import handle_tts_message
from ws.ai_voice import handle_ai_voice_message


class ConnectionManager:
    """
    WebSocket 连接管理器

    负责：
    - 客户端连接/断开管理
    - 消息路由分发到各业务处理器
    - 广播消息到所有或指定客户端
    """

    def __init__(self):
        self._connections: Dict[int, WebSocket] = {}
        self.current_slide: str = "1"

    @property
    def client_count(self) -> int:
        return len(self._connections)

    @property
    def connections(self) -> Dict[int, WebSocket]:
        return self._connections

    async def connect(self, websocket: WebSocket) -> int:
        """接受新的 WebSocket 连接，返回 client_id"""
        await websocket.accept()
        client_id = id(websocket)
        self._connections[client_id] = websocket

        # 发送初始状态
        await websocket.send_json({
            "type": "state",
            "slide": self.current_slide,
            "clients": self.client_count,
        })

        # 广播客户端数量变化
        await self._broadcast_async({"type": "clients_count", "count": self.client_count})
        print(f"[WS] Client connected: {client_id} (Total: {self.client_count})")
        return client_id

    async def disconnect(self, client_id: int):
        """断开客户端连接"""
        self._connections.pop(client_id, None)
        await self._broadcast_async({"type": "clients_count", "count": self.client_count})
        print(f"[WS] Client disconnected: {client_id} (Total: {self.client_count})")

    async def handle_message(self, client_id: int, message: str):
        """接收并路由消息到对应处理器"""
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            print(f"[WS] Invalid JSON from client {client_id}")
            return

        msg_type = data.get("type", "")
        if not msg_type:
            return

        # 路由到各业务处理器
        # 幻灯片控制
        if msg_type in ("next", "prev", "first", "last", "goto", "sync", "fullscreen", "replay_video"):
            await handle_slide_message(self, data, client_id)

        # 游戏/积分
        elif msg_type in ("score_update", "score_set", "score_get", "score_leaderboard",
                          "score_reset", "game_control"):
            await handle_game_message(self, data, client_id)

        # TTS 播报
        elif msg_type in ("tts_speak", "tts_stop", "tts_request"):
            await handle_tts_message(self, data, client_id)

        # AI 语音对话（预留）
        elif msg_type.startswith("ai_voice") or msg_type in ("ai_question",):
            await handle_ai_voice_message(self, data, client_id)

        else:
            print(f"[WS] Unknown message type: {msg_type} from client {client_id}")

    # ---- 广播/发送方法 ----

    async def broadcast(self, message: dict, exclude: Optional[list] = None):
        """广播消息给所有（或排除指定）客户端"""
        if exclude is None:
            exclude = []
        disconnected = []
        for cid, ws in self._connections.items():
            if cid in exclude:
                continue
            try:
                await ws.send_json(message)
            except Exception:
                disconnected.append(cid)
        for cid in disconnected:
            self._connections.pop(cid, None)

    async def send_to_client(self, client_id: int, message: dict):
        """发送消息给指定客户端"""
        ws = self._connections.get(client_id)
        if ws:
            try:
                await ws.send_json(message)
            except Exception:
                self._connections.pop(client_id, None)

    async def _broadcast_async(self, message: dict):
        """异步广播给所有客户端（内部使用）"""
        disconnected = []
        for cid, ws in self._connections.items():
            try:
                await ws.send_json(message)
            except Exception:
                disconnected.append(cid)
        for cid in disconnected:
            self._connections.pop(cid, None)


# 全局单例
manager = ConnectionManager()
