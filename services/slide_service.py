"""
Slide service - 幻灯片领域的唯一业务入口。
负责：元数据 CRUD、排序、服务端渲染、种子数据初始化。
"""
import json
import uuid
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

from db.models import SlideMeta
from editor.models import SlideInfo
from editor.templates import render_slide, get_skeleton, TEMPLATES


# ====== 种子数据：全部 67 页的元数据 ======
# 顺序与原始 slideOrder 一致
SLIDE_SEED_DATA = [
    # 1: 视频开场
    ("1",  "视频开场",          "video",   "开场",     {"video_src": "/static/intro_video.mp4"}),

    # 2: 座位安排
    ("1b", "座位安排",          "seating", "签到",     {"rows": 3, "cols": 4, "labels": ["A1","A2","A3","A4","B1","B2","B3","B4","C1","C2","C3","C4"]}),

    # 3: 签到码
    ("2",  "学习会签到码",      "checkin", "签到",     {}),

    # 4: 主页面
    ("3",  "活动主页面",        "home",    "主页",     {"event_name": "XXX群7月份线下学习会", "date": "2026年7月X日"}),

    # 5-7: 纪律须知
    ("4",  "学习会须知",        "blue",    "纪律须知", {"title": "学习会须知", "subtitle": "请认真阅读以下内容"}),
    ("5",  "线下学习会纪律",    "rules",   "纪律须知", {"rules": [
        "（一）学习会需提前报名，学习会开始前5分钟到达现场进行签到。迟到将记为黄牌（警告）一次，早退视为缺勤。",
        "（二）学习期间，严禁刷手机、看抖音等与学习无关的行为。若发现有人在学习期间进行上述行为，将记为黄牌一次，二次黄牌记一次红牌并扣学习积分5分。",
        "（三）学习期间，若因特殊情况需离开会场或接听电话，时间不得超过15分钟超过此时间限制者，将视为无效参会，不加分。",
        "（四）请勿携带笔记本电脑",
    ]}),
    ("6",  "学习会流程介绍",    "white",   "纪律须知", {"title": "学习会流程介绍", "body": "本次学习会包含以下环节：开场签到、6月份家书前3名表彰、学习会纪律宣导、宣讲员分享、互动问答环节、总结与结束"}),

    # 8-9: 签到章节页 + 签到方式
    ("7",  "01 开场签到",       "blue",    "签到",     {"title": "01", "subtitle": "开场签到"}),
    ("8",  "签到方式",          "white",   "签到",     {"title": "签到方式", "body": "请扫描屏幕上的二维码完成签到"}),

    # 10-13: 家书表彰
    ("9",  "02 家书前3名",      "blue",    "家书表彰", {"title": "02", "subtitle": "6月份家书前3名"}),
    ("10", "宣讲员介绍",        "speaker", "家书表彰", {"name": "XXX", "department": "XX", "topic": "《从搬水小事看团队精神》"}),
    ("15", "6月份家书排行榜",   "ranking", "家书表彰", {"rankings": [
        {"rank": 1, "name": "第一名", "score": "XXX分"},
        {"rank": 2, "name": "第二名", "score": "XXX分"},
        {"rank": 3, "name": "第三名", "score": "XXX分"},
    ]}),
    ("16", "颁奖环节",          "white",   "家书表彰", {"title": "颁奖环节", "body": "请获奖者上台领奖"}),

    # 14-17: 宣讲
    ("11", "03 宣讲环节",       "blue",    "宣讲",     {"title": "03", "subtitle": "宣讲环节"}),
    ("12", "宣讲主题",          "white",   "宣讲",     {"title": "宣讲主题", "body": "《从搬水小事看团队精神》"}),
    ("13", "团队精神的重要性",  "white",   "宣讲",     {"title": "团队精神的重要性", "body": "团队精神是企业文化的重要组成部分，它体现在日常工作中的每一个细节。从搬水这样的小事，我们可以看到团队协作的力量。"}),
    ("14", "04 互动问答",       "blue",    "宣讲",     {"title": "04", "subtitle": "互动问答"}),

    # 18-28: 文化表情包
    ("17", "05 文化共有",       "blue",    "文化表情包", {"title": "05", "subtitle": "文化共有，知行共振"}),
    ("18", "文化表情包比拼",    "white",   "文化表情包", {"title": "文化表情包比拼", "body": "各小组准备文化表情包进行展示和比拼"}),
    ("19", "比拼规则",          "white",   "文化表情包", {"title": "比拼规则", "body": "每组准备3-5个文化表情包；展示时间：每组3分钟；评分标准：创意性、文化契合度、表现力；评委打分，评选最佳创意奖"}),
    ("20", "05 章节页",         "chapter-fancy", "文化表情包", {"chapter_num": "05", "title": "文化共有，知行共振", "subtitle": "——文化表情包比拼"}),
    ("21", "小组展示",          "white",   "文化表情包", {"title": "小组展示", "body": "请各小组依次上台展示文化表情包"}),
    ("22", "第一组展示",        "white",   "文化表情包", {"title": "第一组展示", "body": ""}),
    ("23", "第二组展示",        "white",   "文化表情包", {"title": "第二组展示", "body": ""}),
    ("24", "第三组展示",        "white",   "文化表情包", {"title": "第三组展示", "body": ""}),
    ("25", "第四组展示",        "white",   "文化表情包", {"title": "第四组展示", "body": ""}),
    ("26", "第五组展示",        "white",   "文化表情包", {"title": "第五组展示", "body": ""}),
    ("27", "评分环节",          "white",   "文化表情包", {"title": "评分环节", "body": "请评委为各组打分"}),

    # 29-45: 知识问答
    ("28", "06 知识问答",       "blue",    "知识问答", {"title": "06", "subtitle": "知识问答"}),
    ("29", "问答规则",          "white",   "知识问答", {"title": "问答规则", "body": "答对题目获得相应积分，答错不扣分，鼓励全员积极参与挑战。每题10分，共15题。"}),
    ("30", "第1题", "quiz", "知识问答", {"question": "以下哪项是GSP的核心价值观？", "options": ["A. 追求利润最大化", "B. 客户至上，品质第一", "C. 快速扩张", "D. 降低成本"], "answer": "B"}),
    ("31", "第2题", "quiz", "知识问答", {"question": "学习会迟到将受到什么处罚？", "options": ["A. 直接扣分", "B. 记黄牌一次", "C. 通报批评", "D. 无处罚"], "answer": "B"}),
    ("32", "第3题", "quiz", "知识问答", {"question": "学习期间手机使用规定是？", "options": ["A. 可以静音使用", "B. 严禁刷手机、看抖音", "C. 可以回复紧急消息", "D. 无限制"], "answer": "B"}),
    ("33", "第4题", "quiz", "知识问答", {"question": "离开会场接听电话的时间限制是？", "options": ["A. 5分钟", "B. 10分钟", "C. 15分钟", "D. 无限制"], "answer": "C"}),
    ("34", "第5题", "quiz", "知识问答", {"question": "二次黄牌的处罚是？", "options": ["A. 再记一次黄牌", "B. 记红牌并扣5分", "C. 通报批评", "D. 无处罚"], "answer": "B"}),
    ("35", "第6题", "quiz", "知识问答", {"question": "持续拼命工作的必要条件是什么？", "options": ["A. 高薪", "B. 舒适的工作环境", "C. 喜欢上现在所从事的工作", "D. 轻松的工作氛围"], "answer": "C"}),
    ("36", "第7题", "quiz", "知识问答", {"question": "GSP的全称是？", "options": ["A. 广州汽车集团", "B. 冠盛汽车零部件集团", "C. 国盛汽车集团", "D. 光速汽车集团"], "answer": "B"}),
    ("37", "第8题", "quiz", "知识问答", {"question": "学习会开始前几分钟需要签到？", "options": ["A. 3分钟", "B. 5分钟", "C. 10分钟", "D. 15分钟"], "answer": "B"}),
    ("38", "第9题", "quiz", "知识问答", {"question": "以下哪项行为不被允许？", "options": ["A. 记笔记", "B. 提问", "C. 携带笔记本电脑", "D. 参与讨论"], "answer": "C"}),
    ("39", "第10题", "quiz", "知识问答", {"question": "2张以上红牌会被通报到哪个会议？", "options": ["A. 周例会", "B. 集团文化交流共创会", "C. 月度总结会", "D. 年度大会"], "answer": "B"}),
    ("40", "第11题", "quiz", "知识问答", {"question": "GSP公司位于哪个城市？", "options": ["A. 杭州", "B. 宁波", "C. 温州", "D. 上海"], "answer": "C"}),
    ("41", "第12题", "quiz", "知识问答", {"question": "早退在学习会中被视为？", "options": ["A. 警告", "B. 缺勤", "C. 迟到", "D. 请假"], "answer": "B"}),
    ("42", "第13题", "quiz", "知识问答", {"question": "违反纪律两次及以上会被扣多少分？", "options": ["A. 3分", "B. 5分", "C. 10分", "D. 不扣分"], "answer": "B"}),
    ("43", "第14题", "quiz", "知识问答", {"question": "GSP的官方网站是？", "options": ["A. www.gsp.com", "B. www.gsp.cn", "C. www.gsp.net", "D. www.gsp.com.cn"], "answer": "B"}),
    ("44", "第15题", "quiz", "知识问答", {"question": "冠盛学堂的英文名称是？", "options": ["A. GSP School", "B. GSP Institute", "C. GSP Academy", "D. GSP University"], "answer": "B"}),

    # 46-67: 结束
    ("45", "07 总结与结束",     "blue",    "结束",     {"title": "07", "subtitle": "总结与结束"}),
    ("46", "本次学习会总结",    "white",   "结束",     {"title": "本次学习会总结", "body": "学习会纪律宣导完成、6月份家书前3名表彰、宣讲员分享、文化表情包比拼、知识问答环节"}),
    ("47", "下期预告",          "white",   "结束",     {"title": "下期预告", "body": "敬请期待8月份学习会"}),
    ("48", "感谢参与",          "white",   "结束",     {"title": "感谢参与", "body": "感谢大家的积极参与！"}),
    ("49", "补充内容 1",        "white",   "结束",     {"title": "补充内容 1", "body": ""}),
    ("50", "补充内容 2",        "white",   "结束",     {"title": "补充内容 2", "body": ""}),
    ("51", "补充内容 3",        "white",   "结束",     {"title": "补充内容 3", "body": ""}),
    ("52", "补充内容 4",        "white",   "结束",     {"title": "补充内容 4", "body": ""}),
    ("53", "补充内容 5",        "white",   "结束",     {"title": "补充内容 5", "body": ""}),
    ("54", "补充内容 6",        "white",   "结束",     {"title": "补充内容 6", "body": ""}),
    ("55", "补充内容 7",        "white",   "结束",     {"title": "补充内容 7", "body": ""}),
    ("56", "补充内容 8",        "white",   "结束",     {"title": "补充内容 8", "body": ""}),
    ("57", "补充内容 9",        "white",   "结束",     {"title": "补充内容 9", "body": ""}),
    ("58", "补充内容 10",       "white",   "结束",     {"title": "补充内容 10", "body": ""}),
    ("59", "补充内容 11",       "white",   "结束",     {"title": "补充内容 11", "body": ""}),
    ("60", "补充内容 12",       "white",   "结束",     {"title": "补充内容 12", "body": ""}),
    ("61", "补充内容 13",       "white",   "结束",     {"title": "补充内容 13", "body": ""}),
    ("62", "补充内容 14",       "white",   "结束",     {"title": "补充内容 14", "body": ""}),
    ("63", "补充内容 15",       "white",   "结束",     {"title": "补充内容 15", "body": ""}),
    ("64", "补充内容 16",       "white",   "结束",     {"title": "补充内容 16", "body": ""}),
    ("65", "补充内容 17",       "white",   "结束",     {"title": "补充内容 17", "body": ""}),
    ("66", "结束页",            "ending",  "结束",     {"company": "GSP AUTOMOTIVE GROUP", "address": "No. 1, Niushan South Road, Wutian Subdistrict, Ouhai District, Wenzhou, Zhejiang, China", "phone": "+86(0)577 86292929"}),
    # 67: 主页（背景图版）
    ("67", "活动主页面（背景图）", "home-bg", "主页",     {"event_name": "总部综合2群7月份线下学习会", "date": "2026年7月X日"}),
]


