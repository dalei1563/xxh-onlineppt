"""
Slide service - 幻灯片领域的唯一业务入口。
所有幻灯片的 HTML 内容统一通过模板引擎动态生成，不再依赖预渲染的文件。
"""
import json
import os
import re
import uuid
from html import unescape
from pathlib import Path
from typing import List, Optional, Dict, Any
from urllib.parse import unquote, urlparse
from sqlalchemy.orm import Session

from db.models import SlideMeta, SlideAudioSetting
from editor.models import SlideInfo
from editor.templates import render_slide, TEMPLATES

# 内容文件存储根目录（相对 static/）
SLIDES_DIR = Path(__file__).parent.parent / "static" / "slides"
UPLOADS_DIR = Path(__file__).parent.parent / "static" / "uploads"


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
VIDEO_EXTS = {".mp4", ".webm", ".ogg", ".mov"}
VIDEO_MIME_TYPES = {
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".ogg": "video/ogg",
    ".mov": "video/quicktime",
}
AI_VOICE_SERVICE_MARKER = "service://ai-voice"
DEFAULT_AI_VOICE_SERVICE_URL = "http://127.0.0.1:8100/?embed=1&bridge=1"

# 已从仓库移除的历史视频 HTML 包装页映射。旧数据库升级时无需依赖包装页仍然存在。
LEGACY_VIDEO_PATH_MAP = {
    "slides/slide_intro.html": "intro_video.mp4",
}
_VIDEO_SRC_RE = re.compile(
    r'(?:<source[^>]+|<video[^>]+)src=["\']([^"\']+)',
    re.IGNORECASE,
)

# 根 div 上 data-slide="xxx" 的 pattern；get_slide_html 用它做"自愈"防护：
# 历史/外部脚本产生的 HTML 文件中根 div 的 data-slide 可能与 DB 的 slide_id 不一致，
# 会导致 /api/slides/full 拼接后浏览器按 data-slide 找元素失败、整页黑屏。
_ROOT_DATASLIDE_RE = re.compile(
    r'(<div class="slide[^"]*" data-slide=")([^"]+)(")'
)


