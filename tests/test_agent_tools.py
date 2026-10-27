"""
Agent 工具层与安全层的接线测试 —— 防"函数写对了但没接上"这类回归。

为什么专门写这个文件：
  本次修复的本质是"把散落的校验收进 security.py 并真正调用起来"。
  如果只测 security.py 的纯函数，那么将来有人把 agent.py 里的 validate 调用删掉，
  单元测试照样全绿，而线上已经能执行 DROP TABLE 了 —— 那是测试最大的失效模式。
  所以这层必须单独测：**验证"哪条 SQL 会被送到数据库执行"**，用 FakeDBSession 记录。

跑法：pytest student-score-system -v
"""


class TestQueryDbWiring:
    """只读通道：query_db 必须真的调用 validate_read_sql"""

    def test_正常查询会被执行(self, agent, fake_db):
        db = fake_db(rows=[{"name": "张三"}])
        agent.db = db
        result = agent._tool_query_db({"sql": "SELECT name FROM students"})
        assert result.startswith("DATA:1:")
        assert len(db.executed) == 1

    def test_会自动补上_LIMIT(self, agent, fake_db):
        db = fake_db()
        agent.db = db
        agent._tool_query_db({"sql": "SELECT name FROM students"})
        assert "LIMIT 200" in db.executed[0]

    def test_白名单外的表会被拦在数据库之外(self, agent, fake_db):
        db = fake_db()
        agent.db = db
        result = agent._tool_query_db({"sql": "SELECT name FROM sqlite_master"})
        assert "安全策略拒绝" in result
        assert db.executed == []          # ← 关键断言：SQL 根本没到数据库

    def test_注释注入会被拦在数据库之外(self, agent, fake_db):
        db = fake_db()
        agent.db = db
        result = agent._tool_query_db({"sql": "SELECT * FROM students -- x"})
        assert "安全策略拒绝" in result
        assert db.executed == []

    def test_删表语句走只读通道会被拦(self, agent, fake_db):
        db = fake_db()
        agent.db = db
        result = agent._tool_query_db({"sql": "DROP TABLE scores"})
        assert "安全策略拒绝" in result
        assert db.executed == []


class TestModifyDbWiring:
    """写通道：校验通过只是挂起，绝不能直接执行"""

    def test_合法写语句只挂起不执行(self, agent, fake_db):
        db = fake_db()
        agent.db = db
        result = agent._tool_modify_db({
            "sql": "UPDATE scores SET score = 80 WHERE student_id = '001'",
            "reason": "改成绩",
        })
        assert result.startswith("PENDING_CONFIRM")
        assert agent.pending_write is not None
        assert agent.state == "waiting_user"
        # 没点确认之前一行写操作都不许执行；只允许 SELECT COUNT(*) 这类只读的影响行数预检
        writes = [s for s in db.executed
                  if s.strip().upper().startswith(("INSERT", "UPDATE", "DELETE"))]
        assert writes == []

    def test_写语句挂起时预估影响行数(self, agent, fake_db):
        db = fake_db()
        agent.db = db
        agent._tool_modify_db({
            "sql": "UPDATE scores SET score = 80 WHERE student_id = '001'",
            "reason": "改成绩",
        })
        assert db.executed == ["SELECT COUNT(*) FROM scores"]
        assert "影响" in agent.pending_write["reason"] or agent.pending_write["impact"] is None

    def test_无条件_DELETE_被拒且不挂起(self, agent, fake_db):
        agent.db = fake_db()
        result = agent._tool_modify_db({"sql": "DELETE FROM students", "reason": "试试"})
        assert "安全策略拒绝" in result
        assert agent.pending_write is None

    def test_带子查询的写语句被拒(self, agent, fake_db):
        agent.db = fake_db()
        result = agent._tool_modify_db({
            "sql": "UPDATE scores SET score = 80 WHERE subject_id = (SELECT id FROM subjects WHERE name = '数学')",
            "reason": "改成绩",
        })
        assert "安全策略拒绝" in result
        assert "子查询" in result
        assert agent.pending_write is None

    def test_恒真_WHERE_被拒(self, agent, fake_db):
        agent.db = fake_db()
        result = agent._tool_modify_db({
            "sql": "DELETE FROM scores WHERE score = score", "reason": "清空",
        })
        assert "安全策略拒绝" in result
        assert agent.pending_write is None


class TestConfirmWriteWiring:
    """用户确认后：执行前会再校验一次"""

    def test_确认后正常执行并提交事务(self, agent, fake_db):
        db = fake_db(rowcount=3)
        agent.pending_write = {"sql": "UPDATE scores SET score = 80 WHERE student_id = '001'", "reason": "改成绩"}
        result = agent.confirm_write(db)
        assert "已修改 3 条记录" in result
        assert db.committed is True
        assert agent.pending_write is None

    def test_执行前再校验_被篡改的_pending_也会被拦(self, agent, fake_db):
        """
        第二道防线：即使 pending_write 被绕过工具层直接塞进来（比如代码改错、
        或将来多加了别的写入路径），执行前这次校验仍然会拦住。
        """
        db = fake_db()
        agent.pending_write = {"sql": "DELETE FROM students", "reason": "被篡改"}
        result = agent.confirm_write(db)
        assert "已阻止执行" in result
        assert db.executed == []
        assert db.committed is False

    def test_没有待确认操作时直接返回提示(self, agent, fake_db):
        db = fake_db()
        assert agent.confirm_write(db) == "没有待确认的操作"
        assert db.executed == []

    def test_执行失败时回滚且清理状态(self, agent, fake_db):
        db = fake_db(should_raise=RuntimeError("数据库锁住了"))
        agent.pending_write = {"sql": "DELETE FROM students WHERE student_id = '006'", "reason": "删"}
        result = agent.confirm_write(db)
        assert "执行失败" in result
        assert agent.pending_write is None      # 失败也要清掉，避免状态卡住


class TestCancelWrite:
    def test_取消后清空待确认状态(self, agent):
        agent.pending_write = {"sql": "DELETE FROM students WHERE student_id = '006'", "reason": "删"}
        agent.state = "waiting_user"
        agent.cancel_write()
        assert agent.pending_write is None
        assert agent.state == "thinking"


class TestCheckExists:
    """只读工具，直接用假 db；确认它没有走 SQL 而是走 ORM"""

    def test_学生不存在时返回可读信息(self, agent, fake_db):
        class _Query:
            def filter(self, *a, **k):
                return self

            def first(self):
                return None

        class _DB:
            def query(self, model):
                return _Query()

        agent.db = _DB()
        assert "不存在" in agent._tool_check_exists({"type": "student", "name": "不存在的人"})

    def test_type_传错会返回错误提示(self, agent):
        assert "type 必须是" in agent._tool_check_exists({"type": "teacher", "name": "x"})

    def test_未知工具名返回可用工具列表(self, agent):
        assert "未知工具" in agent._execute_tool("hack_db", {})
