# -*- coding: utf-8 -*-
"""
成绩数据 Agent —— 后端启动入口（Windows 推荐用这个）

为什么需要这个文件（而不是 `python -m uvicorn main:app`）：
    Windows 上 asyncio 默认用 ProactorEventLoop，它的 accept() 会抛
        OSError: [WinError 10014] 系统检测到在一个调用中尝试使用指针参数时的无效指针地址
    监听套接字随即失效——进程还活着，但所有新连接都失败。前端页面能打开
    （那是 Vite 的 5173），但接口全部拉不到数据。

    关键点：事件循环策略必须在**循环创建之前**设置。
    用 `python -m uvicorn main:app` 时，uvicorn 先建好循环、再 import main，
    所以 main.py 里那句 set_event_loop_policy 已经来不及了（实测仍会 10014）。
    用本文件或 `python main.py` 时，入口代码先跑，策略生效后才建循环，才是安全的。

    这也正是 uvicorn 自己的行为：它只在 use_subprocess（--reload / --workers）
    时才切 SelectorEventLoop（见 uvicorn/loops/asyncio.py），单进程默认保留 Proactor。

启动：
    cd backend
    .venv\\Scripts\\python.exe run.py
    （等价于 .venv\\Scripts\\python.exe main.py，端口都是 8080）

诊断：设 SCORE_DISABLE_SELECTOR_LOOP=1 可临时关掉该兜底，用于对照复现。
"""
import os
import sys

# ===== 必须在 import uvicorn / 创建事件循环之前执行 =====
if sys.platform == "win32" and not os.getenv("SCORE_DISABLE_SELECTOR_LOOP"):
    import asyncio

    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn  # noqa: E402  （必须在设置事件循环策略之后导入）

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8080,
        loop="asyncio",  # 使用标准 asyncio 循环（策略已在上方设为 Selector）
        log_level="info",
    )
