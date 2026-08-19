"""
AI 智能体路由 —— ReAct 自主 Agent

Agent 循环：
  用户输入 → Agent 思考 → 选择工具 → 执行 → 观察结果 → 
  反思是否足够 → 继续/向用户确认/给出最终回复

不再依赖关键词路由，Agent 自主决定每一步做什么。
"""
import json, os, sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from openai import OpenAI

from database import get_db
from llm.agent import ReActAgent
from llm.security import is_confirmation, is_cancel

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
)

router = APIRouter(prefix="/api/ai", tags=["智能查询"])

# 全局 Agent 实例（简化：单用户场景）
_agent: ReActAgent | None = None
MAX_STEPS = 8  # 最大思考步数，防止死循环


def sse_event(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _get_agent(db: Session) -> ReActAgent:
    """获取或创建 Agent 实例"""
    global _agent
    if _agent is None:
        _agent = ReActAgent(client, db)
    elif _agent.state == "done":
        # 用户继续对话，恢复 Agent 状态（保留历史记忆）
        _agent.state = "thinking"
        _agent.db = db
    return _agent


@router.get("/query")
async def ai_query(
    q: str = Query(...),
    db: Session = Depends(get_db),
):
    """ReAct Agent 主入口 —— 流式 SSE 返回 Agent 思考过程"""

    agent = _get_agent(db)

    async def event_stream():
        global _agent
        # 重置 Agent 的 db 引用（因为 FastAPI 每个请求新 session）
        agent.db = db

        # ---------- 上下文续接：用户回复 Agent 上轮的提问 ----------
        user_input = q
        if agent.last_question and is_confirmation(q):
            # 用户对 Agent 上轮的提问说"可以/好的/是"，把上下文注入
            user_input = f"（对话背景：你上一轮问：{agent.last_question}。用户现在回答：{q}。请基于上下文继续执行任务。）"
            agent.last_question = None  # 消费掉

        # ---------- 待确认的写操作处理 ----------
        if agent.pending_write:
            if is_confirmation(q):
                yield sse_event({"event": "executing", "step": "write", "message": "正在执行修改..."})
                result = agent.confirm_write(db)
                yield sse_event({
                    "event": "done", "type": "write_result",
                    "summary": result, "message": result,
                })
                # 通知前端刷新数据
                yield sse_event({"event": "data_changed"})
                return
            elif is_cancel(q):
                agent.cancel_write()
                yield sse_event({
                    "event": "done", "type": "chat",
                    "summary": "已取消。", "message": "已取消。",
                })
                return
            else:
                # 用户说了别的，取消待确认操作
                agent.cancel_write()

        # ---------- Agent 思考循环 ----------
        step_count = 0

        while step_count < MAX_STEPS and agent.state != "done":
            step_count += 1

            # 发送进度
            yield sse_event({
                "step": step_count,
                "event": "agent_thinking",
                "message": "思考中...",
            })

            # Agent 执行一步
            result = agent.step(user_input)
            user_input = None  # 后续步骤不再传用户输入

            if result["type"] == "done":
                # 任务完成
                yield sse_event({
                    "event": "done",
                    "type": "chat" if not result.get("thought") else "query",
                    "summary": result["reply"],
                    "message": result["reply"],
                    "thought": result.get("thought", ""),
                })
                # 如果有 tableData 在 scratchpad 中，尝试提取
                # （需要在前端构建，这里先简化）
                break

            elif result["type"] == "observation":
                # 工具执行完毕，发回观察结果，继续循环
                yield sse_event({
                    "event": "agent_step",
                    "thought": result.get("thought", ""),
                    "tool": result.get("tool", ""),
                    "args": result.get("args", {}),
                    "observation": result.get("content", ""),
                    "tableData": result.get("tableData"),
                    "tableCount": result.get("tableCount", 0),
                })

            elif result["type"] == "confirm_required":
                # 需要用户确认修改（不暴露 SQL 给用户）
                reason = result.get("reason", "")
                yield sse_event({
                    "event": "confirm_required",
                    "thought": result.get("thought", ""),
                    "sql": result.get("sql", ""),
                    "reason": reason,
                    "summary": f"{reason}\n\n是否确认执行？",
                    "message": f"{reason}\n是否确认执行？",
                })
                return  # 等待用户确认

            elif result["type"] == "waiting_user":
                # Agent 向用户提问
                yield sse_event({
                    "event": "agent_ask",
                    "thought": result.get("thought", ""),
                    "question": result.get("question", ""),
                    "summary": result.get("question", ""),
                    "message": result.get("question", ""),
                })
                agent.state = "waiting_user"
                return  # 等待用户回复

            elif result["type"] == "error":
                yield sse_event({
                    "event": "error",
                    "message": result["content"],
                })
                break

        # 超过最大步数
        if step_count >= MAX_STEPS and agent.state != "done":
            yield sse_event({
                "event": "error",
                "message": "Agent 思考步数超限，请简化问题重试。",
            })

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.post("/reset")
def reset_agent():
    """重置 Agent 状态"""
    global _agent
    _agent = None
    return {"message": "Agent 已重置"}
