"""
Slides REST API - 幻灯片元数据与内容接口。
内容以独立文件存储，REST 负责元数据 CRUD 和文件读取。
"""
import os
import re
import uuid
from pathlib import Path
from typing import List
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from db.database import get_db
from editor.models import SlideInfo, SlideReorder, SlideUpdate, SlideCreate
from db.models import SlideMeta
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

UPLOADS_DIR = Path(__file__).parent.parent / "static" / "uploads"
MAX_UPLOAD_SIZE_BYTES = int(os.getenv("MAX_UPLOAD_SIZE_BYTES", 100 * 1024 * 1024))
UPLOAD_CHUNK_SIZE = 1024 * 1024


# ---- 集合路由 ----

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
    html = slide_service.get_all_slides_html(db)
    return HTMLResponse(html)


@router.put("/reorder")
async def reorder_slides(data: SlideReorder, db: Session = Depends(get_db)):
    """保存幻灯片新排序，可选同步更新章节归属"""
    current_order = slide_service.get_slide_order(db)
    requested_order = data.order
    # 排序必须是当前全部幻灯片的一次完整排列。否则重复或遗漏的 ID 会让
    # DB、服务端状态和各客户端的顺序发生不可恢复的分歧。
    if (
        len(requested_order) != len(current_order)
        or len(set(requested_order)) != len(requested_order)
        or set(requested_order) != set(current_order)
    ):
        raise HTTPException(
            status_code=422,
            detail="排序必须包含每张现有幻灯片一次且仅一次",
        )
    if data.chapter_changes and not set(data.chapter_changes).issubset(set(current_order)):
        raise HTTPException(status_code=422, detail="章节变更包含不存在的幻灯片")

    slide_service.reorder_slides(db, requested_order)
    # 处理跨章节拖拽的章节变更
    updated_slides = []
    if data.chapter_changes:
        for slide_id, new_chapter in data.chapter_changes.items():
            slide = db.query(SlideMeta).filter(SlideMeta.slide_id == slide_id).first()
            if slide:
                slide.chapter = new_chapter
                updated_slides.append(slide)
        db.commit()
    presentation_state.set_slide_order(requested_order)
    await ws_manager.broadcast(
        SlidesReorderedMsg(order=requested_order).model_dump()
    )
    # 广播章节变更
    for s in updated_slides:
        info = slide_service._to_info(s)
        await ws_manager.broadcast(
            SlideUpdatedMsg(slide=info.model_dump()).model_dump()
        )
    return {"message": "排序已保存", "order": requested_order}


@router.post("/create")
async def create_slide(data: SlideCreate, db: Session = Depends(get_db)):
    """从模板创建新幻灯片（仅创建元数据和空 HTML 文件）"""
    from editor.templates import render_slide, TEMPLATES

    tmpl = TEMPLATES.get(data.type)
    if not tmpl:
        raise HTTPException(status_code=400, detail=f"Unknown slide type: {data.type}")

    # 渲染初始 HTML
    html_content = render_slide(data.type, {}, "{SLIDE_ID}")

    result = slide_service.create_slide(
        db,
        slide_type=data.type,
        chapter=data.chapter,
        title=data.title,
        html_content=html_content,
    )
    if not result:
        raise HTTPException(status_code=400, detail=f"Cannot create slide type: {data.type}")

    order = slide_service.get_slide_order(db)
    presentation_state.set_slide_order(order)

    await ws_manager.broadcast(
        SlideCreatedMsg(slide=result.model_dump()).model_dump()
    )
    return result.model_dump()


