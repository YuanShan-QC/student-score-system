#!/usr/bin/env python
"""
FastAPI 应用入口 —— 学生成绩管理系统 API
启动：cd backend && python main.py
文档：http://localhost:8080/docs
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ===== 数据库初始化 =====
# 【2026-09-27 修复】这里原本内联了一整套种子数据（6 科 5 生 25 条成绩），
# 和 init_data.py 里的那份**重复且不一致**：
#   · init_data.py 只给 5 个学生各录 5 科（CHN/MATH/ENG/PHY/CHEM），BIO 没有成绩
#   · main.py 这份则会给部分学生多插 BIO 成绩
# 结果：同一套代码，走"python main.py"和走"python init_data.py"初始化出来的库不一样，
# 开发库里真的因此多出过 3 条成绩（已用 scripts/fix_dev_data.py 修掉）。
# 现在统一：种子数据只有一个来源 —— init_data.py。main.py 只负责建表。
from database import engine, Base, SessionLocal
from models import Student, Subject, Score  # noqa: F401  确保模型注册到 Base

Base.metadata.create_all(bind=engine)


def _seed_if_empty():
    """
    表为空时灌入种子数据。

    直接 import init_data 会把它的模块级代码（建表 + 灌数据）执行一遍，
    所以这里用 importlib 精确加载，并复用它的数据定义，避免出现第二份种子数据。
    """
    db = SessionLocal()
    try:
        if db.query(Student).count() > 0:
            print("[INIT] 数据库已有数据，跳过种子初始化")
            return
    finally:
        db.close()

    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "seed_init_data", Path(__file__).resolve().parent / "init_data.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)   # init_data.py 自己会打日志并提交


_seed_if_empty()

# ===== FastAPI 应用初始化 =====
app = FastAPI(title="学生成绩管理系统")

# ===== CORS 中间件：Vite 开发服务器可能漂移到 5173/5174/5175 =====
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== 健康检查 =====
@app.get("/")
def root():
    """健康检查：确认 API 运行中，并告知文档地址"""
    return {"message": "API running", "docs": "/docs"}


# ===== 路由注册 =====
from routers import subjects, students, scores, ai, stats
app.include_router(subjects.router)
app.include_router(students.router)
app.include_router(scores.router)
app.include_router(ai.router)
app.include_router(stats.router)


# ===== 启动入口 =====
# 【2026-09-27 修复】这里原本是模块级直接调用 uvicorn.run(...)，没有 __main__ 保护。
# 后果：任何 `from main import app` 都会启动一个真实的服务器并**永久阻塞**
#   —— test_12api.py 跑不起来（卡死）、pytest 一收集到这个文件就 INTERNALERROR。
# 正确写法是把副作用关进 __main__，import 时只暴露 app 对象。
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
