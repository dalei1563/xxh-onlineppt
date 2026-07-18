"""WebSocket message handlers."""
from ws.handlers.slide_handler import register_slide_handlers
from ws.handlers.game_handler import register_game_handlers
from ws.handlers.tts_handler import register_tts_handlers
from ws.handlers.ai_handler import register_ai_handlers


def register_all_handlers(router):
    """向路由器注册所有消息处理函数"""
    register_slide_handlers(router)
    register_game_handlers(router)
    register_tts_handlers(router)
    register_ai_handlers(router)
