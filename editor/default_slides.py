"""Version-controlled fallback manifest for the activity deck.

The checked-in SQLite snapshot is the canonical deck for this event.  This
manifest mirrors it so that deleting the local database still produces the
same 80-slide structure on the next start.
"""
from typing import Dict, Iterable, List


DEFAULT_SLIDES: List[Dict[str, str]] = []


def _add(slide_id: str, title: str, slide_type: str, chapter: str, file_path: str) -> None:
    DEFAULT_SLIDES.append({
        "slide_id": slide_id,
        "title": title,
        "type": slide_type,
        "chapter": chapter,
        "file_path": file_path,
    })


def _add_numbers(numbers: Iterable[int], chapter: str) -> None:
    for number in numbers:
        _add(str(number), f"第{number}页", "image", chapter, f"slides/slide_{number}.html")


# Keep this order exactly aligned with data/gsp_scores.db.
_add_numbers([1, 2, 4, 5, 6], "签到")
_add("3", "第3页", "image", "活动主页面", "slides/slide_3.html")
_add("intro", "第intro页", "video", "活动主页面", "intro_video.mp4")
_add_numbers([9, 10], "宣讲员宣讲")
_add_numbers([11, 12], "家书表彰")
_add_numbers(range(13, 20), "6月数据回顾")

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

_add_numbers([20, 21], "文化共有")
_add_numbers([22], "团队王者宣战")
_add_numbers(range(23, 40), "第一赛季：团队排位赛")
_add_numbers(range(40, 57), "第二赛季：冠军联盟")
_add_numbers([57, 58], "颁奖环节")
_add_numbers(range(59, 65), "结束")
_add("s-830e1be6", "基础模板演示", "base", "模板测试", "slides/slide_s-830e1be6.html")
_add("s-ec889a11", "AI语音对话", "external", "AI互动", "service://ai-voice")
_add("s-9ce10515", "新章节", "white", "新章节", "slides/slide_s-9ce10515.html")