@router.post("/upload")
async def upload_slide_media(
    slide_type: str = Form("image"),
    chapter: str = Form("素材"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """上传视频或图片并创建全屏素材页"""
    if slide_type not in ("image", "video"):
        raise HTTPException(status_code=400, detail="slide_type 必须是 image 或 video")

    ext = Path(file.filename or "").suffix.lower()
    if slide_type == "image" and ext not in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"):
        raise HTTPException(status_code=400, detail="图片仅支持 jpg/png/gif/webp/bmp")
    if slide_type == "video" and ext not in (".mp4", ".webm", ".ogg", ".mov"):
        raise HTTPException(status_code=400, detail="视频仅支持 mp4/webm/ogg/mov")

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    file_id = f"{uuid.uuid4().hex}{ext}"
    file_path = UPLOADS_DIR / file_id

    try:
        with open(file_path, "wb") as buffer:
            size = 0
            while chunk := await file.read(UPLOAD_CHUNK_SIZE):
                size += len(chunk)
                if size > MAX_UPLOAD_SIZE_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"文件不能超过 {MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)} MB",
                    )
                buffer.write(chunk)
    except HTTPException:
        if file_path.exists():
            file_path.unlink()
        raise
    except Exception as e:
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=500, detail=f"文件保存失败: {e}")
    finally:
        file.file.close()

    asset_url = f"/static/uploads/{file_id}"

    try:
        result = slide_service.create_slide(
            db,
            slide_type=slide_type,
            title="图片页" if slide_type == "image" else "视频页",
            chapter=chapter,
            file_src=asset_url,
        )
    except Exception:
        if file_path.exists():
            file_path.unlink()
        raise
    if not result:
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=400, detail=f"无法创建 slide type: {slide_type}")

    order = slide_service.get_slide_order(db)
    presentation_state.set_slide_order(order)

    await ws_manager.broadcast(
        SlideCreatedMsg(slide=result.model_dump()).model_dump()
    )
    return result.model_dump()


# ---- 章节管理路由 ----

@router.post("/chapter/create")
async def create_chapter(chapter: str = "新章节", db: Session = Depends(get_db)):
    """新建一个章节（创建一个空白占位幻灯片）"""
    from editor.templates import render_slide
    html_content = render_slide("white", {
        "title": chapter,
        "body": "在此添加内容"
    }, "{NEW}")
    result = slide_service.create_slide(
        db, slide_type="white", chapter=chapter, title=chapter,
        html_content=html_content,
    )
    if not result:
        raise HTTPException(status_code=400, detail="创建章节失败")
    order = slide_service.get_slide_order(db)
    presentation_state.set_slide_order(order)
    await ws_manager.broadcast(SlideCreatedMsg(slide=result.model_dump()).model_dump())
    return result.model_dump()


@router.put("/chapter/rename")
async def rename_chapter(old_name: str, new_name: str, db: Session = Depends(get_db)):
    """重命名章节（更新该章节下所有幻灯片的 chapter 字段）"""
    if not old_name or not new_name:
        raise HTTPException(status_code=400, detail="参数不能为空")
    from db.models import SlideMeta
    slides = db.query(SlideMeta).filter(SlideMeta.chapter == old_name).all()
    if not slides:
        raise HTTPException(status_code=404, detail=f"未找到章节: {old_name}")
    for s in slides:
        s.chapter = new_name
    db.commit()
    # 广播所有幻灯片更新
    for s in slides:
        info = slide_service._to_info(s)
        await ws_manager.broadcast(SlideUpdatedMsg(slide=info.model_dump()).model_dump())
    return {"message": f"章节已重命名: {old_name} → {new_name}", "count": len(slides)}


@router.delete("/chapter/{chapter_name:path}")
async def delete_chapter(chapter_name: str, db: Session = Depends(get_db)):
    """删除整个章节及其所有幻灯片"""
    from db.models import SlideMeta
    slides = db.query(SlideMeta).filter(SlideMeta.chapter == chapter_name).order_by(SlideMeta.display_order).all()
    if not slides:
        raise HTTPException(status_code=404, detail=f"未找到章节: {chapter_name}")
    
    slide_ids = [s.slide_id for s in slides]
    
    # 删除文件
    for s in slides:
        if s.file_path:
            fp = Path(__file__).parent.parent / "static" / s.file_path
            if fp.exists():
                fp.unlink()
    
    # 删除数据库记录
    for s in slides:
        db.delete(s)
    db.commit()
    
    # 整理顺序
    slide_service._renumber_order(db)
    
    # 更新演示状态
    order = slide_service.get_slide_order(db)
    presentation_state.set_slide_order(order)
    
    # 广播每个删除
    for sid in slide_ids:
        await ws_manager.broadcast(SlideDeletedMsg(slide_id=sid).model_dump())
    
    return {"message": f"章节已删除: {chapter_name}", "deleted": len(slide_ids)}


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
    """读取单个幻灯片的 HTML 片段（不含 doctype/head，用于内联嵌入）"""
    html = slide_service.get_slide_html_by_id(db, slide_id)
    if not html:
        raise HTTPException(status_code=404, detail=f"未找到幻灯片: {slide_id}")
    return HTMLResponse(html)


