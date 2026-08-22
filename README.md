# 学生成绩管理系统

一个基于 **FastAPI + Vue3 + SQLite** 的全栈 Web 应用，实现学生成绩的增删改查、Excel 批量导入导出，以及基于 **DeepSeek 大模型**的自主智能体（ReAct 架构）自然语言查询与数据管理。

## 功能特性

- **数据看板**：统计卡片（学生数/科目数/成绩数/平均分）+ ECharts 图表（各科目平均分、成绩分布）
- **学生管理**：学号 / 姓名 / 性别 / 年龄的增删改查，关键词搜索（防抖），级联删除成绩
- **科目管理**：科目代码 / 名称的增删改查
- **成绩管理**：成绩录入、修改、删除，分数按等级着色（<60 红色，≥90 绿色）
- **Excel 导入导出**：模板下载、批量导入（预校验 + 事务 upsert）、全量导出
- **AI 智能体**：自然语言对话查询与修改数据，多步推理、上下文记忆、写操作二次确认、查询结果自动表格渲染
- **界面美化**：靛紫主题色、暗色模式切换、卡片化布局、路由过渡动画

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.13 · FastAPI · SQLAlchemy 2.x · SQLite · Uvicorn · openpyxl · openai SDK |
| 前端 | Vue 3 · Element Plus · Vue Router · Pinia · Axios · Vite 5 · ECharts 6 |
| AI | DeepSeek · ReAct 循环 · SSE 流式传输 |

## 目录结构

```
student-score-system/
├── backend/                 # FastAPI 后端
│   ├── main.py              # 入口（自动建表 + 种子数据）
│   ├── models.py            # ORM 模型（学生/科目/成绩）
│   ├── schemas.py           # Pydantic 校验模型
│   ├── database.py          # SQLAlchemy 引擎 + Session
│   ├── crud.py              # 数据访问层
│   ├── .env                 # DeepSeek API 配置（已被 .gitignore 忽略）
│   ├── routers/             # 路由：students / subjects / scores / ai
│   └── llm/                 # ReAct Agent 核心 / 知识库 / Schema / 安全校验
├── frontend/                # Vue3 前端
│   └── src/
│       ├── api/             # 接口封装
│       ├── views/           # 学生/科目/成绩/AI 四个页面
│       ├── router/          # 路由 + keep-alive
│       └── stores/          # Pinia 跨页刷新通知
├── data/                    # SQLite 数据库文件（已被 .gitignore 忽略）
├── start.bat                # 一键启动脚本（Windows）
├── stop.bat                 # 一键停止脚本（Windows）
└── 实验手册.md               # 详细技术文档
```

## 快速开始

### 方式一：一键启动（推荐，Windows）

双击项目根目录下的 **`start.bat`**，脚本会自动完成：

1. 首次运行自动创建后端虚拟环境并安装依赖
2. 首次运行自动安装前端 `node_modules`
3. 分别启动后端（8080）和前端（5173）两个窗口
4. 等待就绪后自动打开浏览器

> **停止服务**：双击项目根目录下的 **`stop.bat`**，会自动结束后端（8080）和前端（5173）的进程，无需手动逐个关闭窗口。

### 方式二：手动启动

**后端**（终端 1）：

```bash
cd backend
# 首次运行先安装依赖
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt
# 启动
.venv/Scripts/python main.py
```

> 启动时自动建表并写入种子数据（6 科 / 5 生 / 25 条成绩）。

**前端**（终端 2）：

```bash
cd frontend
npm install        # 首次运行
npm run dev
```

## 访问地址

| 服务 | 地址 |
|------|------|
| 前端页面 | http://localhost:5173/ |
| API 文档（Swagger） | http://localhost:8080/docs |
| 健康检查 | http://localhost:8080/ |

## AI 智能体配置

智能体功能依赖 DeepSeek API，需要在 `backend/.env` 中配置：

```
DEEPSEEK_API_KEY=你的密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
```

> 该文件已被 `.gitignore` 忽略，**请勿将真实密钥提交到公开仓库**。若账号余额不足，AI 接口会返回 402 错误。

## 常见问题

**端口被占用？**

```bash
netstat -ano | findstr :8080
taskkill /PID <进程ID> /F
```

**想重置数据库？**

删除 `data/scores.db` 后重启后端，会自动重建并重新写入种子数据。

**前端报 "Failed to fetch"？**

先确认后端 8080 端口已正常启动，再刷新前端页面。

## 许可证

本项目仅用于学习与演示。
