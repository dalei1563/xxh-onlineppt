"""Version-controlled manifest for the built-in learning-session deck.

The SQLite database is intentionally runtime data and is not committed.  This
manifest is the recoverable source of truth used to bootstrap a fresh install.
"""
from typing import Dict, List


DEFAULT_SLIDES: List[Dict[str, str]] = []


def _add(slide_id: str, title: str, slide_type: str, chapter: str, file_path: str):
    DEFAULT_SLIDES.append({
        "slide_id": slide_id,
        "title": title,
        "type": slide_type,
        "chapter": chapter,
        "file_path": file_path,
    })


def _add_numbered(start: int, end: int, chapter: str):
    for number in range(start, end + 1):
        _add(str(number), f"第{number}页", "image", chapter, f"slides/slide_{number}.html")


# Keep the order and chapters of the activity deck independent from the local
# SQLite file, so a clean checkout produces the same presentation structure.
_add_numbered(1, 2, "签到")
_add_numbered(3, 3, "活动主页面")
_add("intro", "第intro页", "video", "活动主页面", "slides/slide_intro.html")
_add_numbered(4, 7, "学习会须知")
_add_numbered(8, 9, "开场签到")
_add_numbered(10, 12, "家书表彰")
_add_numbered(13, 19, "6月数据回顾")

for _slide_id, _title in [
    ("s-88514696", "6月群积分情况（HTML版）"),
    ("s-ba7b9b41", "6月份积分前10名（HTML版）"),
    ("s-74890002", "6月份家书前3名（HTML版）"),
    ("s-b8a29608", "6月份积分未达标情况（HTML版）"),
    ("s-fd37b442", "6月份学习会参与情况（HTML版）"),
    ("s-6ceea4ae", "6月份违规情况（HTML版）"),
    ("s-c0bb1fa9", "6月份优秀家书分享（HTML版）"),
    ("s-afd4828f", "6月群积分情况（HTML版）"),
    ("s-2050e87e", "6月份积分前10名（HTML版）"),
    ("s-2ffd9658", "6月份家书前3名（HTML版）"),
    ("s-a1576be4", "6月份积分未达标情况（HTML版）"),
    ("s-1b6156c0", "6月份学习会参与情况（HTML版）"),
    ("s-11eb9489", "6月份违规情况（HTML版）"),
    ("s-229c6818", "6月份优秀家书分享（HTML版）"),
]:
    _add(_slide_id, _title, "white", "6月数据回顾", f"slides/slide_{_slide_id}.html")

_add_numbered(20, 21, "文化共有")
_add_numbered(22, 36, "第一赛季：团队排位赛")
_add_numbered(37, 56, "第二赛季：冠军联盟")
_add_numbered(57, 58, "颁奖环节")
_add_numbered(59, 64, "结束")
_add("s-830e1be6", "基础模板演示", "base", "模板测试", "slides/slide_s-830e1be6.html")
