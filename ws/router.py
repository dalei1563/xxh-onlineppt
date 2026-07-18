"""
WebSocket message router - 消息类型到处理函数的注册表。
新增消息类型只需在这里注册，无需修改中央 dispatcher。
"""
from typing import Callable, Dict, Awaitable, Any
from fastapi import WebSocket

# handler 签名: async fn(websocket, data: dict, client_id: int) -> None
WsHandler = Callable[[Any, dict, int], Awaitable[None]]


class MessageRouter:
    """WebSocket 消息路由器"""

    def __init__(self):
        self._handlers: Dict[str, WsHandler] = {}

    def register(self, msg_type: str, handler: WsHandler):
        """注册消息处理函数"""
        self._handlers[msg_type] = handler

    def get_handler(self, msg_type: str) -> WsHandler:
        """获取指定类型的处理函数"""
        return self._handlers.get(msg_type)

    async def route(self, manager: Any, data: dict, client_id: int):
        """路由消息到对应处理函数"""
        msg_type = data.get("type", "")
        handler = self._handlers.get(msg_type)
        if handler:
            await handler(manager, data, client_id)
        else:
            print(f"[WS] Unknown message type: {msg_type} from client {client_id}")


# 全局路由器
ws_router = MessageRouter()
