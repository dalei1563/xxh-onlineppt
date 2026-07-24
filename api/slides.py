"""
Slides REST API - 幻灯片元数据与内容接口。
内容以独立文件存储，REST 负责元数据 CRUD 和文件读取。
"""
import asyncio
import json
import os
import re
import uuid
from pathlib import Path
from typing import List
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session

from db.database import get_db
from editor.models import (
    SlideInfo,
    SlideReorder,
    SlideUpdate,
    SlideCreate,
    SlideVolumeUpdate,
)
from db.models import SlideMeta
from services.slide_service import slide_service
from services.thumbnail_service import thumbnail_service
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
# 0 表示不限制。视频素材常常数百 MB，默认不应因为演示现场素材大小而拒绝上传。
MAX_UPLOAD_SIZE_BYTES = int(os.getenv("MAX_UPLOAD_SIZE_BYTES", "0"))
# 较大的分块可减少 600MB+ 文件上传时的磁盘写入/协程切换次数，同时只占用有限内存。
UPLOAD_CHUNK_SIZE = 8 * 1024 * 1024


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

    file_src = None
    if data.type == "external":
        parsed = urlparse(data.source_url or "")
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise HTTPException(status_code=400, detail="外部页面必须使用有效的 http/https 地址")
        file_src = data.source_url

    # 动态媒体/外部页面由统一模板按需渲染；其他类型创建初始 HTML。
    html_content = (
        None
        if data.type in {"video", "image", "external"}
        else render_slide(data.type, {}, "{SLIDE_ID}")
    )

    result = slide_service.create_slide(
        db,
        slide_type=data.type,
        chapter=data.chapter,
        title=data.title,
        html_content=html_content,
        file_src=file_src,
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
                if MAX_UPLOAD_SIZE_BYTES > 0 and size > MAX_UPLOAD_SIZE_BYTES:
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
    slide = slide_service.get_slide_orm(db, slide_id)
    html = slide_service.get_slide_html(slide)
    if not html:
        raise HTTPException(status_code=404, detail=f"未找到幻灯片: {slide_id}")
    volume_gain = slide_service.get_volume_gain(db, slide_id)
    is_video_slide = bool(slide and slide.type == "video")

    extra_css = ""
    external_url = slide_service.get_external_url(slide)
    external_origin = ""
    if external_url:
        parsed_external = urlparse(external_url)
        external_origin = f"{parsed_external.scheme}://{parsed_external.netloc}"
    external_origin_js = json.dumps(external_origin).replace("<", "\\u003c")
    slide_id_js = json.dumps(slide_id).replace("<", "\\u003c")
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
  var videos = document.querySelectorAll('video');
  var externalFrame = document.querySelector('.external-service-frame');
  var externalOrigin = {external_origin_js};
  var configuredGain = {volume_gain:.4f};
  var audioContext = null;
  var gainNode = null;
  var audioSources = [];

  function ensureAudioGraph() {{
    if (gainNode || !videos.length) return gainNode;
    var AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) return null;
    try {{
      audioContext = new AudioContextClass();
      gainNode = audioContext.createGain();
      gainNode.connect(audioContext.destination);
      videos.forEach(function(v) {{
        var source = audioContext.createMediaElementSource(v);
        source.connect(gainNode);
        audioSources.push(source);
        // 连接到 Web Audio 后由 GainNode 统一控制倍数。
        v.volume = 1;
      }});
      return gainNode;
    }} catch (err) {{
      console.warn('[Video volume] Web Audio initialization failed:', err);
      return null;
    }}
  }}

  function resumeAudioGraph() {{
    if (audioContext && audioContext.state === 'suspended') {{
      audioContext.resume().catch(function(){{}});
    }}
  }}

  function applyVolumeGain(value) {{
    var nextGain = Number(value);
    if (!Number.isFinite(nextGain)) nextGain = 1;
    configuredGain = Math.max(0, Math.min(20, nextGain));

    // 0~1 倍可先走原生 volume，避免默认 1 倍播放无谓创建 AudioContext。
    // 超过 1 倍时建立 GainNode，才能实现真正的音量增强。
    if (!gainNode && configuredGain <= 1) {{
      videos.forEach(function(v) {{ v.volume = configuredGain; }});
      return;
    }}
    var node = ensureAudioGraph();
    if (node) {{
      node.gain.setTargetAtTime(
        configuredGain,
        audioContext.currentTime,
        0.015
      );
      resumeAudioGraph();
    }}
  }}

  function sendToExternal(type, payload) {{
    if (!externalFrame || !externalFrame.contentWindow || !externalOrigin) return;
    externalFrame.contentWindow.postMessage({{
      source: 'xxh-presentation',
      version: 1,
      type: type,
      payload: payload || {{}}
    }}, externalOrigin);
  }}

  if (externalFrame) {{
    externalFrame.addEventListener('load', function() {{
      sendToExternal('presentation.enter', {{ slideId: {slide_id_js} }});
    }});
  }}

  // 统一新旧视频页行为：进入即播放、点击切换暂停/继续、结束停在最后一帧。
  // 历史 HTML 里即使带有 loop，也会在这里被关闭。
  videos.forEach(function(v) {{
    v.loop = false;
    v.removeAttribute('loop');
    v.preload = 'auto';
    v.setAttribute('preload', 'auto');
    v.autoplay = true;
    v.setAttribute('autoplay', '');
    v.style.cursor = 'pointer';
    v.addEventListener('click', function(ev) {{
      ev.preventDefault();
      ev.stopPropagation();
      // 播放完成后保持最后一帧；只有离开页面再回来或显式“重播”才从头开始。
      if (v.ended) return;
      resumeAudioGraph();
      if (v.paused) v.play().catch(function(){{}});
      else v.pause();
    }});
    v.addEventListener('ended', function() {{
      v.pause();
    }});
    v.play().catch(function(){{}});
  }});

  // ---- 外层 → iframe 控制桥接 ----
  window.addEventListener('message', function(ev) {{
    var msg = ev.data || {{}};
    if (externalFrame && ev.source === externalFrame.contentWindow) {{
      if (ev.origin !== externalOrigin || msg.source !== 'xxh-ai-voice' || msg.version !== 1) return;
      parent.postMessage({{
        type: 'external_service_event',
        slide: {slide_id_js},
        event: msg
      }}, window.location.origin);
      return;
    }}
    if (ev.source !== parent || ev.origin !== window.location.origin) return;
    if (msg.type === 'unmute') {{
      applyVolumeGain(configuredGain);
      resumeAudioGraph();
      videos.forEach(function(v) {{ v.muted = false; v.play().catch(function(){{}}); }});
    }} else if (msg.type === 'replay_video') {{
      videos.forEach(function(v) {{ v.currentTime = 0; v.play().catch(function(){{}}); }});
    }} else if (msg.type === 'pause') {{
      videos.forEach(function(v) {{ v.pause(); }});
      sendToExternal('presentation.pause');
    }} else if (msg.type === 'resume') {{
      sendToExternal('presentation.resume');
    }} else if (msg.type === 'set_volume_gain') {{
      applyVolumeGain(msg.volumeGain);
    }} else if (msg.type === 'probe') {{
      // 外层连上后询问当前 frame 是否含视频，用于 unmute-overlay 显隐
      ev.source.postMessage({{
        type: 'state',
        hasVideo: !!document.querySelector('.slide video'),
        isVideoSlide: {str(is_video_slide).lower()},
        isExternalSlide: !!externalFrame,
        volumeGain: configuredGain,
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
  // iframe 获焦后，按键不会冒泡到外层演示页。捕获阶段转发演示快捷键，
  // 即使焦点落在 video 控件上，左右翻页和全屏仍保持可用。
  document.addEventListener('keydown', function(e) {{
    var target = e.target;
    var isEditable = target && (
      target.tagName === 'INPUT' ||
      target.tagName === 'TEXTAREA' ||
      target.tagName === 'SELECT' ||
      target.isContentEditable
    );
    if (isEditable) return;
    var presentationKeys = [
      'ArrowRight', 'ArrowLeft', ' ', 'Backspace',
      'Home', 'End', 'f', 'F', 'F2'
    ];
    if (presentationKeys.indexOf(e.key) === -1 && !(e.ctrlKey && e.key === 'F1')) return;
    e.preventDefault();
    e.stopPropagation();
    var keyPayload = {{
      type: 'presentation_key',
      key: e.key,
      ctrlKey: e.ctrlKey,
      altKey: e.altKey,
      shiftKey: e.shiftKey
    }};
    // 同源时同步调用，保留按键产生的浏览器用户激活状态（全屏 API 需要）；
    // 若未来改为跨域幻灯片文档，再退回 postMessage 桥接。
    try {{
      if (parent.app && typeof parent.app.handlePresentationKey === 'function') {{
        parent.app.handlePresentationKey(e.key, keyPayload);
        return;
      }}
    }} catch (error) {{}}
    parent.postMessage(keyPayload, window.location.origin);
  }}, true);
  window.addEventListener('beforeunload', function() {{
    sendToExternal('presentation.leave', {{ slideId: {slide_id_js} }});
  }});
  applyVolumeGain(configuredGain);
}})();
</script>
</body>
</html>"""
    return HTMLResponse(document)


@router.get("/{slide_id}/volume")
async def get_slide_volume(slide_id: str, db: Session = Depends(get_db)):
    """读取视频页已保存的音量增益倍数。"""
    slide = slide_service.get_slide_orm(db, slide_id)
    if not slide:
        raise HTTPException(status_code=404, detail=f"未找到幻灯片: {slide_id}")
    if slide.type != "video":
        raise HTTPException(status_code=400, detail="只有视频幻灯片支持音量设置")
    return {
        "slide_id": slide_id,
        "volume_gain": slide_service.get_volume_gain(db, slide_id),
    }


@router.put("/{slide_id}/volume")
async def update_slide_volume(
    slide_id: str,
    data: SlideVolumeUpdate,
    db: Session = Depends(get_db),
):
    """实时保存视频页音量增益倍数。"""
    slide = slide_service.get_slide_orm(db, slide_id)
    if not slide:
        raise HTTPException(status_code=404, detail=f"未找到幻灯片: {slide_id}")
    if slide.type != "video":
        raise HTTPException(status_code=400, detail="只有视频幻灯片支持音量设置")
    gain = slide_service.set_volume_gain(db, slide_id, data.volume_gain)
    return {"slide_id": slide_id, "volume_gain": gain}


@router.get("/{slide_id}/thumbnail")
async def get_slide_thumbnail(
    slide_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """返回后台生成并缓存的静态缩略图，避免编辑器加载完整幻灯片。"""
    slide = db.query(SlideMeta).filter(SlideMeta.slide_id == slide_id).first()
    if not slide:
        raise HTTPException(status_code=404, detail=f"未找到幻灯片: {slide_id}")
    path = await asyncio.to_thread(
        thumbnail_service.ensure_thumbnail,
        slide,
        str(request.base_url).rstrip("/"),
    )
    return FileResponse(
        path,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=3600"},
    )


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
    thumbnail_service.invalidate(slide_id)

    order = slide_service.get_slide_order(db)
    presentation_state.set_slide_order(order)

    await ws_manager.broadcast(
        SlideDeletedMsg(slide_id=slide_id).model_dump()
    )
    return {"message": "幻灯片已删除", "slide_id": slide_id}
