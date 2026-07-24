"""独立 AI 语音服务冒烟测试，不连接真实上游。"""
import os

os.environ["ZHIPU_API_KEY"] = "your_zhipu_api_key_here"

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from ai_voice_service.main import app


def test_ai_voice_service():
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "独立语音服务" in response.text
        assert "/static/ai-chat.js?v=2" in response.text

        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {
            "status": "ok",
            "service": "ai-voice",
            "version": 1,
            "configured": False,
            "active_sessions": 0,
        }

        response = client.get("/static/ai-chat.js")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith(
            ("application/javascript", "text/javascript")
        )
        assert "xxh-presentation" in response.text
        assert "presentation.leave" in response.text

        with client.websocket_connect("/ws") as websocket:
            websocket.send_json({
                "type": "ai_realtime_start",
                "audio": True,
                "mode": "realtime",
            })
            message = websocket.receive_json()
            assert message["type"] == "ai_realtime_status"
            assert message["status"] == "error"

        response = client.get("/health")
        assert response.json()["active_sessions"] == 0

        try:
            with client.websocket_connect(
                "/ws",
                headers={"origin": "https://evil.example"},
            ):
                raise AssertionError("跨来源 WebSocket 不应建立连接")
        except WebSocketDisconnect as exc:
            assert exc.code == 1008


if __name__ == "__main__":
    test_ai_voice_service()
    print("独立 AI 语音服务冒烟测试通过")
