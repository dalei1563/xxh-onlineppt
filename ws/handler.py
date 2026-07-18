"""
WebSocket connection manager - handles client lifecycle and message routing.
"""
import json
from typing import Dict, Set, Any, Optional
from fastapi import WebSocket

from state.presentation import presentation_state
from ws.router import ws_router
from ws.handlers import register_all_handlers
from ws.protocol import PresentationStateMsg, ClientsCountMsg


# 注册所有消息处理器
register_all_handlers(ws_router)


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

        # 发送初始演示状态
        await websocket.send_json(
            PresentationStateMsg(
                current_slide_id=presentation_state.current_slide_id,
                slide_order=presentation_state.slide_order,
                total=presentation_state.total_slides,
                current_position=presentation_state.current_position,
                is_game_active=presentation_state.is_game_active,
                current_round=presentation_state.current_round,
            ).model_dump()
        )

        # 广播客户端数量变化
        await self.broadcast(
            ClientsCountMsg(count=self.client_count).model_dump()
        )
        print(f"[WS] Client connected: {client_id} (Total: {self.client_count})")
        return client_id

    async def disconnect(self, client_id: int):
        """断开客户端连接"""
        self._connections.pop(client_id, None)
        await self.broadcast(
            ClientsCountMsg(count=self.client_count).model_dump()
        )
        print(f"[WS] Client disconnected: {client_id} (Total: {self.client_count})")

    async def handle_message(self, client_id: int, message: str):
        """接收并路由消息到对应处理器"""
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            print(f"[WS] Invalid JSON from client {client_id}")
            return

        if not data.get("type"):
            return

        await ws_router.route(self, data, client_id)

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


# 全局单例
manager = ConnectionManager()