class SlideService:
    """幻灯片领域服务——DB 只存元数据，HTML 通过模板动态渲染"""

    # ===== 初始化 =====

    def seed_slides(self, db: Session):
        """初始化版本受控的默认幻灯片（只在数据库为空时执行）。"""
        existing = db.query(SlideMeta).count()
        if existing > 0:
            return
        from editor.default_slides import DEFAULT_SLIDES

        for i, item in enumerate(DEFAULT_SLIDES):
            slide = SlideMeta(
                slide_id=item["slide_id"],
                title=item["title"],
                type=item["type"],
                chapter=item["chapter"],
                display_order=i,
                file_path=item["file_path"],
            )
            db.add(slide)
        db.commit()
        print(f"[Editor] Seeded {len(DEFAULT_SLIDES)} built-in slides")

    def migrate_legacy_video_slides(self, db: Session) -> int:
        """把历史 video + HTML 包装页记录迁移为直接视频资源路径。

        迁移是幂等的；任何无法识别的旧视频页都会显式报错，避免运行时悄悄走第二套渲染逻辑。
        """
        legacy_slides = [
            slide
            for slide in db.query(SlideMeta).filter(SlideMeta.type == "video").all()
            if (slide.file_path or "").lower().endswith(".html")
        ]
        if not legacy_slides:
            return 0

        failures = []
        for slide in legacy_slides:
            original_path = (slide.file_path or "").replace("\\", "/")
            media_path = LEGACY_VIDEO_PATH_MAP.get(original_path)
            if not media_path:
                wrapper_path = Path(__file__).parent.parent / "static" / original_path
                if wrapper_path.is_file():
                    html = wrapper_path.read_text(encoding="utf-8", errors="ignore")
                    match = _VIDEO_SRC_RE.search(html)
                    if match:
                        media_path = self._normalize_static_media_path(
                            match.group(1),
                            wrapper_path.parent,
                        )

            media_file = (
                Path(__file__).parent.parent / "static" / media_path
                if media_path else None
            )
            if (
                not media_path
                or Path(media_path).suffix.lower() not in VIDEO_EXTS
                or not media_file.is_file()
            ):
                failures.append(f"{slide.slide_id} ({original_path})")
                continue
            slide.file_path = media_path.replace("\\", "/")

        if failures:
            db.rollback()
            raise RuntimeError(
                "无法迁移历史视频幻灯片，请修复其视频地址: " + ", ".join(failures)
            )
        db.commit()
        return len(legacy_slides)

    def migrate_ai_chat_slides(self, db: Session) -> int:
        """将历史内嵌 AI 页面迁移为通用 external iframe 幻灯片。"""
        legacy_slides = (
            db.query(SlideMeta)
            .filter(SlideMeta.type == "ai_chat")
            .all()
        )
        if not legacy_slides:
            return 0
        for slide in legacy_slides:
            slide.type = "external"
            slide.file_path = AI_VOICE_SERVICE_MARKER
        db.commit()
        return len(legacy_slides)

    @staticmethod
    def _normalize_static_media_path(src: str, wrapper_dir: Path) -> Optional[str]:
        parsed = urlparse(unescape(src))
        if parsed.scheme or parsed.netloc:
            return None
        path = unquote(parsed.path).replace("\\", "/")
        static_root = (Path(__file__).parent.parent / "static").resolve()
        if path.startswith("/static/"):
            candidate = static_root / path.removeprefix("/static/")
        else:
            candidate = wrapper_dir / path
        candidate = candidate.resolve()
        try:
            return candidate.relative_to(static_root).as_posix()
        except ValueError:
            return None

    # ===== 查询 =====

    def get_all_slides(self, db: Session) -> List[SlideInfo]:
        slides = db.query(SlideMeta).order_by(SlideMeta.display_order).all()
        return [self._to_info(s) for s in slides]

    def get_slide_order(self, db: Session) -> List[str]:
        slides = db.query(SlideMeta).order_by(SlideMeta.display_order).all()
        return [s.slide_id for s in slides]

    def get_slide(self, db: Session, slide_id: str) -> Optional[SlideInfo]:
        slide = db.query(SlideMeta).filter(SlideMeta.slide_id == slide_id).first()
        return self._to_info(slide) if slide else None

    def get_slide_orm(self, db: Session, slide_id: str) -> Optional[SlideMeta]:
        """获取原始 ORM 对象"""
        return db.query(SlideMeta).filter(SlideMeta.slide_id == slide_id).first()

    @staticmethod
    def get_external_url(slide: SlideMeta) -> str:
        """解析外部页面地址；内置服务标记通过环境变量映射到真实部署地址。"""
        if not slide or slide.type != "external":
            return ""
        value = (slide.file_path or "").strip()
        if value == AI_VOICE_SERVICE_MARKER:
            value = os.getenv(
                "AI_VOICE_SERVICE_URL",
                DEFAULT_AI_VOICE_SERVICE_URL,
            ).strip()
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return ""
        return value

    def get_volume_gain(self, db: Session, slide_id: str) -> float:
        """获取某张视频页保存的音量倍数；未设置时为原始音量。"""
        setting = (
            db.query(SlideAudioSetting)
            .filter(SlideAudioSetting.slide_id == slide_id)
            .first()
        )
        return float(setting.volume_gain) if setting else 1.0

    def set_volume_gain(self, db: Session, slide_id: str, volume_gain: float) -> float:
        """保存视频音量倍数，调用方负责确认 slide 存在且类型为 video。"""
        gain = max(0.0, min(20.0, float(volume_gain)))
        setting = (
            db.query(SlideAudioSetting)
            .filter(SlideAudioSetting.slide_id == slide_id)
            .first()
        )
        if setting:
            setting.volume_gain = gain
        else:
            db.add(SlideAudioSetting(slide_id=slide_id, volume_gain=gain))
        db.commit()
        return gain

    # ===== 统一幻灯片渲染 =====

    def _render_media_html(self, slide: SlideMeta) -> str:
        """通过唯一模板入口渲染图片/视频幻灯片。"""
        fp = slide.file_path or ""
        if slide.type == "image":
            src = f"/static/{fp}" if fp else ""
            return render_slide(
                "image",
                {"image_src": src},
                slide.slide_id,
            )
        if slide.type == "video":
            src = f"/static/{fp}" if fp else "/static/intro_video.mp4"
            mime_type = VIDEO_MIME_TYPES.get(Path(fp).suffix.lower(), "video/mp4")
            return render_slide(
                "video",
                {"video_src": src, "video_mime": mime_type},
                slide.slide_id,
            )
        if slide.type == "external":
            return render_slide(
                "external",
                {
                    "external_url": self.get_external_url(slide) or "about:blank",
                    "external_title": slide.title or "外部页面",
                },
                slide.slide_id,
            )
        return ""

    def get_slide_html(self, slide: SlideMeta) -> str:
        """获取幻灯片 HTML 内容——统一出口。

        会强制把根 div 的 data-slide 属性改写为当前 slide.slide_id，
        以防止历史/外部脚本生成的 HTML 中 data-slide 与 DB slide_id 不一致，
        进而导致 /api/slides/full 拼接后浏览器选中失败、整页黑屏。
        """
        if not slide:
            return ""
        expected_sid = slide.slide_id
        fp = slide.file_path or ""
        html: str = ""
        # 视频类型永远只走统一动态模板；历史 HTML 包装页必须在启动迁移阶段消除。
        if slide.type in ("video", "external"):
            if fp.lower().endswith(".html"):
                raise RuntimeError(
                    f"动态幻灯片 {slide.slide_id} 尚未迁移: {fp}"
                )
            html = self._render_media_html(slide)
        # 有 HTML 文件则直接读取（兼容 PPT 导入等预渲染的幻灯片）
        elif fp.endswith(".html"):
            abs_path = Path(__file__).parent.parent / "static" / fp
            if abs_path.exists():
                html = abs_path.read_text(encoding="utf-8")
        # 无 HTML 文件的图片：用模板动态生成
        if not html and slide.type == "image":
            html = self._render_media_html(slide)
        # 其他类型用模板骨架兜底
        if not html:
            tmpl = TEMPLATES.get(slide.type)
            if tmpl:
                html = tmpl["render"]({}, slide.slide_id)
        if not html:
            return ""
        # 自愈：把根 div 的 data-slide 改写为正确 slide_id。
        # 只替换第一个匹配（根 div），避免误伤正文里其它 data-slide 属性。
        return _ROOT_DATASLIDE_RE.sub(
            lambda mo: mo.group(1) + expected_sid + mo.group(3),
            html,
            count=1,
        )

    def get_slide_html_by_id(self, db: Session, slide_id: str) -> str:
        slide = self.get_slide_orm(db, slide_id)
        return self.get_slide_html(slide)

    def write_slide_html(self, slide: SlideMeta, html: str):
        """将 HTML 写入幻灯片文件"""
        if not slide or not slide.file_path:
            return
        abs_path = Path(__file__).parent.parent / "static" / slide.file_path
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_text(html, encoding="utf-8")

    def get_all_slides_html(self, db: Session) -> str:
        """按顺序读取所有幻灯片 HTML 并拼接"""
        slides = db.query(SlideMeta).order_by(SlideMeta.display_order).all()
        parts = []
        for s in slides:
            html = self.get_slide_html(s)
            if html:
                parts.append(html)
        return "".join(parts)

    # ===== 增删改 =====

    def reorder_slides(self, db: Session, new_order: List[str]):
        for i, slide_id in enumerate(new_order):
            slide = db.query(SlideMeta).filter(SlideMeta.slide_id == slide_id).first()
            if slide:
                slide.display_order = i
        db.commit()

    def create_slide(self, db: Session, slide_type: str, chapter: str = None,
                     title: str = None, html_content: str = None,
                     file_src: str = None) -> Optional[SlideInfo]:
        """
        创建幻灯片
        - HTML 类：html_content 为渲染好的 HTML
        - 图片/视频类：file_src 为已保存的文件路径
        """
        new_id = self._generate_slide_id(db)
        tmpl = TEMPLATES.get(slide_type)
        effective_chapter = chapter or (tmpl["default_chapter"] if tmpl else "未分类")
        effective_title = title or (tmpl["default_title"] if tmpl else "新页面")

        existing_count = db.query(SlideMeta).count()

        if slide_type in ("image", "video", "external"):
            # 图片/视频：file_src 指向上传文件
            # 注意：必须用 removeprefix 而非 lstrip，lstrip 是按字符集剥离
            # 会错误吃掉 "/static/assets/..."、"/static/slides/..." 等以 s/t/a/i/c 开头的后续字符
            if slide_type == "external":
                file_path_rel = file_src or ""
            elif file_src:
                file_path_rel = file_src.removeprefix("/static/") or file_src.lstrip("/")
            else:
                file_path_rel = f"uploads/{new_id}.bin"
        else:
            # HTML 类：将内容写入独立 HTML 文件
            file_name = f"slide_{new_id}.html"
            file_path_rel = f"slides/{file_name}"
            abs_path = SLIDES_DIR / file_name
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            # 替换 {SLIDE_ID} 占位符为实际的 slide_id
            final_html = (html_content or "").replace("{SLIDE_ID}", new_id)
            abs_path.write_text(final_html, encoding="utf-8")

        slide = SlideMeta(
            slide_id=new_id,
            title=effective_title,
            type=slide_type,
            chapter=effective_chapter,
            display_order=existing_count,
            file_path=file_path_rel,
        )
        db.add(slide)
        db.commit()
        db.refresh(slide)
        return self._to_info(slide)

    def update_slide(self, db: Session, slide_id: str, title: str = None,
                     chapter: str = None, html_content: str = None) -> Optional[SlideInfo]:
        """更新幻灯片元数据及文件内容"""
        slide = db.query(SlideMeta).filter(SlideMeta.slide_id == slide_id).first()
        if not slide:
            return None
        if title is not None:
            slide.title = title
        if chapter is not None:
            slide.chapter = chapter
        if html_content is not None and slide.type not in ("image", "video"):
            self.write_slide_html(slide, html_content)
        db.commit()
        db.refresh(slide)
        return self._to_info(slide)

    def delete_slide(self, db: Session, slide_id: str) -> bool:
        """删除幻灯片（含文件）"""
        slide = db.query(SlideMeta).filter(SlideMeta.slide_id == slide_id).first()
        if not slide:
            return False

        # 删除内容文件
        if slide.file_path and slide.type != "external":
            abs_path = Path(__file__).parent.parent / "static" / slide.file_path
            if abs_path.exists():
                abs_path.unlink()

        db.query(SlideAudioSetting).filter(
            SlideAudioSetting.slide_id == slide_id
        ).delete(synchronize_session=False)
        db.delete(slide)
        db.commit()
        self._renumber_order(db)
        return True

    def get_chapters(self, db: Session) -> List[str]:
        from sqlalchemy import func as sa_func
        chapters = db.query(SlideMeta.chapter).distinct().order_by(SlideMeta.display_order).all()
        return [c[0] for c in chapters if c[0]]

    # ===== 内部方法 =====

    def _generate_slide_id(self, db: Session) -> str:
        return f"s-{uuid.uuid4().hex[:8]}"

    def _renumber_order(self, db: Session):
        slides = db.query(SlideMeta).order_by(SlideMeta.display_order).all()
        for i, slide in enumerate(slides):
            slide.display_order = i
        db.commit()

    @staticmethod
    def _to_info(slide: SlideMeta) -> SlideInfo:
        return SlideInfo(
            id=slide.id,
            slide_id=slide.slide_id,
            title=slide.title,
            type=slide.type,
            chapter=slide.chapter,
            display_order=slide.display_order,
            file_path=slide.file_path,
        )


# 全局单例
slide_service = SlideService()
