"""端到端冒烟测试：使用临时数据库，不触碰活动现场数据。"""
import atexit
import os
import shutil
import tempfile


_test_data_dir = tempfile.mkdtemp(prefix="gsp-smoke-")
os.environ["GSP_DB_PATH"] = os.path.join(_test_data_dir, "gsp_scores.db")
os.environ["THUMBNAIL_WARMUP"] = "false"
atexit.register(lambda: shutil.rmtree(_test_data_dir, ignore_errors=True))

from fastapi.testclient import TestClient
from main import app
from db.database import SessionLocal
from db.models import SlideMeta
from services.slide_service import slide_service
from state.presentation import presentation_state

def test_http():
    with TestClient(app) as client:
        # 1. 幻灯片顺序
        r = client.get('/api/slides/order')
        assert r.status_code == 200
        order = r.json()
        assert len(order) > 0, '幻灯片顺序为空'
        print(f'[HTTP] /api/slides/order -> {len(order)} slides')

        # 2. 所有幻灯片元数据
        r = client.get('/api/slides')
        assert r.status_code == 200
        slides = r.json()
        assert len(slides) == len(order)
        print(f'[HTTP] /api/slides -> {len(slides)} metadata records')

        # 3. 整页渲染
        r = client.get('/api/slides/full')
        assert r.status_code == 200
        assert '<div class="slide' in r.text
        print(f'[HTTP] /api/slides/full -> rendered {len(r.text)} chars')

        # 4. 模板列表
        r = client.get('/api/templates')
        assert r.status_code == 200
        templates = r.json()
        assert len(templates) > 0
        assert any(t['type'] == 'external' for t in templates)
        assert not any(t['type'] == 'ai_chat' for t in templates)
        print(f'[HTTP] /api/templates -> {len(templates)} templates')

        controller_html = client.get('/controller.html').text
        assert 'data-tab="ai"' not in controller_html
        assert 'ai_realtime_' not in controller_html
        assert 'data-tab="scores"' not in controller_html
        assert 'data-tab="game"' not in controller_html
        assert "score_update" not in controller_html
        assert "game_control" not in controller_html
        assert controller_html.index('id="prevBtn"') < controller_html.index('id="firstBtn"')
        assert "this.store.onSlidesChange" in controller_html
        assert "self.jumpToSlide(chapter.firstSlideId)" in controller_html
        assert 'id="carouselCurrentImage"' in controller_html
        assert "renderCarousel" in controller_html
        assert "/thumbnail" in controller_html
        assert 'id="jumpInput"' not in controller_html
        assert 'id="qrcode"' not in controller_html
        assert "qrcode.min.js" not in controller_html
        assert "opacity: 0 !important" in controller_html
        assert "delete image.dataset.slideId" in controller_html
        assert "image.onload = null" in controller_html
        assert "card.disabled = true" in controller_html

        slides_html = client.get('/slides.html').text
        assert "position: relative !important" in slides_html
        assert "top: auto !important" in slides_html
        assert "msg.type === 'presentation_key'" in slides_html
        assert "getFullscreenDocument" in slides_html
        assert 'onclick="app.doToggleFullscreen()"' in slides_html
        assert 'id="fullscreenPrompt"' in slides_html
        assert 'id="__slideFrameA"' in slides_html
        assert 'id="__slideFrameB"' in slides_html
        assert "standbyFrame" in slides_html
        assert "_waitForFrameReady" in slides_html
        assert "_commitPreparedFrame" in slides_html

        slides_css = client.get('/static/css/slides.css').text
        assert "slideFadeIn" not in slides_css
        assert ".slide.active" not in slides_css or "animation:" not in slides_css.split(".slide.active", 1)[1].split("}", 1)[0]

        # 游戏与积分接口已从核心服务完整移除。
        assert client.get('/api/teams').status_code == 404
        assert client.post('/api/game/control', json={'action': 'start'}).status_code == 404

        # 5. 单页渲染
        first_id = order[0]
        r = client.get(f'/api/slides/{first_id}/render')
        assert r.status_code == 200
        print(f'[HTTP] /api/slides/{first_id}/render -> ok')

        # 5b. 视频页统一关闭循环并支持点击暂停/继续
        video_slide = next((s for s in slides if s['type'] == 'video'), None)
        if video_slide:
            assert not video_slide['file_path'].lower().endswith('.html')
            r = client.get(f"/api/slides/{video_slide['slide_id']}/page")
            assert r.status_code == 200
            assert "v.loop = false" in r.text
            assert "if (v.ended) return" in r.text
            assert "createGain()" in r.text
            assert "set_volume_gain" in r.text
            assert "type: 'presentation_key'" in r.text
            assert "e.stopPropagation()" in r.text
            assert "volumeGain: configuredGain" in r.text
            assert " muted loop" not in r.text
            assert f'mediaVideo-{video_slide["slide_id"]}' in r.text
            print(f"[HTTP] video page behavior -> ok")

            # 每张视频页独立持久化 0~4 倍音量增益。
            r = client.get(f"/api/slides/{video_slide['slide_id']}/volume")
            assert r.status_code == 200
            assert r.json()['volume_gain'] == 1.0
            r = client.put(
                f"/api/slides/{video_slide['slide_id']}/volume",
                json={"volume_gain": 2.35},
            )
            assert r.status_code == 200, r.text
            assert r.json()['volume_gain'] == 2.35
            r = client.get(f"/api/slides/{video_slide['slide_id']}/page")
            assert "var configuredGain = 2.3500;" in r.text
            r = client.put(
                f"/api/slides/{video_slide['slide_id']}/volume",
                json={"volume_gain": 20},
            )
            assert r.status_code == 200
            assert r.json()['volume_gain'] == 20
            r = client.put(
                f"/api/slides/{video_slide['slide_id']}/volume",
                json={"volume_gain": 20.01},
            )
            assert r.status_code == 422
            print("[HTTP] per-slide video volume persistence -> ok")

            # 旧数据库即使仍保存已删除的 HTML 包装页，也能在启动阶段映射到真实视频。
            db = SessionLocal()
            try:
                legacy = db.query(SlideMeta).filter(SlideMeta.slide_id == video_slide['slide_id']).first()
                legacy.file_path = "slides/slide_intro.html"
                db.commit()
                assert slide_service.migrate_legacy_video_slides(db) == 1
                db.refresh(legacy)
                assert legacy.file_path == "intro_video.mp4"
            finally:
                db.close()
            print("[HTTP] legacy video migration -> ok")

        # 5c. 历史内嵌 AI 页面会迁移为通用 external iframe，不再进入核心 WS。
        external_slide = next((s for s in slides if s['type'] == 'external'), None)
        assert external_slide is not None
        assert external_slide['file_path'] == 'service://ai-voice'
        r = client.get(f"/api/slides/{external_slide['slide_id']}/page")
        assert r.status_code == 200
        assert 'class="external-service-frame"' in r.text
        assert 'http://127.0.0.1:8100/' in r.text
        assert "source: 'xxh-presentation'" in r.text
        assert "presentation.leave" in r.text
        assert "ai_realtime_start" not in r.text

        db = SessionLocal()
        try:
            legacy_ai = (
                db.query(SlideMeta)
                .filter(SlideMeta.slide_id == external_slide['slide_id'])
                .first()
            )
            legacy_ai.type = 'ai_chat'
            legacy_ai.file_path = 'slides/slide_s-ec889a11.html'
            db.commit()
            assert slide_service.migrate_ai_chat_slides(db) == 1
            db.refresh(legacy_ai)
            assert legacy_ai.type == 'external'
            assert legacy_ai.file_path == 'service://ai-voice'
        finally:
            db.close()
        print("[HTTP] external AI service migration and bridge -> ok")

        # 通用外部页面创建接口只接受 http/https。
        r = client.post('/api/slides/create', json={
            'type': 'external',
            'title': '外部服务测试',
            'source_url': 'javascript:alert(1)',
        })
        assert r.status_code == 400
        r = client.post('/api/slides/create', json={
            'type': 'external',
            'title': '外部服务测试',
            'source_url': 'https://example.com/service',
        })
        assert r.status_code == 200, r.text
        external_test_id = r.json()['slide_id']
        r = client.get(f'/api/slides/{external_test_id}/page')
        assert r.status_code == 200
        assert 'https://example.com/service' in r.text
        r = client.delete(f'/api/slides/{external_test_id}')
        assert r.status_code == 200
        print("[HTTP] generic external slide create/delete -> ok")

        # 6. 创建新幻灯片
        r = client.post('/api/slides/create', json={
            # image 类型不写入 static/slides，确保测试不修改活动素材。
            'type': 'image',
            'title': '冒烟测试页',
        })
        assert r.status_code == 200, r.text
        new_id = r.json()['slide_id']
        print(f'[HTTP] POST /api/slides/create -> {new_id}')

        # 7. 创建后顺序+1
        r = client.get('/api/slides/order')
        assert len(r.json()) == len(order) + 1
        print(f'[HTTP] order after create -> {len(r.json())} slides')

        # 8. 更新标题
        r = client.put(f'/api/slides/{new_id}', json={
            'title': '更新后的标题',
        })
        assert r.status_code == 200, r.text
        print(f'[HTTP] PUT /api/slides/{new_id} -> ok')

        # 9. 排序（把新页移到最前）
        new_order = [new_id] + order
        r = client.put('/api/slides/reorder', json={'order': new_order})
        assert r.status_code == 200, r.text
        print(f'[HTTP] PUT /api/slides/reorder -> ok')

        # 10. 删除测试页
        r = client.delete(f'/api/slides/{new_id}')
        assert r.status_code == 200, r.text
        print(f'[HTTP] DELETE /api/slides/{new_id} -> ok')

        r = client.get('/api/slides/order')
        assert len(r.json()) == len(order)
        print(f'[HTTP] order after delete -> {len(r.json())} slides')

def test_ws():
    with TestClient(app) as client:
        with client.websocket_connect('/ws') as ws:
            # 等待服务端发送的 PresentationState 与 clients_count
            data = ws.receive_json()
            assert data['type'] == 'presentation_state', data
            assert data['total'] == presentation_state.total_slides
            assert 'is_game_active' not in data
            assert 'current_round' not in data
            print(f"[WS] initial presentation_state: total={data['total']}")

            data = ws.receive_json()
            assert data['type'] == 'clients_count', data
            print(f"[WS] clients_count: {data['count']}")

            # 请求下一页
            ws.send_json({'type': 'next'})
            data = ws.receive_json()
            assert data['type'] == 'goto', data
            print(f"[WS] next -> {data['slide']}")

            # 直接跳转
            target = presentation_state.slide_order[2]
            ws.send_json({'type': 'goto', 'slide': target})
            data = ws.receive_json()
            assert data['type'] == 'goto'
            assert data['slide'] == target
            print(f"[WS] goto({target}) -> ok")

if __name__ == '__main__':
    test_http()
    test_ws()
    print('\n所有冒烟测试通过')
