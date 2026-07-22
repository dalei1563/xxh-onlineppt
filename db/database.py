"""
Database connection management for SQLite.
"""
import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base

# 数据库文件路径。GSP_DB_PATH 便于部署和测试使用隔离的数据文件；
# 未配置时保持原有的项目内 data/ 默认位置。
_default_db_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DB_PATH = os.path.abspath(os.getenv("GSP_DB_PATH", os.path.join(_default_db_dir, "gsp_scores.db")))
DB_DIR = os.path.dirname(DB_PATH)

# 确保 data 目录存在
os.makedirs(DB_DIR, exist_ok=True)

# SQLite 连接 URL
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # FastAPI 多线程需要
    echo=False,
)

# 启用 WAL 模式以提升并发性能
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """获取数据库会话的依赖注入"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """初始化数据库，创建所有表"""
    import db.models  # noqa: F401 - 确保模型被导入以注册到 Base
    Base.metadata.create_all(bind=engine)