@router.get("/{slide_id}/page")
async def render_slide_page(slide_id: str, db: Session = Depends(get_db)):
    """
    返回可独立 iframe 嵌入的完整 HTML 文档：
    - 包含 doctype/head/body，引入 slides.css
    - 给根 div 自动补 active class（slides.css 中 .slide { display:none }，需 .active 才显示）
    - 内嵌 postMessage 桥接脚本，用于演示页外层控制视频 mute/play/replay
    """
    html = slide_service.get_slide_html_by_id(db, slide_id)
    if not html:
        raise HTTPException(status_code=404, detail=f"未找到幻灯片: {slide_id}")

    # 检测幻灯片类型，添加相应的 CSS
    extra_css = ""
    if "template-ai-chat" in html:
        extra_css = '<link rel="stylesheet" href="/static/css/ai-chat.css">'
    # 给根 div 的 class 加上 active（若已存在则不重复）
    # slides.css 中 .slide { display:none }、.slide.active { display:flex }
    slide_fragment = re.sub(
        r'<div class="slide([^"]*)"',
        lambda mo: '<div class="slide' + mo.group(1) + (
            '' if 'active' in mo.group(1) else ' active'
        ) + '"',
        html,
        count=1,
    )
    document = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="stylesheet" href="/static/css/slides.css">
{extra_css}
</head>
<body class="presentation">
{slide_fragment}
<script>
(function() {{
  'use strict';
  // ---- 外层 → iframe 控制桥接 ----
  window.addEventListener('message', function(ev) {{
    var msg = ev.data || {{}};
    var videos = document.querySelectorAll('video');
    if (msg.type === 'unmute') {{
      videos.forEach(function(v) {{ v.muted = false; v.play().catch(function(){{}}); }});
    }} else if (msg.type === 'replay_video') {{
      videos.forEach(function(v) {{ v.currentTime = 0; v.play().catch(function(){{}}); }});
    }} else if (msg.type === 'pause') {{
      videos.forEach(function(v) {{ v.pause(); }});
    }} else if (msg.type === 'probe') {{
      // 外层连上后询问当前 frame 是否含视频，用于 unmute-overlay 显隐
      ev.source.postMessage({{
        type: 'state',
        hasVideo: !!document.querySelector('.slide video'),
        slide: (document.querySelector('.slide') || {{}}).dataset ? document.querySelector('.slide').dataset.slide : null
      }}, ev.origin);
    }}
  }});
  // ---- iframe → 外层 视频结束通知 ----
  document.addEventListener('ended', function(e) {{
    if (e.target && e.target.tagName === 'VIDEO') {{
      parent.postMessage({{ type: 'video_ended' }}, '*');
    }}
  }}, true);
}})();
</script>
</body>
</html>"""
    return HTMLResponse(document)


@router.put("/{slide_id}")
async def update_slide(slide_id: str, data: SlideUpdate, db: Session = Depends(get_db)):
    """更新幻灯片元数据"""
    result = slide_service.update_slide(
        db, slide_id, title=data.title, chapter=data.chapter
    )
    if not result:
        raise HTTPException(status_code=404, detail=f"未找到幻灯片: {slide_id}")

    await ws_manager.broadcast(
        SlideUpdatedMsg(slide=result.model_dump()).model_dump()
    )
    return result.model_dump()


@router.delete("/{slide_id}")
async def delete_slide(slide_id: str, db: Session = Depends(get_db)):
    """删除幻灯片（含文件）"""
    success = slide_service.delete_slide(db, slide_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"未找到幻灯片: {slide_id}")

    order = slide_service.get_slide_order(db)
    presentation_state.set_slide_order(order)

    await ws_manager.broadcast(
        SlideDeletedMsg(slide_id=slide_id).model_dump()
    )
    return {"message": "幻灯片已删除", "slide_id": slide_id}
