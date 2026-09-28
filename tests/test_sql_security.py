"""
SQL 安全层单元测试 —— 这是整个项目最该有测试的地方。

为什么先测这里（面试话术）：
  Agent 的其他部分出错是"功能不好用"，安全层出错是"数据没了"。
  而且 security.py 全是纯函数（不碰 DB、不读全局状态），测试成本最低、价值最高。

运行：
    cd C:\\Users\\Lenovo\\DSH
    pytest student-score-system -v
"""

import pytest

from llm.security import (
    ALLOWED_TABLES,
    classify_intent,
    extract_tables,
    is_cancel,
    is_confirmation,
    validate_read_sql,
    validate_write_sql,
)


# ============================================================================
# 一、只读通道：该放行的
# ============================================================================

class TestReadSqlAllowed:
    def test_普通查询并自动补_LIMIT(self):
        ok, sql = validate_read_sql(
            "SELECT s.student_id, s.name, sc.score "
            "FROM students s JOIN scores sc ON s.student_id = sc.student_id "
            "WHERE sc.score < 60"
        )
        assert ok
        assert sql.endswith("LIMIT 200")

    def test_已有_LIMIT_不重复追加以免变成两个_LIMIT(self):
        ok, sql = validate_read_sql("SELECT * FROM students LIMIT 10")
        assert ok
        assert sql.count("LIMIT") == 1
        assert sql.endswith("LIMIT 10")

    def test_末尾分号会被剥掉(self):
        ok, sql = validate_read_sql("SELECT name FROM students;")
        assert ok
        assert ";" not in sql

    def test_三表_JOIN_加聚合函数(self):
        ok, _ = validate_read_sql(
            "SELECT su.name, AVG(sc.score) AS avg_score FROM scores sc "
            "JOIN subjects su ON sc.subject_id = su.id GROUP BY su.name"
        )
        assert ok

    def test_SUBSTR_这类带括号的函数不会误伤表名提取(self):
        ok, _ = validate_read_sql(
            "SELECT SUBSTR(s.name, 1, 1) FROM students s WHERE s.age > 18"
        )
        assert ok


# ============================================================================
# 二、只读通道：必须拦下的
# ============================================================================

class TestReadSqlBlocked:
    def test_非_SELECT_语句走读通道会被拒(self):
        ok, reason = validate_read_sql("DELETE FROM students")
        assert not ok
        assert "只允许" in reason

    def test_表名不在白名单会被拒(self):
        ok, reason = validate_read_sql("SELECT name FROM sqlite_master")
        assert not ok
        assert "白名单" in reason

    def test_行注释注入会被拒(self):
        """注释能把校验看到的 SQL 和数据库执行的 SQL 变成两条不同语句"""
        ok, reason = validate_read_sql("SELECT * FROM students -- AND active=1")
        assert not ok
        assert "注释" in reason

    def test_块注释注入会被拒(self):
        ok, reason = validate_read_sql("SELECT * FROM students /* 装成无害 */")
        assert not ok
        assert "注释" in reason

    def test_UNION_外带数据会被拒(self):
        ok, reason = validate_read_sql(
            "SELECT name FROM students UNION SELECT password FROM users"
        )
        assert not ok
        assert "UNION" in reason

    def test_多语句拼接会被拒(self):
        ok, reason = validate_read_sql("SELECT * FROM students; DROP TABLE scores")
        assert not ok

    def test_读通道里夹带_DDL_会被拒(self):
        ok, reason = validate_read_sql("SELECT 1 FROM students WHERE 1=1 DROP TABLE scores")
        assert not ok

    def test_无表名无法识别的_SQL_会被拒(self):
        """宁可拒绝也不要放行一个自己看不懂的语句"""
        ok, reason = validate_read_sql("SELECT 1")
        assert not ok
        assert "表名" in reason

    def test_空_SQL_会被拒(self):
        ok, _ = validate_read_sql("")
        assert not ok
        ok, _ = validate_read_sql("   ")
        assert not ok

    @pytest.mark.parametrize("sql", [
        "SELECT * FROM students WHERE name = :name",   # 有占位符没参数
    ])
    def test_有占位符没参数会被拒(self, sql):
        ok, reason = validate_read_sql(sql)
        assert not ok
        assert "占位符" in reason

    def test_有参数没占位符会被拒(self):
        ok, reason = validate_read_sql("SELECT * FROM students", params={"name": "张三"})
        assert not ok
        assert "占位符" in reason


# ============================================================================
# 三、写通道：该放行的
# ============================================================================

