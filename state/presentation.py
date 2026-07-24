"""
Presentation state - 演示运行时权威状态。
维护当前页码、幻灯片顺序等所有客户端共享的运行时信息。
"""
from typing import List, Optional


class PresentationState:
    """演示权威状态"""

    def __init__(self):
        self._slide_order: List[str] = []
        self._current_slide_id: str = "1"

    # ---- 幻灯片顺序 ----

    @property
    def slide_order(self) -> List[str]:
        return self._slide_order.copy()

    def set_slide_order(self, order: List[str]):
        self._slide_order = list(order)
        # 如果当前页不在新顺序中，回到第一页
        if self._current_slide_id not in self._slide_order:
            self._current_slide_id = self._slide_order[0] if self._slide_order else ""

    # ---- 当前幻灯片 ----

    @property
    def current_slide_id(self) -> str:
        return self._current_slide_id

    @property
    def total_slides(self) -> int:
        return len(self._slide_order)

    @property
    def current_position(self) -> int:
        """当前页在顺序中的位置（从 1 开始）"""
        try:
            return self._slide_order.index(self._current_slide_id) + 1
        except ValueError:
            return 1

    def goto_slide(self, slide_id: str) -> bool:
        """跳转到指定 slide_id"""
        if slide_id in self._slide_order:
            self._current_slide_id = slide_id
            return True
        return False

    def next_slide(self) -> Optional[str]:
        """下一页，返回新的 slide_id"""
        if not self._slide_order:
            return None
        try:
            idx = self._slide_order.index(self._current_slide_id)
        except ValueError:
            idx = -1
        if idx < len(self._slide_order) - 1:
            self._current_slide_id = self._slide_order[idx + 1]
        return self._current_slide_id

    def prev_slide(self) -> Optional[str]:
        """上一页，返回新的 slide_id"""
        if not self._slide_order:
            return None
        try:
            idx = self._slide_order.index(self._current_slide_id)
        except ValueError:
            idx = 1
        if idx > 0:
            self._current_slide_id = self._slide_order[idx - 1]
        return self._current_slide_id

    def first_slide(self) -> Optional[str]:
        """第一页"""
        if self._slide_order:
            self._current_slide_id = self._slide_order[0]
        return self._current_slide_id

    def last_slide(self) -> Optional[str]:
        """最后一页"""
        if self._slide_order:
            self._current_slide_id = self._slide_order[-1]
        return self._current_slide_id

    # ---- 序列化 ----

    def to_dict(self) -> dict:
        return {
            "current_slide_id": self._current_slide_id,
            "slide_order": self._slide_order,
            "total": self.total_slides,
            "current_position": self.current_position,
        }


# 全局单例
presentation_state = PresentationState()
