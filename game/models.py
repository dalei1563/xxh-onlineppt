"""
Pydantic models for game-related WebSocket messages and API.
"""
from pydantic import BaseModel, Field
from typing import Optional, List


class ScoreUpdate(BaseModel):
    """积分更新请求"""
    team_name: str = Field(..., description="组名")
    delta: int = Field(..., ge=-10000, le=10000, description="分数变化（正数加分，负数减分）")
    auto_tts: bool = Field(False, description="是否自动语音播报")


class ScoreSet(BaseModel):
    """设置积分请求"""
    team_name: str = Field(..., description="组名")
    score: int = Field(..., ge=-1_000_000, le=1_000_000, description="目标分数")


class TeamInfo(BaseModel):
    """团队信息"""
    team_name: str
    score: int = 0
    display_order: int = 0


class ScoreBoard(BaseModel):
    """排行榜数据"""
    teams: List[TeamInfo]


class GameControl(BaseModel):
    """游戏环节控制"""
    action: str = Field(..., description="控制动作: start / end / reset / pause / resume")
    round_name: Optional[str] = Field(None, description="环节名称")
