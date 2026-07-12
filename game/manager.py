"""
Game state manager - handles scoring logic and database operations.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from db.models import TeamScore
from game.models import TeamInfo


class GameManager:
    """游戏状态管理器，维护积分等游戏状态"""

    def __init__(self):
        self._game_active = False
        self._current_round = ""
        self._default_teams = [
            "第一组", "第二组", "第三组", "第四组", "第五组",
        ]

    @property
    def is_game_active(self) -> bool:
        return self._game_active

    @property
    def current_round(self) -> str:
        return self._current_round

    # ---- 数据库操作 ----

    def init_teams(self, db: Session, team_names: Optional[List[str]] = None):
        """初始化队伍列表（如数据库为空则创建默认队伍）"""
        names = team_names or self._default_teams
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

    def get_leaderboard(self, db: Session) -> List[TeamInfo]:
        """获取排行榜（按积分降序）"""
        teams = db.query(TeamScore).order_by(TeamScore.score.desc()).all()
        return [TeamInfo(team_name=t.team_name, score=t.score, display_order=t.display_order) for t in teams]

    def get_tts_for_score(self, team_name: str, delta: int, new_score: int) -> str:
        """生成积分变化的 TTS 播报文本"""
        action = "加" if delta > 0 else "减"
        abs_delta = abs(delta)
        return f"{team_name}{action}{abs_delta}分，当前{team_name}{new_score}分"

    # ---- 游戏环节控制 ----

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


# 全局单例
game_manager = GameManager()
