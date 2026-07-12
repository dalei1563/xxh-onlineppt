"""
SQLAlchemy ORM models for game scoring and slide management.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, func
from db.database import Base


class TeamScore(Base):
    """团队积分记录"""
    __tablename__ = "team_scores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    team_name = Column(String(50), nullable=False, unique=True, comment="组名")
    score = Column(Integer, nullable=False, default=0, comment="当前积分")
    display_order = Column(Integer, nullable=False, default=0, comment="显示排序")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    def to_dict(self):
        return {
            "id": self.id,
            "team_name": self.team_name,
            "score": self.score,
            "display_order": self.display_order,
        }


class SlideMeta(Base):
    """幻灯片元数据"""
    __tablename__ = "slides_meta"

    id = Column(Integer, primary_key=True, autoincrement=True)
    slide_id = Column(String(10), nullable=False, unique=True, comment="幻灯片标识，如 1, 1b, 2...66")
    title = Column(String(200), default="", comment="编辑器中显示的标题")
    type = Column(String(50), default="content", comment="幻灯片类型")
    chapter = Column(String(100), default="", comment="所属章节名称")
    display_order = Column(Integer, nullable=False, default=0, comment="排序序号")
    content_json = Column(Text, default="{}", comment="可编辑内容（JSON 格式）")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        import json
        return {
            "id": self.id,
            "slide_id": self.slide_id,
            "title": self.title,
            "type": self.type,
            "chapter": self.chapter,
            "display_order": self.display_order,
            "content_json": json.loads(self.content_json) if self.content_json else {},
        }
