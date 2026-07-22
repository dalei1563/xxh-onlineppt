"""幻灯片缩略图生成与缓存。"""

from __future__ import annotations

import asyncio
import os
import re
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Iterable
from urllib.parse import unquote, urlparse

from PIL import Image, ImageDraw, ImageFont, ImageOps


PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = PROJECT_ROOT / "static"
THUMBNAIL_DIR = STATIC_DIR / "thumbnails"
THUMBNAIL_SIZE = (420, 236)
THUMBNAIL_CACHE_VERSION = "v2"


class ThumbnailService:
    def __init__(self) -> None:
        THUMBNAIL_DIR.mkdir(parents=True, exist_ok=True)
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()
        # 避免多个 HTML/视频渲染进程同时争抢 CPU、磁盘和显存。
        self._heavy_render_slots = threading.Semaphore(2)

    @staticmethod
    def _safe_id(slide_id: str) -> str:
        return re.sub(r"[^a-zA-Z0-9_-]", "_", slide_id)

    def thumbnail_path(self, slide_id: str) -> Path:
        return THUMBNAIL_DIR / f"{THUMBNAIL_CACHE_VERSION}_{self._safe_id(slide_id)}.jpg"

    def _lock_for(self, slide_id: str) -> threading.Lock:
        with self._locks_guard:
            return self._locks.setdefault(slide_id, threading.Lock())

    def ensure_thumbnail(self, slide, base_url: str) -> Path:
        """返回缓存缩略图路径；不存在时同步生成一次。"""
        output = self.thumbnail_path(slide.slide_id)
        if output.exists() and output.stat().st_size > 0:
            return output

        with self._lock_for(slide.slide_id):
            if output.exists() and output.stat().st_size > 0:
                return output
            temp_output = output.with_suffix(".tmp.jpg")
            temp_output.unlink(missing_ok=True)
            try:
                # 历史 PPT 导入数据常标记为 image，但 file_path 实际是包含
                # <img> 的 HTML 包装页。先识别包装页，避免误把 HTML 交给 Pillow。
                if (slide.file_path or "").lower().endswith(".html"):
                    if not self._render_legacy_media_wrapper(slide, temp_output):
                        self._render_html(slide, base_url, temp_output)
                elif slide.type == "image":
                    self._render_image(slide, temp_output)
                elif slide.type == "video":
                    self._render_video(slide, temp_output)
                else:
                    self._render_html(slide, base_url, temp_output)
            except Exception as exc:
                print(f"[Thumbnail] Fallback for {slide.slide_id}: {exc}")
                self._render_fallback(slide, temp_output)
            os.replace(temp_output, output)
            print(f"[Thumbnail] Generated: {slide.slide_id}")
            return output

    def invalidate(self, slide_id: str) -> None:
        self.thumbnail_path(slide_id).unlink(missing_ok=True)

    @staticmethod
    def _source_path(slide) -> Path:
        return STATIC_DIR / (slide.file_path or "")

    @staticmethod
    def _save_contained(image: Image.Image, output: Path, background=(12, 18, 28)) -> None:
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", THUMBNAIL_SIZE, background)
        left = (THUMBNAIL_SIZE[0] - image.width) // 2
        top = (THUMBNAIL_SIZE[1] - image.height) // 2
        canvas.paste(image, (left, top))
        canvas.save(output, "JPEG", quality=80, optimize=True, progressive=True)

    def _render_image(self, slide, output: Path) -> None:
        source = self._source_path(slide)
        if not source.is_file():
            raise FileNotFoundError(source)
        with Image.open(source) as image:
            self._save_contained(image, output)

    @staticmethod
    def _static_asset_from_url(url: str) -> Path | None:
        path = unquote(urlparse(url).path)
        if not path.startswith("/static/"):
            return None
        candidate = (STATIC_DIR / path.removeprefix("/static/")).resolve()
        try:
            candidate.relative_to(STATIC_DIR.resolve())
        except ValueError:
            return None
        return candidate if candidate.is_file() else None

    def _render_legacy_media_wrapper(self, slide, output: Path) -> bool:
        """快速处理仅包裹单个图片/视频的历史 HTML 页面。"""
        wrapper = self._source_path(slide)
        if not wrapper.is_file():
            return False
        html = wrapper.read_text(encoding="utf-8", errors="ignore")
        if "slide-media slide-image" in html:
            match = re.search(r'<img[^>]+src=["\']([^"\']+)', html, re.IGNORECASE)
            source = self._static_asset_from_url(match.group(1)) if match else None
            if source:
                with Image.open(source) as image:
                    self._save_contained(image, output)
                return True
        if "slide-media slide-video" in html:
            match = re.search(
                r'(?:<source[^>]+|<video[^>]+)src=["\']([^"\']+)',
                html,
                re.IGNORECASE,
            )
            source = self._static_asset_from_url(match.group(1)) if match else None
            if source:
                class _VideoSource:
                    file_path = str(source.relative_to(STATIC_DIR)).replace("\\", "/")
                self._render_video(_VideoSource(), output)
                return True
        return False

    def _render_video(self, slide, output: Path) -> None:
        source = self._source_path(slide)
        if not source.is_file():
            raise FileNotFoundError(source)
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError("ffmpeg is not available")
        video_filter = (
            "scale=420:236:force_original_aspect_ratio=decrease,"
            "pad=420:236:(ow-iw)/2:(oh-ih)/2:color=black"
        )
        with self._heavy_render_slots:
            result = subprocess.run(
                [
                    ffmpeg,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-ss",
                    "1",
                    "-i",
                    str(source),
                    "-frames:v",
                    "1",
                    "-vf",
                    video_filter,
                    "-q:v",
                    "5",
                    "-y",
                    str(output),
                ],
                capture_output=True,
                text=True,
                timeout=90,
            )
        if result.returncode != 0 or not output.exists():
            raise RuntimeError(result.stderr.strip() or "video thumbnail failed")

    @staticmethod
    def _browser_path() -> Path | None:
        candidates = [
            Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
            Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
            Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
            Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
        ]
        return next((path for path in candidates if path.is_file()), None)

    def _render_html(self, slide, base_url: str, output: Path) -> None:
        browser = self._browser_path()
        if not browser:
            raise RuntimeError("Edge/Chrome is not available")
        url = f"{base_url.rstrip('/')}/api/slides/{slide.slide_id}/page"
        with tempfile.TemporaryDirectory(prefix="gsp-thumb-") as profile_dir:
            screenshot = Path(profile_dir) / "shot.png"
            with self._heavy_render_slots:
                result = subprocess.run(
                    [
                        str(browser),
                        "--headless=new",
                        "--disable-gpu",
                        "--hide-scrollbars",
                        "--mute-audio",
                        "--window-size=1920,1080",
                        "--virtual-time-budget=1500",
                        f"--user-data-dir={profile_dir}",
                        f"--screenshot={screenshot}",
                        url,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=45,
                )
            if result.returncode != 0 or not screenshot.exists():
                raise RuntimeError(result.stderr.strip() or "HTML thumbnail failed")
            with Image.open(screenshot) as image:
                self._save_contained(image, output, background=(255, 255, 255))

    @staticmethod
    def _font(size: int):
        for font_path in (
            Path(r"C:\Windows\Fonts\msyh.ttc"),
            Path(r"C:\Windows\Fonts\simhei.ttf"),
        ):
            if font_path.is_file():
                return ImageFont.truetype(str(font_path), size)
        return ImageFont.load_default()

    def _render_fallback(self, slide, output: Path) -> None:
        canvas = Image.new("RGB", THUMBNAIL_SIZE, (241, 245, 249))
        draw = ImageDraw.Draw(canvas)
        label = {"video": "视频", "image": "图片"}.get(slide.type, "HTML")
        title = (slide.title or "未命名幻灯片")[:24]
        draw.rounded_rectangle((24, 24, 396, 212), radius=18, fill=(255, 255, 255), outline=(203, 213, 225), width=2)
        draw.text((42, 58), label, font=self._font(24), fill=(34, 197, 94))
        draw.text((42, 112), title, font=self._font(22), fill=(30, 41, 59))
        canvas.save(output, "JPEG", quality=80, optimize=True)

    async def warm_cache(self, slides: Iterable, base_url: str) -> None:
        """服务启动后低并发预生成现有课件缩略图。"""
        await asyncio.sleep(1)
        generated = 0
        for slide in slides:
            try:
                if not self.thumbnail_path(slide.slide_id).exists():
                    await asyncio.to_thread(self.ensure_thumbnail, slide, base_url)
                    generated += 1
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                print(f"[Thumbnail] Warm-up failed for {slide.slide_id}: {exc}")
        print(f"[Thumbnail] Cache ready; generated {generated} thumbnails")


thumbnail_service = ThumbnailService()
