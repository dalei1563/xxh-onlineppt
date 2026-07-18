"""
Teams REST API - 队伍积分管理接口。
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db.database import get_db
from game.models import TeamInfo, ScoreUpdate, ScoreSet
from services.game_service import game_service
from ws.handler import manager as ws_manager
from ws.protocol import ScoreUpdateMsgOut, ScoreSetMsgOut, ScoreResetMsgOut


router = APIRouter(prefix="/api/teams", tags=["teams"])


@router.get("", response_model=List[TeamInfo])
async def get_teams(db: Session = Depends(get_db)):
    """获取所有队伍及其积分"""
    return game_service.get_all_teams(db)


@router.get("/leaderboard", response_model=List[TeamInfo])
async def get_leaderboard(db: Session = Depends(get_db)):
    """获取排行榜（按积分降序）"""
    return game_service.get_leaderboard(db)


@router.post("/score")
async def update_team_score(data: ScoreUpdate, db: Session = Depends(get_db)):
    """更新队伍积分"""
    result = game_service.update_score(db, data.team_name, data.delta)
    if not result:
        raise HTTPException(status_code=404, detail=f"未找到队伍: {data.team_name}")
    await ws_manager.broadcast(
        ScoreUpdateMsgOut(
            team_name=result.team_name,
            score=result.score,
            delta=data.delta,
        ).model_dump()
    )
    return result


@router.post("/score/set")
async def set_team_score(data: ScoreSet, db: Session = Depends(get_db)):
    """直接设置队伍积分"""
    result = game_service.set_score(db, data.team_name, data.score)
    if not result:
        raise HTTPException(status_code=404, detail=f"未找到队伍: {data.team_name}")
    await ws_manager.broadcast(
        ScoreSetMsgOut(team_name=result.team_name, score=result.score).model_dump()
    )
    return result


@router.post("/reset")
async def reset_scores(db: Session = Depends(get_db)):
    """重置所有队伍积分"""
    game_service.reset_all_scores(db)
    teams = game_service.get_all_teams(db)
    await ws_manager.broadcast(
        ScoreResetMsgOut(teams=[t.model_dump() for t in teams]).model_dump()
    )
    return {"message": "所有积分已重置", "teams": teams}