class SlideService:
    """幻灯片领域服务"""

    def seed_slides(self, db: Session):
        """初始化种子数据（只在数据库为空时执行）"""
        existing = db.query(SlideMeta).count()
        if existing > 0:
            return

        for i, (slide_id, title, slide_type, chapter, content) in enumerate(SLIDE_SEED_DATA):
            slide = SlideMeta(
                slide_id=slide_id,
                title=title,
                type=slide_type,
                chapter=chapter,
                display_order=i,
                content_json=json.dumps(content, ensure_ascii=False),
            )
            db.add(slide)
        db.commit()

    def get_all_slides(self, db: Session) -> List[SlideInfo]:
        """获取所有幻灯片，按排序顺序返回"""
        slides = db.query(SlideMeta).order_by(SlideMeta.display_order).all()
        return [self._to_info(s) for s in slides]

    def get_slide_order(self, db: Session) -> List[str]:
        """获取排序后的 slide_id 数组"""
        slides = db.query(SlideMeta).order_by(SlideMeta.display_order).all()
        return [s.slide_id for s in slides]

    def get_slide(self, db: Session, slide_id: str) -> Optional[SlideInfo]:
        """获取单个幻灯片"""
        slide = db.query(SlideMeta).filter(SlideMeta.slide_id == slide_id).first()
        return self._to_info(slide) if slide else None

    def get_slide_by_id(self, db: Session, slide_id: str) -> Optional[SlideMeta]:
        """获取原始 ORM 对象（用于渲染）"""
        return db.query(SlideMeta).filter(SlideMeta.slide_id == slide_id).first()

    def reorder_slides(self, db: Session, new_order: List[str]):
        """重新排序幻灯片"""
        for i, slide_id in enumerate(new_order):
            slide = db.query(SlideMeta).filter(SlideMeta.slide_id == slide_id).first()
            if slide:
                slide.display_order = i
        db.commit()

    def update_slide(self, db: Session, slide_id: str, title: str = None, chapter: str = None, content_json: dict = None) -> Optional[SlideInfo]:
        """更新幻灯片标题、章节和/或内容"""
        slide = db.query(SlideMeta).filter(SlideMeta.slide_id == slide_id).first()
        if not slide:
            return None
        if title is not None:
            slide.title = title
        if chapter is not None:
            slide.chapter = chapter
        if content_json is not None:
            slide.content_json = json.dumps(content_json, ensure_ascii=False)
        db.commit()
        db.refresh(slide)
        return self._to_info(slide)

    def delete_slide(self, db: Session, slide_id: str) -> bool:
        """删除幻灯片"""
        slide = db.query(SlideMeta).filter(SlideMeta.slide_id == slide_id).first()
        if not slide:
            return False
        db.delete(slide)
        db.commit()
        # 重新整理 display_order，避免空洞
        self._renumber_order(db)
        return True

    def create_slide(self, db: Session, slide_type: str, chapter: str = None, title: str = None, content_json: dict = None) -> Optional[SlideInfo]:
        """从模板创建新幻灯片"""
        tmpl = TEMPLATES.get(slide_type)
        if not tmpl:
            return None

        new_id = self._generate_slide_id(db)
        effective_chapter = chapter or tmpl["default_chapter"]
        effective_title = title or tmpl["default_title"]

        # 合并用户传入的内容与模板默认值
        content = content_json or {}
        # 骨架中可能需要的占位符
        content.setdefault("video_src", "/static/intro_video.mp4")

        existing_count = db.query(SlideMeta).count()
        slide = SlideMeta(
            slide_id=new_id,
            title=effective_title,
            type=slide_type,
            chapter=effective_chapter,
            display_order=existing_count,
            content_json=json.dumps(content, ensure_ascii=False),
        )
        db.add(slide)
        db.commit()
        db.refresh(slide)
        return self._to_info(slide)

    def get_chapters(self, db: Session) -> List[str]:
        """获取所有章节名称（按首次出现顺序）"""
        from sqlalchemy import func as sa_func
        chapters = db.query(SlideMeta.chapter).distinct().order_by(SlideMeta.display_order).all()
        return [c[0] for c in chapters if c[0]]

    def render_slide(self, slide: SlideMeta) -> str:
        """渲染单个幻灯片 HTML"""
        if not slide:
            return ""
        content = json.loads(slide.content_json) if slide.content_json else {}
        # 如果用户保存了原始 HTML，优先使用（保留高级模式）
        if content.get("html"):
            return content["html"]
        return render_slide(slide.type, content, slide.slide_id)

    def render_slide_by_id(self, db: Session, slide_id: str) -> str:
        """根据 slide_id 渲染 HTML"""
        slide = self.get_slide_by_id(db, slide_id)
        return self.render_slide(slide)

    def render_all_slides(self, db: Session) -> str:
        """按顺序渲染全部幻灯片 HTML"""
        slides = db.query(SlideMeta).order_by(SlideMeta.display_order).all()
        return "".join(self.render_slide(s) for s in slides)

    def _generate_slide_id(self, db: Session) -> str:
        """生成唯一 slide_id，使用 UUID 避免与现有数字 ID 冲突"""
        # 简单使用 s-前缀 + UUID 前8位
        return f"s-{uuid.uuid4().hex[:8]}"

    def _renumber_order(self, db: Session):
        """重新按 display_order 排序编号"""
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
            content_json=json.loads(slide.content_json) if slide.content_json else {},
        )


# 全局单例
slide_service = SlideService()
