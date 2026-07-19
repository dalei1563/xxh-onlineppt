"""端到端冒烟测试：删除旧数据库后在全新进程运行。"""
import os, sys

# 删除旧数据库（在导入 main 之前）
for f in ['data/gsp_scores.db', 'data/gsp_scores.db-shm', 'data/gsp_scores.db-wal']:
    try:
        os.remove(f)
    except FileNotFoundError:
        pass

from fastapi.testclient import TestClient
from main import app
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
        print(f'[HTTP] /api/templates -> {len(templates)} templates')

        # 5. 单页渲染
        first_id = order[0]
        r = client.get(f'/api/slides/{first_id}/render')
        assert r.status_code == 200
        print(f'[HTTP] /api/slides/{first_id}/render -> ok')

        # 6. 创建新幻灯片
        r = client.post('/api/slides/create', json={
            'type': 'white',
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
        new_order = [new_id] + [s for s in r.json() if s != new_id]
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
    print('\n✅ 所有冒烟测试通过')
