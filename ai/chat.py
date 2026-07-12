"""
AI Chat service - 预留接口，用于后续 AI 语音对话/答疑/总结功能。

!!! 注意: 此文件为骨架预留，待后续实现 !!!
"""


class AIChatManager:
    """
    AI 对话管理器（预留）
    
    后续计划接入的功能：
    1. 实时语音对话（WebRTC 或 WebSocket Audio）
    2. AI 知识问答（基于学习会内容）
    3. AI 总结发言
    """

    def __init__(self):
        self._ready = False

    @property
    def is_ready(self) -> bool:
        return self._ready

    async def initialize(self):
        """初始化 AI 服务（后续实现）"""
        pass

    async def chat(self, message: str, context: dict = None) -> str:
        """发送对话消息，获取回复（后续实现）"""
        return "[AI 对话功能待接入]"

    async def summarize(self, content: str) -> str:
        """生成总结（后续实现）"""
        return "[AI 总结功能待接入]"


# 全局单例
ai_chat_manager = AIChatManager()
