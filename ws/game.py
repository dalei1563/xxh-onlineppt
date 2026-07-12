"""
WebSocket message handler for game/scoring messages.
"""
from typing import Any
from db.database import SessionLocal
from game.manager import game_manager


async def handle_game_message(handler: Any, data: dict, client_id: int):
    """处理游戏/积分相关消息"""
    msg_type = data.get("type", "")

    if msg_type == "score_update":
        team_name = data.get("team_name", "")
        delta = data.get("delta", 0)
        auto_tts = data.get("auto_tts", False)

        if not team_name:
            return

        db = SessionLocal()
        try:
            result = game_manager.update_score(db, team_name, delta)
            if result:
                # 广播积分更新
                await handler.broadcast({
                    "type": "score_update",
                    "team_name": result.team_name,
                    "score": result.score,
                    "delta": delta,
                })

                # 如需 TTS 播报
                if auto_tts:
                    tts_text = game_manager.get_tts_for_score(
                        result.team_name, delta, result.score
                    )
                    await handler.broadcast({
                        "type": "tts_request",
                        "text": tts_text,
                    })

                print(f"[Game] Score updated: {team_name} {delta:+d} -> {result.score}")
            else:
                print(f"[Game] Team not found: {team_name}")
        finally:
            db.close()

    elif msg_type == "score_set":
        team_name = data.get("team_name", "")
        score = data.get("score", 0)

        if not team_name:
            return

        db = SessionLocal()
        try:
            result = game_manager.set_score(db, team_name, score)
            if result:
                await handler.broadcast({
                    "type": "score_set",
                    "team_name": result.team_name,
                    "score": result.score,
                })
                print(f"[Game] Score set: {team_name} -> {score}")
        finally:
            db.close()

    elif msg_type == "score_get":
        """请求获取所有队伍当前积分"""
        db = SessionLocal()
        try:
            teams = game_manager.get_all_teams(db)
            await handler.send_to_client(client_id, {
                "type": "score_board",
                "teams": [t.model_dump() for t in teams],
            })
        finally:
            db.close()

    elif msg_type == "score_leaderboard":
        """请求获取排行榜"""
        db = SessionLocal()
        try:
            teams = game_manager.get_leaderboard(db)
            await handler.broadcast({
                "type": "score_board",
                "teams": [t.model_dump() for t in teams],
                "leaderboard": True,
            })
        finally:
            db.close()

    elif msg_type == "score_reset":
        """重置所有积分"""
        db = SessionLocal()
        try:
            game_manager.reset_all_scores(db)
            teams = game_manager.get_all_teams(db)
            await handler.broadcast({
                "type": "score_reset",
                "teams": [t.model_dump() for t in teams],
            })
            print(f"[Game] All scores reset")
        finally:
            db.close()

    elif msg_type == "game_control":
        """游戏环节控制"""
        action = data.get("action", "")
        round_name = data.get("round_name", "")

        if action == "start":
            game_manager.start_game(round_name)
            await handler.broadcast({
                "type": "game_control",
                "action": "started",
                "round_name": round_name,
            })
            print(f"[Game] Game started: {round_name}")

        elif action == "end":
            game_manager.end_game()
            await handler.broadcast({
                "type": "game_control",
                "action": "ended",
            })
            print(f"[Game] Game ended")

        elif action == "reset":
            db = SessionLocal()
            try:
                game_manager.reset_game(db)
                await handler.broadcast({
                    "type": "game_control",
                    "action": "reset",
                })
                print(f"[Game] Game reset")
            finally:
                db.close()
