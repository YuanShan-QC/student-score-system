"""
测试夹具 —— 让测试可以在"没有真实 API Key、没有真实大模型调用"的情况下运行。

关键点：
  backend/llm/agent.py 在 `from config import client` 时会真的构造 OpenAI 客户端，
  没有 key 就会抛异常。所以必须在 import 之前塞一个假的 key 进环境变量。
  实测结论：OpenAI 客户端只在**发请求时**才校验 key，构造时不校验，
  因此塞假 key 足够让 import 通过，而且不会产生任何网络调用。
"""

import os
import sys
from pathlib import Path

# --- 1. import agent 之前必须先设好假 key，顺序不能反 -------------------------
os.environ.setdefault("DEEPSEEK_API_KEY", "test-key-not-used")

# --- 2. 把 backend 目录加进 sys.path -----------------------------------------
BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import pytest  # noqa: E402


class FakeDBSession:
    """
    假数据库会话 —— 只记录被执行的 SQL，不真的连库。

    用途：验证"哪条 SQL 会被放行到执行层"（安全测试），
    以及"执行后的结果怎么被格式化"（工具层测试），二者都不需要真实 DB。
    """

    def __init__(self, rows=None, rowcount=1, should_raise=None):
        self.executed = []          # 每次 execute 收到的 SQL 文本
        self.rows = rows or []      # fetchall() 返回的假数据
        self.rowcount = rowcount
        self.should_raise = should_raise
        self.committed = False
        self.flushed = False

    def execute(self, statement, params=None):
        # SQLAlchemy 的 text() 对象用 str() 能拿到原始 SQL
        sql = str(statement)
        self.executed.append(sql)
        if self.should_raise:
            raise self.should_raise

        outer = self

        class _Result:
            rowcount = outer.rowcount

            def fetchall(self):
                class _Row:
                    def __init__(self, mapping):
                        self._mapping = mapping

                return [_Row(r) for r in outer.rows]

        return _Result()

    def flush(self):
        self.flushed = True

    def commit(self):
        self.committed = True

    def rollback(self):
        pass


@pytest.fixture
def agent():
    """一个不调用大模型的 Agent 实例（db 传 None，只测工具层与解析层）"""
    from llm.agent import ReActAgent

    return ReActAgent(client=None, db_session=None)


@pytest.fixture
def fake_db():
    """假 DB 会话工厂"""
    return FakeDBSession
