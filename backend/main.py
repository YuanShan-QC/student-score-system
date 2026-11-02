#!/usr/bin/env python
"""
FastAPI 应用入口 —— 学生成绩管理系统 API
启动：cd backend && python main.py
文档：http://localhost:8080/docs
"""
# ===== Windows 事件循环兜底（必须在事件循环创建前设置，import 期执行刚好）=====
# Windows 默认的 ProactorEventLoop 在 accept() 上会抛
#   OSError: [WinError 10014] 系统检测到在一个调用中尝试使用指针参数时的无效指针地址
# 监听套接字随即失效：进程还活着，但所有新连接都会失败
# （前端页面能打开——那是 Vite 的 5173——但接口全挂，页面提示"拉取数据失败"）。
# uvicorn 只在 use_subprocess（--reload / --workers）时才切 SelectorEventLoop，
# 单进程启动会保留 Proactor，所以这里显式切换。
#
# 注意：这段只在**入口先执行、循环后创建**的顺序下有效 ——
#   ✅ `python main.py`   ✅ `python run.py`（新建，推荐）
#   ❌ `python -m uvicorn main:app`：uvicorn 先建循环再 import 本模块，
#      此处的设置来不及生效，实测仍会 10014（已验证）。所以要跑 uvicorn
#      请用 `backend/run.py`，别用 -m uvicorn。
# 设 SCORE_DISABLE_SELECTOR_LOOP=1 可临时关闭该兜底（仅用于诊断对比）。
import asyncio
import os
import sys

if sys.platform == "win32" and not os.getenv("SCORE_DISABLE_SELECTOR_LOOP"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

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
        # localhost 与 127.0.0.1 是两个不同的 origin，Vite 提示里两种都给，
        # 只放 localhost 的话，用 127.0.0.1:5173 打开页面会 CORS 失败、
        # 表现为"页面能进但数据拉不到"，和 10014 的症状一模一样，容易误判。
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
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
