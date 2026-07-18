"""
Game service - 积分与游戏环节的统一业务入口。
REST API 和 WebSocket 都通过此处操作积分与游戏状态。
"""
from typing import List, Optional
from sqlalchemy.orm import Session

from db.models import TeamScore
from game.models import TeamInfo


_DEFAULT_TEAMS = ["A队", "B队", "C队", "D队"]


class GameService:
    """游戏状态服务"""

    def __init__(self):
        self._game_active = False
        self._current_round = ""

    @property
    def is_game_active(self) -> bool:
        return self._game_active

    @property
    def current_round(self) -> str:
        return self._current_round

    def init_teams(self, db: Session, team_names: Optional[List[str]] = None):
        """初始化队伍列表（如数据库为空则创建默认队伍）"""
        names = team_names or _DEFAULT_TEAMS
        existing = db.query(TeamScore).count()
        if existing > 0:
            return

        for i, name in enumerate(names):
            team = TeamScore(team_name=name, score=0, display_order=i)
            db.add(team)
        db.commit()

    def get_all_teams(self, db: Session) -> List[TeamInfo]:
        """获取所有队伍积分"""
        teams = db.query(TeamScore).order_by(TeamScore.display_order).all()
        return [TeamInfo(team_name=t.team_name, score=t.score, display_order=t.display_order) for t in teams]

    def get_leaderboard(self, db: Session) -> List[TeamInfo]:
        """获取排行榜（按积分降序）"""
        teams = db.query(TeamScore).order_by(TeamScore.score.desc()).all()
        return [TeamInfo(team_name=t.team_name, score=t.score, display_order=t.display_order) for t in teams]

    def update_score(self, db: Session, team_name: str, delta: int) -> Optional[TeamInfo]:
        """更新指定队伍的积分（delta 可为正负数）"""
        team = db.query(TeamScore).filter(TeamScore.team_name == team_name).first()
        if not team:
            return None
        team.score += delta
        db.commit()
        db.refresh(team)
        return TeamInfo(team_name=team.team_name, score=team.score, display_order=team.display_order)

    def set_score(self, db: Session, team_name: str, score: int) -> Optional[TeamInfo]:
        """直接设置指定队伍的积分"""
        team = db.query(TeamScore).filter(TeamScore.team_name == team_name).first()
        if not team:
            return None
        team.score = score
        db.commit()
        db.refresh(team)
        return TeamInfo(team_name=team.team_name, score=team.score, display_order=team.display_order)

    def reset_all_scores(self, db: Session):
        """重置所有队伍积分为 0"""
        db.query(TeamScore).update({"score": 0})
        db.commit()

    def start_game(self, round_name: str = ""):
        """开始游戏环节"""
        self._game_active = True
        self._current_round = round_name

    def end_game(self):
        """结束游戏环节"""
        self._game_active = False
        self._current_round = ""

    def reset_game(self, db: Session):
        """重置游戏（结束环节 + 清零积分）"""
        self.end_game()
        self.reset_all_scores(db)

    def get_tts_for_score(self, team_name: str, delta: int, new_score: int) -> str:
        """生成积分变化的 TTS 播报文本"""
        action = "加" if delta > 0 else "减"
        abs_delta = abs(delta)
        if abs_delta == 0:
            return f"{team_name}当前{new_score}分"
        return f"{team_name}{action}{abs_delta}分，当前{new_score}分"


# 全局单例
game_service = GameService()
