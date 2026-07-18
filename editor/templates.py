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

    "seating": {
        "label": "座位安排",
        "icon": "🪑",
        "desc": "会议室座位分布图",
        "default_title": "座位安排",
        "default_chapter": "签到",
        "render": lambda content, slide_id: _render_seating(content, slide_id),
    },

    "checkin": {
        "label": "签到码",
        "icon": "📷",
        "desc": "微信扫码签到页面",
        "default_title": "学习会签到码",
        "default_chapter": "签到",
        "render": lambda content, slide_id: f"""<div class="slide slide-02" data-slide="{slide_id}">
    <div class="gsp-logo">GSP®</div>
    <div class="title">{_esc(content.get('title', '学习会签到码'))}</div>
    <div class="subtitle">{_esc(content.get('subtitle', '微信扫码签到'))}</div>
    <div class="qr-placeholder">{content.get('qr_text', '[二维码位置]')}</div>
    <div class="page-indicator">Page No -</div>
</div>""",
    },

    "home": {
        "label": "主页",
        "icon": "🏠",
        "desc": "活动主页面，含标题和日期",
        "default_title": "活动主页面",
        "default_chapter": "主页",
        "render": lambda content, slide_id: f"""<div class="slide slide-03" data-slide="{slide_id}">
    <div class="gsp-logo gsp-logo-white" style="top: 40px; left: 60px; font-size: 48px;">GSP®</div>
    <div class="left-section">
        <div class="main-title">{_esc_br(content.get('event_name', 'XXX群7月份'))}</div>
        <div class="date">{_esc(content.get('date', '2026年7月X日'))}</div>
    </div>
    <div class="right-section">
        <div class="car-images"></div>
        <div class="wave-overlay"></div>
    </div>
    <div class="website-url website-url-white" style="left: 80px; transform: none;">www.gsp.cn</div>
    <div class="page-indicator page-indicator-white">Page No -</div>
</div>""",
    },

    "home-bg": {
        "label": "主页（背景图）",
        "icon": "🏞️",
        "desc": "活动主页面（背景图版）",
        "default_title": "活动主页面",
        "default_chapter": "主页",
        "render": lambda content, slide_id: f"""<div class="slide slide-67" data-slide="{slide_id}">
    <div class="gsp-logo gsp-logo-white" style="top: 40px; left: 60px; font-size: 48px; z-index: 2;">GSP®</div>
    <div class="left-section">
        <div class="main-title">{_esc_br(content.get('event_name', '总部综合2群7月份'))}</div>
        <div class="date">{_esc(content.get('date', '2026年7月X日'))}</div>
    </div>
    <div class="website-url website-url-white" style="left: 80px; transform: none; z-index: 2;">www.gsp.cn</div>
    <div class="page-indicator page-indicator-white">Page No -</div>
</div>""",
    },

    "blue": {
        "label": "章节页(蓝)",
        "icon": "🔵",
        "desc": "蓝色渐变背景的章节分隔页",
        "default_title": "新章节",
        "default_chapter": "未分类",
        "render": lambda content, slide_id: f"""<div class="slide template-blue" data-slide="{slide_id}">
    <div class="gsp-logo gsp-logo-white">GSP®</div>
    <div class="title">{_esc(content.get('title', '章节标题'))}</div>
    <div class="subtitle">{_esc(content.get('subtitle', ''))}</div>
    <div class="page-indicator page-indicator-white">Page No -</div>
</div>""",
    },

    "chapter-fancy": {
        "label": "章节页(精美)",
        "icon": "✨",
        "desc": "带图片的章节分隔页",
        "default_title": "新章节",
        "default_chapter": "未分类",
        "render": lambda content, slide_id: f"""<div class="slide slide-20" data-slide="{slide_id}">
    <div class="gsp-logo gsp-logo-white">GSP®</div>
    <div class="content-left">
        <div class="chapter-number">{_esc(content.get('chapter_num', '01'))}</div>
        <div class="chapter-title">{_esc(content.get('title', '章节标题'))}</div>
        <div class="chapter-subtitle">{_esc(content.get('subtitle', ''))}</div>
    </div>
    <div class="image-section">
        <div class="car-image"></div>
        <div class="diagonal-cut"></div>
    </div>
    <div class="website-url website-url-white" style="right: 30px; left: auto; transform: none;">www.gsp.cn</div>
    <div class="page-indicator page-indicator-white">Page No -</div>
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

    "rules": {
        "label": "纪律页",
        "icon": "📋",
        "desc": "深色背景的学习纪律页面",
        "default_title": "纪律须知",
        "default_chapter": "纪律须知",
        "render": lambda content, slide_id: _render_rules(content, slide_id),
    },

    "ranking": {
        "label": "排行榜",
        "icon": "🏆",
        "desc": "前三名排行榜页面",
        "default_title": "排行榜",
        "default_chapter": "家书表彰",
        "render": lambda content, slide_id: _render_ranking(content, slide_id),
    },

    "speaker": {
        "label": "宣讲员",
        "icon": "🎤",
        "desc": "宣讲员介绍卡片",
        "default_title": "宣讲员介绍",
        "default_chapter": "宣讲",
        "render": lambda content, slide_id: f"""<div class="slide" data-slide="{slide_id}" style="background: #003366; flex-direction: row; padding: 80px;">
    <div class="gsp-logo gsp-logo-white">GSP®</div>
    <div style="flex: 1; border: 3px solid white; border-radius: 16px; padding: 50px; display: flex; flex-direction: column; justify-content: center;">
        <div style="width: 60px; height: 60px; border: 3px solid white; border-radius: 8px; margin-bottom: 40px; display: flex; align-items: center; justify-content: center;">
            <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2">
                <rect x="3" y="3" width="18" height="18" rx="2"/>
                <line x1="9" y1="9" x2="15" y2="9"/>
                <line x1="9" y1="13" x2="15" y2="13"/>
            </svg>
        </div>
        <div style="font-size: 56px; font-weight: bold; color: white; margin-bottom: 30px;">宣讲员：{_esc(content.get('name', 'XXX'))}</div>
        <div style="font-size: 28px; color: rgba(255,255,255,0.9); margin-bottom: 10px;">部门：{_esc(content.get('department', 'XX'))}</div>
        <div style="font-size: 28px; color: rgba(255,255,255,0.9);">宣讲主题：{_esc(content.get('topic', '《宣讲主题》'))}</div>
    </div>
    <div style="width: 350px; background: rgba(100,150,200,0.5); border-radius: 12px; margin-left: 40px; display: flex; align-items: center; justify-content: center; color: white; font-size: 18px;">照片</div>
    <div class="page-indicator page-indicator-white">Page No -</div>
</div>""",
    },

    "quiz": {
        "label": "问答题",
        "icon": "❓",
        "desc": "单项选择题页面",
        "default_title": "新题目",
        "default_chapter": "知识问答",
        "render": lambda content, slide_id: _render_quiz(content, slide_id),
    },

    "ending": {
        "label": "结束页",
        "icon": "🎉",
        "desc": "感谢页，含公司信息和联系方式",
        "default_title": "结束页",
        "default_chapter": "结束",
        "render": lambda content, slide_id: f"""<div class="slide slide-66" data-slide="{slide_id}">
    <div class="background-image"></div>
    <div class="gsp-logo gsp-logo-white" style="top: 30px; right: 40px; font-size: 42px;">GSP®</div>
    <div class="content">
        <div class="thanks-text">THANKS</div>
        <div class="company-name">{_esc(content.get('company', 'GSP AUTOMOTIVE GROUP'))}</div>
        <div class="contact-info">
            {_render_ending_address(content.get('address', ''))}
        </div>
        <div class="social-links">
            <div class="social-item"><div class="social-icon">f</div><div class="social-label">GSP Facebook</div></div>
            <div class="social-item"><div class="social-icon">in</div><div class="social-label">GSP Linkedin</div></div>
            <div class="social-item"><div class="social-icon">▶</div><div class="social-label">GSP Youtube</div></div>
        </div>
    </div>
    <div class="website-url website-url-white" style="left: 80px; transform: none;">www.gsp.cn</div>
    <div class="page-indicator page-indicator-white">Page No -</div>
</div>""",
    },
}

TEMPLATE_ORDER = [
    "video", "image", "white", "blue", "chapter-fancy", "quiz",
    "seating", "checkin", "home", "home-bg", "rules",
    "ranking", "speaker", "ending",
]


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


def _render_seating(content: Dict[str, Any], slide_id: str) -> str:
    labels = content.get("labels", ["A1", "A2", "A3", "A4", "B1", "B2", "B3", "B4", "C1", "C2", "C3", "C4"])
    seats_html = "".join(f'<div class="seat">{_esc(label)}</div>' for label in labels)
    return f"""<div class="slide slide-01b" data-slide="{slide_id}">
    <div class="header-bar">{_esc(content.get('header', '请按照座位分布依次落座'))}</div>
    <div class="content">
        <div class="podium">讲台</div>
        <div class="seating-area">{seats_html}</div>
    </div>
    <div class="page-indicator">Page No -</div>
</div>"""


def _render_rules(content: Dict[str, Any], slide_id: str) -> str:
    rules = content.get("rules", [
        "（一）第一条纪律要求",
        "（二）第二条纪律要求",
    ])
    rules_html = "".join(f'<p>{_esc(rule)}</p>' for rule in rules)
    return f"""<div class="slide slide-05" data-slide="{slide_id}">
    <div class="gsp-logo gsp-logo-white" style="top: 20px; right: 30px;">冠盛学堂<br><span style="font-size: 14px;">GSP INSTITUTE</span></div>
    <div class="section-header">
        <div class="section-title">{_esc(content.get('title', '线下学习会纪律'))}</div>
    </div>
    <div class="rules-content">
        <div class="rules-text">
            {rules_html}
        </div>
        <div class="warning-cards">
            <div class="warning-card yellow">
                <div class="card-title">警告</div>
                <div class="card-desc">若再次违反学习会纪律，将记红牌，并扣除学习积分5分</div>
            </div>
            <div class="warning-card red">
                <div class="card-title">扣分</div>
                <div class="card-desc">违反学习会纪律两次及以上，记红牌，并扣除学习积分5分</div>
            </div>
        </div>
    </div>
    <div class="page-indicator page-indicator-white">Page No -</div>
</div>"""


def _render_ranking(content: Dict[str, Any], slide_id: str) -> str:
    rankings = content.get("rankings", [
        {"rank": 1, "name": "第一名", "score": "XXX分"},
        {"rank": 2, "name": "第二名", "score": "XXX分"},
        {"rank": 3, "name": "第三名", "score": "XXX分"},
    ])
    rank_classes = ["gold", "silver", "bronze"]
    items_html = ""
    for i, r in enumerate(rankings):
        cls = rank_classes[i] if i < 3 else "gold"
        items_html += f"""<div class="ranking-item">
            <div class="rank-number {cls}">{r.get('rank', i+1)}</div>
            <div class="rank-name">{_esc(r.get('name', ''))}</div>
            <div class="rank-score">{_esc(r.get('score', ''))}</div>
        </div>"""
    return f"""<div class="slide slide-15" data-slide="{slide_id}">
    <div class="gsp-logo">GSP®</div>
    <div class="title">{_esc(content.get('title', '排行榜'))}</div>
    <div class="ranking-list">
        {items_html}
    </div>
    <div class="page-indicator">Page No -</div>
</div>"""


def _render_quiz(content: Dict[str, Any], slide_id: str) -> str:
    question = content.get("question", "题目内容？")
    options = content.get("options", ["A. 选项一", "B. 选项二", "C. 选项三", "D. 选项四"])
    answer = content.get("answer", "A")
    options_html = "".join(f'<div class="option">{_esc(opt)}</div>' for opt in options)
    return f"""<div class="slide slide-30" data-slide="{slide_id}">
    <div class="gsp-logo">GSP®</div>
    <div class="quiz-header">{_esc(content.get('header', '答对题目获得相应积分，答错不扣分，鼓励全员积极参与挑战。每题10分，共15题。'))}</div>
    <div class="quiz-section">{_esc(content.get('section', '一、单项选择题（每题10分，共15题）'))}</div>
    <div class="question">{_esc(question)}</div>
    <div class="options">
        {options_html}
    </div>
    <div class="answer">答案：{_esc(answer)}</div>
    <div class="page-indicator">Page No -</div>
</div>"""


def _render_ending_address(address: Any) -> str:
    if not address:
        return "<p>+86(0)577 86292929</p><p>No. 1, Niushan South Road, Wutian Subdistrict,</p><p>Ouhai District, Wenzhou, Zhejiang, China</p>"
    if isinstance(address, str):
        return "".join(f"<p>{_esc(line)}</p>" for line in address.split("\n") if line.strip())
    if isinstance(address, list):
        return "".join(f"<p>{_esc(line)}</p>" for line in address if line)
    return f"<p>{_esc(address)}</p>"


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
