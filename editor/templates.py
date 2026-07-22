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
        "render": lambda content, slide_id: f"""<div class="slide slide-media slide-video" data-slide="{slide_id}">
    <video id="mediaVideo" playsinline autoplay muted loop>
        <source src="{_esc(content.get('video_src', '/static/intro_video.mp4'))}" type="video/mp4">
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
        "render": lambda content, slide_id: f"""<div class="slide slide-media slide-image" data-slide="{slide_id}">
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

    "ai_chat": {
        "label": "AI对话",
        "icon": "🤖",
        "desc": "智能语音对话页面",
        "default_title": "AI 对话",
        "default_chapter": "AI互动",
        "render": lambda content, slide_id: f"""<link rel="stylesheet" href="/static/css/ai-chat.css">
<div class="slide template-ai-chat" data-slide="{slide_id}">
    <div class="ai-chat-container" id="aiChatContainer">
        <!-- 左侧：视频头像 + 录音按钮 -->
        <div class="ai-chat-left">
            <div class="ai-avatar-wrapper">
                <video class="ai-avatar-video" id="aiAvatarVideo" playsinline muted loop>
                    <source src="/static/assets/聆听.mp4" type="video/mp4">
                </video>
                <div class="ai-avatar-ring" id="aiAvatarRing"></div>
            </div>
            <div class="ai-chat-status" id="aiChatStatus">点击开始对话</div>
            <button class="ai-record-btn" id="aiRecordBtn">
                <svg class="mic-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path>
                    <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
                    <line x1="12" y1="19" x2="12" y2="23"></line>
                    <line x1="8" y1="23" x2="16" y2="23"></line>
                </svg>
                <span class="record-text">点击说话</span>
            </button>
        </div>
        <!-- 右侧：对话记录 -->
        <div class="ai-chat-right">
            <div class="ai-chat-header">
                <span class="ai-chat-title">💬 AI 对话</span>
                <button class="ai-clear-btn" id="aiClearBtn">清除记录</button>
            </div>
            <div class="ai-chat-messages" id="aiChatMessages">
                <div class="ai-message ai-message-system">
                    <div class="ai-message-content">您好！我是GSP学习会的AI主持助手，请问有什么可以帮助您的？🎤</div>
                </div>
            </div>
        </div>
    </div>
    <script src="/static/js/ai-chat.js"></script>
</div>""",
    },
}

TEMPLATE_ORDER = ["video", "image", "white", "base", "ai_chat"]


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
