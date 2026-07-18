"""
Game REST API - 游戏环节控制接口。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db.database import get_db, SessionLocal
from game.models import GameControl
from services.game_service import game_service
from state.presentation import presentation_state
from ws.handler import manager as ws_manager
from ws.protocol import GameControlMsgOut


router = APIRouter(prefix="/api/game", tags=["game"])


@router.post("/control")
async def game_control(control: GameControl, db: Session = Depends(get_db)):
    """控制游戏环节"""
    if control.action == "start":
        game_service.start_game(control.round_name or "")
        presentation_state.start_game(control.round_name or "")
        await ws_manager.broadcast(
            GameControlMsgOut(action="started", round_name=control.round_name or "").model_dump()
        )
        return {"message": f"游戏环节已开始: {control.round_name}"}

    elif control.action == "end":
        game_service.end_game()
        presentation_state.end_game()
        await ws_manager.broadcast(
            GameControlMsgOut(action="ended").model_dump()
        )
        return {"message": "游戏环节已结束"}

    elif control.action == "reset":
        game_service.reset_game(db)
        presentation_state.reset_game()
        await ws_manager.broadcast(
            GameControlMsgOut(action="reset").model_dump()
        )
        return {"message": "游戏已重置"}

    raise HTTPException(status_code=400, detail=f"不支持的动作: {control.action}")
