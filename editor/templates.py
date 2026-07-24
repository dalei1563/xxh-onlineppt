"""
Slide templates - 预定义的幻灯片模板与渲染函数。
每个模板包含：
- 元数据（label/icon/desc/default_title/default_chapter）
- skeleton：创建新幻灯片时的初始 HTML
- render(content, slide_id)：根据结构化数据渲染最终 HTML
"""
from typing import Dict, Any, List, Optional
import html


def _esc(value: Any) -> str:
    """安全地转义字符串，用于插入 HTML"""
    if value is None:
        return ""
    return html.escape(str(value))


def _esc_br(value: Any) -> str:
    """转义字符串并将换行转换为 <br>"""
    return _esc(value).replace("\n", "<br>")


# ====== 模板定义 ======

TEMPLATES: Dict[str, dict] = {
    "video": {
        "label": "视频页",
        "icon": "🎬",
        "desc": "全屏视频页面",
        "default_title": "视频页",
        "default_chapter": "未分类",
        "render": lambda content, slide_id: f"""<div class="slide slide-media slide-video" data-slide="{_esc(slide_id)}">
    <video id="mediaVideo-{_esc(slide_id)}" playsinline autoplay muted>
        <source src="{_esc(content.get('video_src', '/static/intro_video.mp4'))}" type="{_esc(content.get('video_mime', 'video/mp4'))}">
        您的浏览器不支持视频播放
    </video>
</div>""",
    },

    "image": {
        "label": "图片页",
        "icon": "🖼️",
        "desc": "全屏图片页面",
        "default_title": "图片页",
        "default_chapter": "未分类",
        "render": lambda content, slide_id: f"""<div class="slide slide-media slide-image" data-slide="{_esc(slide_id)}">
    <img src="{_esc(content.get('image_src', ''))}" alt="全屏图片">
</div>""",
    },

    "white": {
        "label": "内容页(白)",
        "icon": "📄",
        "desc": "白色背景的通用内容页面",
        "default_title": "新内容页",
        "default_chapter": "未分类",
        "render": lambda content, slide_id: f"""<div class="slide template-white" data-slide="{slide_id}">
    <div class="gsp-logo">GSP®</div>
    <div class="title">{_esc(content.get('title', '标题'))}</div>
    <div class="content">
        {_render_body(content.get('body', '正文内容'))}
    </div>
    <div class="page-indicator">Page No -</div>
</div>""",
    },

    "base": {
        "label": "基础模板",
        "icon": "📋",
        "desc": "白色背景+蓝色边栏的标准模板",
        "default_title": "新页面",
        "default_chapter": "未分类",
        "render": lambda content, slide_id: f"""<div class="slide template-base" data-slide="{slide_id}">
    <div class="gsp-logo"><img src="/static/images/gsp-logo.png" alt="GSP"></div>
    <div class="right-sidebar">
        <div class="sidebar-icon">
            <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <circle cx="12" cy="12" r="10" fill="none" stroke="white" stroke-width="2"/>
                <circle cx="12" cy="12" r="4" fill="white"/>
            </svg>
        </div>
        <div class="page-indicator">Page No -</div>
    </div>
    <div class="content-area">
        <div class="accent-line"></div>
        <div class="title">{_esc(content.get('title', '标题'))}</div>
        <div class="subtitle">{_esc(content.get('subtitle', '副标题'))}</div>
        <div class="body">
            {_render_body(content.get('body', '在此添加内容'))}
        </div>
    </div>
</div>""",
    },

    "external": {
        "label": "外部页面",
        "icon": "🌐",
        "desc": "通过安全 iframe 接入独立服务或网页",
        "default_title": "外部页面",
        "default_chapter": "外部服务",
        "render": lambda content, slide_id: f"""<div class="slide slide-external" data-slide="{_esc(slide_id)}">
    <iframe
        class="external-service-frame"
        src="{_esc(content.get('external_url', 'about:blank'))}"
        title="{_esc(content.get('external_title', '外部页面'))}"
        allow="microphone; autoplay"
        sandbox="allow-scripts allow-same-origin allow-forms"
        referrerpolicy="strict-origin-when-cross-origin"
    ></iframe>
</div>""",
    },
}

TEMPLATE_ORDER = ["video", "image", "external", "white", "base"]


def _render_body(body: Any) -> str:
    """渲染正文：如果内容以 < 开头则视为 HTML，否则包裹为 <p>"""
    if not body:
        return "<p></p>"
    text = str(body)
    if text.strip().startswith("<"):
        return text
    # 将换行转换为 <p>
    parts = text.strip().split("\n")
    return "".join(f"<p>{_esc(p)}</p>" for p in parts if p.strip())


# ====== 公共 API ======

def get_template(template_type: str) -> Optional[dict]:
    """获取指定模板定义"""
    return TEMPLATES.get(template_type)


def get_skeleton(template_type: str, slide_id: str = "{SLIDE_ID}") -> str:
    """获取模板初始骨架 HTML（用于创建新幻灯片）"""
    tmpl = TEMPLATES.get(template_type)
    if not tmpl:
        return ""
    # 使用默认空 content 渲染一次，得到骨架
    return tmpl["render"]({}, slide_id)


def render_slide(template_type: str, content: Dict[str, Any], slide_id: str) -> str:
    """根据模板类型和内容渲染幻灯片 HTML"""
    tmpl = TEMPLATES.get(template_type)
    if not tmpl:
        # 未知类型：返回一个空白页
        return f"""<div class="slide template-white" data-slide="{slide_id}">
    <div class="gsp-logo">GSP®</div>
    <div class="title">未识别模板: {_esc(template_type)}</div>
    <div class="content"><p>请检查幻灯片类型</p></div>
    <div class="page-indicator">Page No -</div>
</div>"""
    return tmpl["render"](content or {}, slide_id)


def get_all_templates_for_ui() -> List[dict]:
    """获取 UI 展示用的模板列表"""
    result = []
    for ttype in TEMPLATE_ORDER:
        tmpl = TEMPLATES.get(ttype)
        if tmpl:
            result.append({
                "type": ttype,
                "label": tmpl["label"],
                "icon": tmpl["icon"],
                "desc": tmpl["desc"],
                "default_title": tmpl["default_title"],
                "default_chapter": tmpl["default_chapter"],
            })
    # 添加不在 TEMPLATE_ORDER 中的剩余模板
    for ttype, tmpl in TEMPLATES.items():
        if ttype not in TEMPLATE_ORDER:
            result.append({
                "type": ttype,
                "label": tmpl["label"],
                "icon": tmpl["icon"],
                "desc": tmpl["desc"],
                "default_title": tmpl["default_title"],
                "default_chapter": tmpl["default_chapter"],
            })
    return result
