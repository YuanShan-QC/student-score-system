"""
SQLAlchemy 引擎配置 —— SQLite 数据库连接与 Session 管理
"""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base

# 连接串：数据库文件放在 ../data/scores.db（相对于本文件的父级 data 目录）
engine = create_engine(
    "sqlite:///../data/scores.db",
    echo=True,                               # 打印 SQL 日志，方便调试
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
