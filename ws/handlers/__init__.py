"""WebSocket message handlers."""
from ws.handlers.slide_handler import register_slide_handlers
from ws.handlers.tts_handler import register_tts_handlers


def register_all_handlers(router):
    """向路由器注册所有消息处理函数"""
    register_slide_handlers(router)
    register_tts_handlers(router)


def register_all_disconnect_handlers(manager):
    """注册需要在连接断开时清理状态的核心领域。"""
