"""
Pydantic models for slide editor API.
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List


class SlideInfo(BaseModel):
    """幻灯片信息"""
    id: int
    slide_id: str
    title: str = ""
    type: str = "content"
    chapter: str = ""
    display_order: int = 0
    content_json: Dict[str, Any] = {}


class SlideReorder(BaseModel):
    """排序请求"""
    order: List[str] = Field(..., description="按新顺序排列的 slide_id 数组")


class SlideUpdate(BaseModel):
    """更新幻灯片内容"""
    title: Optional[str] = None
    content_json: Optional[Dict[str, Any]] = None