class TestWriteSqlAllowed:
    def test_带条件的_UPDATE(self):
        ok, sql = validate_write_sql(
            "UPDATE scores SET score = 80 WHERE student_id = '001' AND subject_id = 2"
        )
        assert ok
        assert ";" not in sql

    def test_带条件的_DELETE(self):
        ok, _ = validate_write_sql("DELETE FROM students WHERE student_id = '006'")
        assert ok

    def test_写明了列名的_INSERT(self):
        ok, _ = validate_write_sql(
            "INSERT INTO students (student_id, name, gender, age) "
            "VALUES ('006', '王小明', '男', 20)"
        )
        assert ok

    def test_末尾分号被剥掉后放行(self):
        ok, sql = validate_write_sql("DELETE FROM scores WHERE subject_id = 6;")
        assert ok
        assert not sql.endswith(";")


# ============================================================================
# 四、写通道：必须拦下的（第 3 层护栏）
# ============================================================================

class TestWriteSqlBlocked:
    def test_无条件_DELETE_会清空整表_必须拒(self):
        ok, reason = validate_write_sql("DELETE FROM students")
        assert not ok
        assert "WHERE" in reason

    def test_无条件_UPDATE_必须拒(self):
        ok, reason = validate_write_sql("UPDATE scores SET score = 0")
        assert not ok
        assert "WHERE" in reason

    def test_恒真_WHERE_等同于全表操作_必须拒(self):
        ok, reason = validate_write_sql("DELETE FROM scores WHERE student_id = student_id")
        assert not ok
        assert "恒真" in reason

    def test_写操作里的子查询会被拒(self):
        """这条规则对应真实事故：scores.student_id 是 VARCHAR 学号，不是自增 id"""
        ok, reason = validate_write_sql(
            "UPDATE scores SET score = 80 WHERE student_id = '001' "
            "AND subject_id = (SELECT id FROM subjects WHERE name = '数学')"
        )
        assert not ok
        assert "子查询" in reason

    def test_INSERT_不写列名会被拒(self):
        ok, reason = validate_write_sql("INSERT INTO students VALUES ('006','王小明','男',20)")
        assert not ok
        assert "列名" in reason

    def test_写通道里夹带_DDL_会被拒(self):
        ok, reason = validate_write_sql("DELETE FROM students WHERE student_id='006'; DROP TABLE scores")
        assert not ok

    def test_删表语句直接拒(self):
        ok, reason = validate_write_sql("DROP TABLE scores")
        assert not ok

    def test_ALTER_改表结构直接拒(self):
        ok, reason = validate_write_sql("ALTER TABLE students ADD COLUMN phone VARCHAR(20)")
        assert not ok

    def test_写通道访问白名单外的表会被拒(self):
        ok, reason = validate_write_sql("DELETE FROM users WHERE id = 1")
        assert not ok
        assert "白名单" in reason


# ============================================================================
# 五、表名提取
# ============================================================================

class TestExtractTables:
    def test_提取_FROM_和_JOIN_上的表(self):
        tables = extract_tables(
            "SELECT * FROM students s JOIN scores sc ON s.student_id = sc.student_id "
            "JOIN subjects su ON sc.subject_id = su.id"
        )
        assert tables == {"students", "scores", "subjects"}

    def test_表名大小写不敏感(self):
        assert extract_tables("SELECT * FROM STUDENTS") == {"students"}

    def test_白名单常量内容正确(self):
        assert ALLOWED_TABLES == {"students", "subjects", "scores"}


# ============================================================================
# 六、意图分类与确认识别
# ============================================================================

class TestIntent:
    @pytest.mark.parametrize("text", ["你好", "hi", "你是谁", "谢谢"])
    def test_问候语(self, text):
        assert classify_intent(text) == "greeting"

    @pytest.mark.parametrize("text", ["张三数学多少分", "列出所有不及格的学生", "删除学号006的学生"])
    def test_成绩域(self, text):
        assert classify_intent(text) == "score_query"

    @pytest.mark.parametrize("text", ["今天天气怎么样", "讲个笑话", "帮我写首诗"])
    def test_无关问题默认拒绝(self, text):
        """默认安全姿态：拿不准就不进业务/写库流程"""
        assert classify_intent(text) == "unrelated"

    def test_空输入(self):
        assert classify_intent("") == "unrelated"


class TestConfirmation:
    @pytest.mark.parametrize("text", ["确认", "好的", "yes", "可以执行"])
    def test_确认(self, text):
        assert is_confirmation(text)

    def test_不行_不能被误判成确认(self):
        """关键词匹配的经典陷阱：'不行' 里含有 '行'"""
        assert not is_confirmation("不行")

    @pytest.mark.parametrize("text", ["取消", "算了", "no"])
    def test_取消(self, text):
        assert is_cancel(text)

    def test_空输入不算确认(self):
        assert not is_confirmation("")
