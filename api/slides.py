"""
Slides REST API - 幻灯片元数据与渲染接口。
所有变更操作都会通过 WebSocket 广播，确保各端实时同步。
"""
import os
import shutil
import uuid
from pathlib import Path
from typing import List
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from db.database import get_db
from editor.models import SlideInfo, SlideReorder, SlideUpdate, SlideCreate
from services.slide_service import slide_service
from state.presentation import presentation_state
from ws.handler import manager as ws_manager
from ws.protocol import (
    SlideCreatedMsg,
    SlideUpdatedMsg,
    SlideDeletedMsg,
    SlidesReorderedMsg,
)


router = APIRouter(prefix="/api/slides", tags=["slides"])


# ---- 集合操作路由（必须放在 /{slide_id} 之前）----

@router.get("", response_model=List[SlideInfo])
async def get_slides(db: Session = Depends(get_db)):
    """获取所有幻灯片元数据"""
    return [s.model_dump() for s in slide_service.get_all_slides(db)]


@router.get("/order")
async def get_slide_order(db: Session = Depends(get_db)):
    """获取当前幻灯片排序"""
    return slide_service.get_slide_order(db)


@router.get("/full")
async def get_full_slides(db: Session = Depends(get_db)):
    """获取全部幻灯片渲染后的 HTML"""
    html = slide_service.render_all_slides(db)
    return HTMLResponse(html)


@router.put("/reorder")
async def reorder_slides(data: SlideReorder, db: Session = Depends(get_db)):
    """保存幻灯片新排序"""
    slide_service.reorder_slides(db, data.order)
    # 更新权威状态
    presentation_state.set_slide_order(data.order)
    await ws_manager.broadcast(
        SlidesReorderedMsg(order=data.order).model_dump()
    )
    return {"message": "排序已保存", "order": data.order}


@router.post("/create")
async def create_slide(data: SlideCreate, db: Session = Depends(get_db)):
    """从模板创建新幻灯片"""
    result = slide_service.create_slide(
        db,
        slide_type=data.type,
        chapter=data.chapter,
        title=data.title,
        content_json=data.content_json,
    )
    if not result:
        raise HTTPException(status_code=400, detail=f"Unknown slide type: {data.type}")

    # 更新权威状态中的顺序
    order = slide_service.get_slide_order(db)
    presentation_state.set_slide_order(order)

    await ws_manager.broadcast(
        SlideCreatedMsg(slide=result.model_dump()).model_dump()
    )
    return result.model_dump()


@router.post("/upload")
async def upload_slide_media(
    slide_type: str = "image",
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """上传视频或图片并创建全屏素材页"""
    if slide_type not in ("image", "video"):
        raise HTTPException(status_code=400, detail="slide_type 必须是 image 或 video")

    # 校验扩展名
    ext = Path(file.filename or "").suffix.lower()
    if slide_type == "image" and ext not in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"):
        raise HTTPException(status_code=400, detail="图片仅支持 jpg/png/gif/webp/bmp")
    if slide_type == "video" and ext not in (".mp4", ".webm", ".ogg", ".mov"):
        raise HTTPException(status_code=400, detail="视频仅支持 mp4/webm/ogg/mov")

    # 保存到 static/uploads/
    upload_dir = Path(__file__).parent.parent / "static" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_id = f"{uuid.uuid4().hex}{ext}"
    file_path = upload_dir / file_id

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件保存失败: {e}")
    finally:
        file.file.close()

    asset_url = f"/static/uploads/{file_id}"
    content = {"video_src": asset_url} if slide_type == "video" else {"image_src": asset_url}

    result = slide_service.create_slide(
        db,
        slide_type=slide_type,
        title="图片页" if slide_type == "image" else "视频页",
        chapter="素材",
        content_json=content,
    )
    if not result:
        raise HTTPException(status_code=400, detail=f"无法创建 slide type: {slide_type}")

    order = slide_service.get_slide_order(db)
    presentation_state.set_slide_order(order)

    await ws_manager.broadcast(
        SlideCreatedMsg(slide=result.model_dump()).model_dump()
    )
    return result.model_dump()


# ---- 单幻灯片路由 ----

@router.get("/{slide_id}", response_model=SlideInfo)
async def get_slide(slide_id: str, db: Session = Depends(get_db)):
    """获取单个幻灯片元数据"""
    slide = slide_service.get_slide(db, slide_id)
    if not slide:
        raise HTTPException(status_code=404, detail=f"未找到幻灯片: {slide_id}")
    return slide.model_dump()


@router.get("/{slide_id}/render")
async def render_slide(slide_id: str, db: Session = Depends(get_db)):
    """渲染单个幻灯片为 HTML"""
    html = slide_service.render_slide_by_id(db, slide_id)
    if not html:
        raise HTTPException(status_code=404, detail=f"未找到幻灯片: {slide_id}")
    return HTMLResponse(html)


@router.put("/{slide_id}")
async def update_slide(slide_id: str, data: SlideUpdate, db: Session = Depends(get_db)):
    """更新幻灯片内容"""
    result = slide_service.update_slide(
        db, slide_id, title=data.title, chapter=data.chapter, content_json=data.content_json
    )
    if not result:
        raise HTTPException(status_code=404, detail=f"未找到幻灯片: {slide_id}")

    # 广播更新
    await ws_manager.broadcast(
        SlideUpdatedMsg(slide=result.model_dump()).model_dump()
    )
    return result.model_dump()


@router.delete("/{slide_id}")
async def delete_slide(slide_id: str, db: Session = Depends(get_db)):
    """删除幻灯片"""
    success = slide_service.delete_slide(db, slide_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"未找到幻灯片: {slide_id}")

    # 更新权威状态
    order = slide_service.get_slide_order(db)
    presentation_state.set_slide_order(order)

    await ws_manager.broadcast(
        SlideDeletedMsg(slide_id=slide_id).model_dump()
    )
    return {"message": "幻灯片已删除", "slide_id": slide_id}

