"""
将 PPTX 逐页导出为图片，全部替换导入在线 PPT 系统。
"""
import os
import sys
import json
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import win32com.client
from db.database import SessionLocal
from db.models import SlideMeta
from services.slide_service import SLIDES_DIR
from state.presentation import presentation_state

PPTX_PATH = r"D:\Project\学习会在线PPT\xxh-onlineppt\temp.pptx"
OUTPUT_DIR = Path(__file__).parent / "static" / "uploads"
SLIDE_W, SLIDE_H = 1920, 1080

# 章节映射（起始页, 结束页, 章节名）
CHAPTERS = [
    (1,  2,   "签到"),
    (3,  3,   "活动主页面"),
    (4,  7,   "学习会须知"),
    (8,  9,   "开场签到"),
    (10, 12,  "家书表彰"),
    (13, 19,  "6月数据回顾"),
    (20, 21,  "文化共有"),
    (22, 22,  "团队王者宣战"),
    (23, 39,  "第一赛季：团队排位赛"),
    (40, 56,  "第二赛季：冠军联盟"),
    (57, 58,  "颁奖环节"),
    (59, 64,  "结束"),
]

def chapter_of(page):
    for s, e, n in CHAPTERS:
        if s <= page <= e:
            return n
    return "未分类"

def export_pptx():
    print("[1/3] 导出 PPT 为图片...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ppt = win32com.client.Dispatch("PowerPoint.Application")
    ppt.Visible = True
    pres = None
    results = []
    try:
        pres = ppt.Presentations.Open(PPTX_PATH, WithWindow=False)
        total = pres.Slides.Count
        for i in range(1, total + 1):
            fname = f"pptx_slide_{i:02d}.png"
            fpath = os.path.join(OUTPUT_DIR, fname)
            pres.Slides(i).Export(fpath, "PNG", SLIDE_W, SLIDE_H)
            results.append((i, fname, chapter_of(i)))
            if i % 10 == 0:
                print(f"   已导出 {i}/{total}")
        print(f"   ✅ 共 {total} 页")
        return results
    finally:
        if pres:
            pres.Close()
        ppt.Quit()

def import_slides(items):
    print("[2/3] 替换数据库与文件...")
    db = SessionLocal()
    try:
        # 清空旧数据
        db.query(SlideMeta).delete()
        db.commit()
        # 清空 slides 目录
        if SLIDES_DIR.exists():
            for f in SLIDES_DIR.iterdir():
                f.unlink()
        SLIDES_DIR.mkdir(parents=True, exist_ok=True)

        for idx, (page, fname, chapter) in enumerate(items):
            slide_id = str(page)
            img_url = f"/static/uploads/{fname}"
            title = f"第{page}页"

            # 生成 image 类型 HTML 文件
            html = (
                f'<div class="slide slide-media slide-image" data-slide="{slide_id}">\n'
                f'    <img src="{img_url}" alt="全屏图片">\n'
                f'</div>'
            )
            file_path_rel = f"slides/slide_{slide_id}.html"
            abs_path = SLIDES_DIR / f"slide_{slide_id}.html"
            abs_path.write_text(html, encoding="utf-8")

            # 写入数据库元数据
            slide = SlideMeta(
                slide_id=slide_id,
                title=title,
                type="image",
                chapter=chapter,
                display_order=idx,
                file_path=file_path_rel,
            )
            db.add(slide)

        db.commit()
        print(f"   ✅ 数据库写入 {len(items)} 条记录")
        print(f"   ✅ HTML 文件已生成")

        # 更新运行状态
        order = [str(p[0]) for p in items]
        presentation_state.set_slide_order(order)
        if order:
            presentation_state.goto_slide(order[0])
        print(f"   ✅ 演示状态已同步")

    finally:
        db.close()

def verify():
    print("[3/3] 验证...")
    db = SessionLocal()
    try:
        count = db.query(SlideMeta).count()
        order = [s.slide_id for s in db.query(SlideMeta).order_by(SlideMeta.display_order).all()]
        chapter_list = db.query(SlideMeta.chapter).distinct().order_by(SlideMeta.display_order).all()
        chapters = [c[0] for c in chapter_list]
        print(f"   幻灯片总数: {count}")
        print(f"   章节数: {len(chapters)}")
        for ch in chapters:
            n = db.query(SlideMeta).filter(SlideMeta.chapter == ch).count()
            print(f"     📁 {ch}: {n} 页")
        # 检查图片文件是否存在
        missing = []
        for s in db.query(SlideMeta).all():
            if s.file_path:
                fp = Path(__file__).parent / "static" / s.file_path
                if not fp.exists():
                    missing.append(s.slide_id)
        if missing:
            print(f"   ⚠️  {len(missing)} 个文件缺失: {missing}")
        else:
            print(f"   ✅ 所有文件存在")
    finally:
        db.close()

if __name__ == "__main__":
    print("=" * 50)
    print("📥 PPT 导入工具")
    print("=" * 50)

    items = export_pptx()
    import_slides(items)
    verify()
    print("\n✅ 全部完成！")
