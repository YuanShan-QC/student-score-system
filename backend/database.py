"""
SQLAlchemy 引擎配置 —— SQLite 数据库连接与 Session 管理

【2026-09-27 两处修复，都值得在面试里讲】

1) 连接串原本是相对路径 "sqlite:///../data/scores.db"，相对于**进程工作目录**解析。
   后果：从仓库根目录启动就变成 C:/Users/Lenovo/DSH/data/scores.db，
   从 backend 启动才是 student-score-system/data/scores.db —— 同一份代码连到两个库，
   表现为"数据莫名其妙不见了"或"pytest 一跑就在别处建了个空库"。
   修法：用 __file__ 推出绝对路径，与启动目录无关。

2) echo=True 是硬编码的，SQL 日志会淹没测试输出和正常日志。
   修法：从环境变量 SQL_ECHO 读取，默认关闭；调试时在 .env 里设 SQL_ECHO=1。

3) 额外加了 DATABASE_URL 环境变量覆盖：测试可以指向临时库，
   这样跑接口测试不会碰开发库的数据（否则测试写进去的脏数据会留在演示数据里）。
"""
import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base

# 数据库文件固定在 student-score-system/data/scores.db（与启动目录无关）
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "scores.db"

# SQLite 在 Windows 上要用正斜杠，否则 create_engine 解析 URL 会出错
# 允许用环境变量覆盖（测试指向临时库；生产可指向 PostgreSQL 等）
DATABASE_URL = os.getenv("DATABASE_URL") or f"sqlite:///{DB_PATH.as_posix()}"

# 是否打印 SQL 日志：默认关闭（.env 里设 SQL_ECHO=1 打开）
SQL_ECHO = os.getenv("SQL_ECHO", "").strip().lower() in ("1", "true", "yes", "on")

# 连接串：数据库文件放在 student-score-system/data/scores.db
engine = create_engine(
    DATABASE_URL,
    echo=SQL_ECHO,                            # 由 SQL_ECHO 控制，默认不打印
    connect_args={"check_same_thread": False} # SQLite 允许多线程（FastAPI 需要）
)


# 每次建立连接时强制开启外键约束（SQLite 默认关闭）
@event.listens_for(engine, "connect")
def enable_foreign_keys(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# SessionLocal = 每次请求一个独立 session
SessionLocal = sessionmaker(bind=engine)

# Base = 所有 ORM 模型的基类
Base = declarative_base()


# ===== FastAPI 依赖注入：每个请求一个独立 session =====
def get_db():
    """
    FastAPI Depends 用的数据库 session 生成器。
    用法：@router.get("/xxx")
          def handler(db: Session = Depends(get_db)): ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
