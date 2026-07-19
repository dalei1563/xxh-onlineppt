"""
Pydantic models for slide editor API.
内容以独立文件存储，DB 只存元数据。
"""
from pydantic import BaseModel, Field
from typing import Optional, List


class SlideInfo(BaseModel):
    """幻灯片信息"""
    id: int
    slide_id: str
    title: str = ""
    type: str = "content"
    chapter: str = ""
    display_order: int = 0
    file_path: str = ""


class SlideReorder(BaseModel):
    """排序请求"""
    order: List[str] = Field(..., description="按新顺序排列的 slide_id 数组")
    chapter_changes: Optional[dict[str, str]] = Field(default=None, description="slide_id → 新章节名称 的映射")


class SlideUpdate(BaseModel):
    """更新幻灯片内容"""
    title: Optional[str] = None
    chapter: Optional[str] = None


class SlideCreate(BaseModel):
    """创建幻灯片请求"""
    type: str
    chapter: Optional[str] = None
    title: Optional[str] = None


class SlideRenderResponse(BaseModel):
    """渲染单页幻灯片响应"""
    slide_id: str
    html: str
