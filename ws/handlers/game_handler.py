"""
WebSocket handler for game/scoring messages.
所有积分与游戏状态变更都通过 services/game_service.py 完成。
"""
from typing import Any
import asyncio

from db.database import SessionLocal
from services.game_service import game_service
from state.presentation import presentation_state
from ws.protocol import (
    ScoreUpdateMsgOut,
    ScoreSetMsgOut,
    ScoreBoardMsg,
    ScoreResetMsgOut,
    GameControlMsgOut,
    TtsSpeakMsg,
)


async def handle_score_update(manager: Any, data: dict, client_id: int):
    team_name = data.get("team_name", "")
    delta = int(data.get("delta", 0))
    auto_tts = bool(data.get("auto_tts", False))

    if not team_name:
        return

    db = SessionLocal()
    try:
        result = game_service.update_score(db, team_name, delta)
        if result:
            await manager.broadcast(
                ScoreUpdateMsgOut(
                    team_name=result.team_name,
                    score=result.score,
                    delta=delta,
                ).model_dump()
            )

            if auto_tts:
                tts_text = game_service.get_tts_for_score(result.team_name, delta, result.score)
                await manager.broadcast(
                    TtsSpeakMsg(text=tts_text).model_dump()
                )

            print(f"[Game] Score updated: {team_name} {delta:+d} -> {result.score}")
        else:
            print(f"[Game] Team not found: {team_name}")
    finally:
        db.close()


async def handle_score_set(manager: Any, data: dict, client_id: int):
    team_name = data.get("team_name", "")
    score = int(data.get("score", 0))

    if not team_name:
        return

    db = SessionLocal()
    try:
        result = game_service.set_score(db, team_name, score)
        if result:
            await manager.broadcast(
                ScoreSetMsgOut(team_name=result.team_name, score=result.score).model_dump()
            )
            print(f"[Game] Score set: {team_name} -> {score}")
    finally:
        db.close()


async def handle_score_get(manager: Any, data: dict, client_id: int):
    db = SessionLocal()
    try:
        teams = game_service.get_all_teams(db)
        await manager.send_to_client(
            client_id,
            ScoreBoardMsg(teams=[t.model_dump() for t in teams]).model_dump(),
        )
    finally:
        db.close()


async def handle_score_leaderboard(manager: Any, data: dict, client_id: int):
    db = SessionLocal()
    try:
        teams = game_service.get_leaderboard(db)
        await manager.broadcast(
            ScoreBoardMsg(
                teams=[t.model_dump() for t in teams],
                leaderboard=True,
            ).model_dump()
        )
    finally:
        db.close()


async def handle_score_reset(manager: Any, data: dict, client_id: int):
    db = SessionLocal()
    try:
        game_service.reset_all_scores(db)
        teams = game_service.get_all_teams(db)
        await manager.broadcast(
            ScoreResetMsgOut(teams=[t.model_dump() for t in teams]).model_dump()
        )
        print("[Game] All scores reset")
    finally:
        db.close()


async def handle_game_control(manager: Any, data: dict, client_id: int):
    action = data.get("action", "")
    round_name = data.get("round_name", "")

    if action == "start":
        game_service.start_game(round_name)
        presentation_state.start_game(round_name)
        await manager.broadcast(
            GameControlMsgOut(action="started", round_name=round_name).model_dump()
        )
        print(f"[Game] Game started: {round_name}")

    elif action == "end":
        game_service.end_game()
        presentation_state.end_game()
        await manager.broadcast(
            GameControlMsgOut(action="ended").model_dump()
        )
        print("[Game] Game ended")

    elif action == "reset":
        db = SessionLocal()
        try:
            game_service.reset_game(db)
            presentation_state.reset_game()
            await manager.broadcast(
                GameControlMsgOut(action="reset").model_dump()
            )
            print("[Game] Game reset")
        finally:
            db.close()


def register_game_handlers(router):
    """向路由器注册所有游戏/积分消息"""
    router.register("score_update", handle_score_update)
    router.register("score_set", handle_score_set)
    router.register("score_get", handle_score_get)
    router.register("score_leaderboard", handle_score_leaderboard)
    router.register("score_reset", handle_score_reset)
    router.register("game_control", handle_game_control)
