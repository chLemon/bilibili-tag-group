from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings.database_url,
    future=True,
    connect_args={
        "check_same_thread": False,
        "timeout": 15,
    },
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


# 启用 WAL 模式（持久化，只需设置一次），提升 SQLite 并发能力。
# busy_timeout 配置写锁等待，减少 "database is locked" 错误。
import sqlite3 as _sqlite3


def _setup_pragma(dbapi_connection, _connection_record):
    if isinstance(dbapi_connection, _sqlite3.Connection):
        dbapi_connection.execute("PRAGMA journal_mode=WAL")
        dbapi_connection.execute("PRAGMA busy_timeout=5000")


# 使用 _enable_wal=False 的隔离连接来设置 pragma，避免已有进程持有写锁时失败
def _init_pragmas():
    try:
        raw = engine.raw_connection()
        raw.execute("PRAGMA journal_mode=WAL")
        raw.execute("PRAGMA busy_timeout=5000")
        raw.close()
    except Exception:
        pass  # 可能已有进程正在写入，pragma 已经设过了就跳过


from sqlalchemy import event
event.listen(engine, "connect", _setup_pragma)
_init_pragmas()
