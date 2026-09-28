"""
SQL 安全层 —— Agent 生成的所有 SQL 必须经过这里才能落库。

设计原则（三层防护，面试口径）：
  第 1 层 语句结构校验   —— 单语句、禁注释、禁 DDL、禁 UNION、操作类型与通道匹配
  第 2 层 表名白名单     —— 只能碰 students / subjects / scores
  第 3 层 破坏性操作护栏 —— 写操作必须有真实 WHERE、禁止子查询、必须经用户二次确认

与旧版的区别（这是本次修复的核心）：
  旧版 validate_sql() 只做了一件事：查分号。DANGEROUS_PATTERN 定义了但从未被调用，
  表名白名单散落在 agent.py 里、只读通道（query_db）完全没有校验 —— 等于文档里写
  "三层防护"，代码里只有零层。现在三层全部收在本文件，agent.py 只负责调用。

所有校验函数都是纯函数：不碰数据库、不读全局状态，所以能脱离 DB 单独测试
（见 tests/test_sql_security.py，52 个断言）。
"""

import re

# ============================================================================
# 常量
# ============================================================================

#: 允许操作的表 —— 白名单，不在其中的一律拒绝
ALLOWED_TABLES = frozenset({"students", "subjects", "scores"})

#: 结构性破坏操作 —— 任何语句里出现都直接拒绝
DANGEROUS_KEYWORDS = ("DROP", "ALTER", "TRUNCATE", "CREATE", "REPLACE", "GRANT", "ATTACH", "PRAGMA", "VACUUM")

#: 注释语法 —— 注释可以把校验器看到的 SQL 和执行时生效的 SQL 变成两条不同的语句，必须全禁
COMMENT_TOKENS = ("--", "/*", "*/", "#")

#: 读通道允许的起始关键字
READ_PREFIXES = ("SELECT", "WITH")

#: 写通道允许的起始关键字
WRITE_PREFIXES = ("INSERT", "UPDATE", "DELETE")

#: 查询结果默认上限（防止 LLM 写出全表扫描把 20 条截断逻辑撑爆）
DEFAULT_LIMIT = 200

#: 表名提取：抓 FROM / JOIN / UPDATE / INTO 后面紧跟的标识符
_TABLE_RE = re.compile(r"\b(?:FROM|JOIN|UPDATE|INTO)\s+([A-Za-z_][A-Za-z0-9_]*)", re.IGNORECASE)

#: 占位符：SQLAlchemy 具名参数（:name）或 DBAPI 问号参数
_PLACEHOLDER_RE = re.compile(r"(?<![:/\w]):([A-Za-z_][A-Za-z0-9_]*)|\?")

#: 恒真 WHERE —— UPDATE/DELETE 写成这样等于全表操作，必须拦住。
#: 注意 [A-Za-z_] 而非 [\w]：写成 \w 会把 `subject_id = 6` 这种
#: "列 = 数字字面量"的**正常条件**也判成恒真（测试跑出来的真实 bug）。
_TAUTOLOGY_RE = re.compile(
    r"WHERE\s+(?:1\s*=\s*1|'[^']*'\s*=\s*'[^']*'|([A-Za-z_]\w*)\s*=\s*\1)\s*$",
    re.IGNORECASE,
)

#: LIMIT 子句检测（只看语句末尾，避免误判子查询里的 LIMIT）
_LIMIT_TAIL_RE = re.compile(r"\bLIMIT\s+\d+\s*$", re.IGNORECASE)

#: 子查询检测 —— 写操作里的子查询是"学号被当成自增 id"这类事故的温床
_SUBQUERY_RE = re.compile(r"\(\s*SELECT\b", re.IGNORECASE)


# ============================================================================
# 内部工具
# ============================================================================

def _strip_trailing_semicolon(sql: str) -> str:
    """去掉语句末尾的分号（唯一合法的分号位置）"""
    s = sql.strip()
    while s.endswith(";"):
        s = s[:-1].strip()
    return s


def _check_common(sql: str) -> str | None:
    """
    三层里第 1 层中所有通道共用的检查。

    返回 None 表示通过；返回字符串表示拒绝原因（即给 Agent/用户的提示语）。
    """
    upper = sql.upper()

    # 1) 注释：注释之后的校验都是自欺欺人
    for token in COMMENT_TOKENS:
        if token in sql:
            return f"禁止 SQL 注释（{token}）：注释会让校验看到的语句和实际执行的不是同一条"

    # 2) 分号：走到这里末尾分号已被剥掉，再出现分号 = 多语句拼接
    if ";" in sql:
        return "禁止多语句操作（SQL 中不允许出现分号）"

    # 3) DDL / 结构性危险关键字
    for kw in DANGEROUS_KEYWORDS:
        if re.search(rf"\b{kw}\b", upper):
            return f"禁止 {kw} 操作（结构性变更请走数据库迁移，不允许由模型生成）"

    return None


def extract_tables(sql: str) -> set[str]:
    """
    提取语句里引用到的表名。

    局限（面试要主动说出来）：正则提取无法处理 CTE（WITH t AS ...）、
    动态表名、反引号/引号包裹的表名。本系统的 SQL 由固定 Prompt 生成、
    表数量只有 3 张，正则够用；生产环境应改用 SQL 解析器（如 sqlglot）。
    """
    return {m.group(1).lower() for m in _TABLE_RE.finditer(sql)}


def _check_tables(sql: str) -> str | None:
    """第 2 层：表名白名单"""
    tables = extract_tables(sql)
    if not tables:
        return "无法识别 SQL 中的表名，拒绝执行（请检查 FROM/JOIN 是否完整）"
    illegal = tables - ALLOWED_TABLES
    if illegal:
        return f"表名不在白名单中: {sorted(illegal)}，只允许 {sorted(ALLOWED_TABLES)}"
    return None


# ============================================================================
# 第 1+2 层：读通道（SELECT）
# ============================================================================

def validate_read_sql(sql: str, params: dict | None = None,
                      max_limit: int = DEFAULT_LIMIT) -> tuple[bool, str]:
    """
    校验只读 SQL。

    返回 (is_valid, sql_or_reason)：
      通过 → (True, 已清洗并补好 LIMIT 的 SQL)
      拒绝 → (False, 拒绝原因)

    检查项：单语句 / 无注释 / 无 DDL / 以 SELECT 或 WITH 开头 / 无 UNION 外带 /
            表名白名单 / 占位符与参数配对 / 自动补 LIMIT。
    """
    sql_clean = _strip_trailing_semicolon(sql or "")

    if not sql_clean:
        return False, "SQL 为空"

    if not sql_clean.upper().startswith(READ_PREFIXES):
        return False, f"query_db 只允许 {'/'.join(READ_PREFIXES)} 语句"

    reason = _check_common(sql_clean)
    if reason:
        return False, reason

    # UNION 可以把另一张表的数据"合法地"拼进结果集，读通道直接禁掉
    if re.search(r"\bUNION\b", sql_clean, re.IGNORECASE):
        return False, "只读查询禁止 UNION（防止用合法查询外带其他表数据）"

    reason = _check_tables(sql_clean)
    if reason:
        return False, reason

    # 占位符必须与参数配对：有占位符没参数 → 执行必报错；有参数没占位符 → 参数被静默忽略
    has_placeholder = bool(_PLACEHOLDER_RE.search(sql_clean))
    if has_placeholder and not params:
        return False, "SQL 含占位符但没有提供参数（请直接把字面量写进 SQL，或同时提供 params）"
    if params and not has_placeholder:
        return False, "提供了参数但 SQL 中没有占位符（参数会被忽略，疑似拼接错误）"

    # 自动补 LIMIT
    if not _LIMIT_TAIL_RE.search(sql_clean):
        sql_clean = f"{sql_clean} LIMIT {max_limit}"

    return True, sql_clean


# ============================================================================
# 第 1+2+3 层：写通道（INSERT / UPDATE / DELETE）
# ============================================================================

def validate_write_sql(sql: str) -> tuple[bool, str]:
    """
    校验写 SQL（必须经用户二次确认后才真正执行）。

    返回 (is_valid, sql_or_reason)。

    第 3 层护栏：
      - UPDATE / DELETE 必须有 WHERE，且 WHERE 不能是恒真条件
      - 写语句禁止子查询（现实事故：scores.student_id 写成按自增 id 子查询）
      - INSERT 必须写明列名（否则列顺序一变就写错）
    """
    sql_clean = _strip_trailing_semicolon(sql or "")

    if not sql_clean:
        return False, "SQL 为空"

    upper = sql_clean.upper()

    if not upper.startswith(WRITE_PREFIXES):
        return False, f"modify_db 只允许 {'/'.join(WRITE_PREFIXES)} 语句"

    reason = _check_common(sql_clean)
    if reason:
        return False, reason

    reason = _check_tables(sql_clean)
    if reason:
        return False, reason

    if _SUBQUERY_RE.search(sql_clean):
        return False, ("写操作禁止子查询：请先从数据库查到真实的 id/学号，"
                       "再用字面量写第二条语句，避免把学号当自增 id 这类事故")

    if upper.startswith("UPDATE"):
        if not re.search(r"\bWHERE\b", upper):
            return False, "UPDATE 必须带 WHERE 条件（禁止无条件全表更新）"
    elif upper.startswith("DELETE"):
        if not re.search(r"\bWHERE\b", upper):
            return False, "DELETE 必须带 WHERE 条件（禁止清空整表）"
    elif upper.startswith("INSERT"):
        if not re.search(r"\bINTO\s+\w+\s*\(", sql_clean, re.IGNORECASE):
            return False, "INSERT 必须显式写明列名，如 INSERT INTO students (a, b) VALUES (...)"

    # 恒真条件：只有 UPDATE/DELETE 需要检查
    if upper.startswith(("UPDATE", "DELETE")) and _TAUTOLOGY_RE.search(sql_clean):
        return False, "WHERE 条件恒真，等同于全表操作，拒绝执行"

    return True, sql_clean


# ============================================================================
# 意图分类（保留：供 Agent 前置路由 / 单测使用，默认安全姿态是"拒绝"）
# ============================================================================

#: 问候语 —— 命中后不进 SQL 流程
GREETING_WORDS = [
    "你好", "您好", "嗨", "hi", "hello", "hey",
    "早上好", "下午好", "晚上好",
    "你是谁", "你能做什么", "有什么功能", "介绍一下",
    "谢谢", "感谢", "thanks",
    "再见", "拜拜", "bye",
]

#: 成绩域关键词 —— 命中后进入业务处理
SCORE_KEYWORDS = [
    "成绩", "分数", "多少分", "得分", "考",
    "学生", "学号", "同学", "姓名",
    "科目", "语文", "数学", "英语", "物理", "化学", "生物",
    "总分", "平均分", "平均", "最高分", "最低分",
    "及格", "不及格", "优秀", "排名", "排行",
    "统计", "汇总", "查询", "列出", "显示", "查看",
    "大于", "小于", "等于", "超过", "低于",
    "男生", "女生", "年龄", "性别",
    "哪些", "有几个", "谁", "哪个",
    "删除", "删掉", "删了", "移除", "清空",
    "修改", "改动", "改掉", "改一下", "更改", "更新", "改成", "改为",
    "插入", "新增", "添加", "写入", "录入",
    "创建", "建表", "新建", "修改为", "设置为",
    "delete", "update", "insert", "select",
]

#: 肯定 / 否定 —— 只在"确认识别"这一个场景使用。
#: 否定词必须收全：`不行` 里含有确认词 `行`，漏掉它就会把"拒绝"当成"同意"。
CONFIRM_WORDS = ["确认", "是", "是的", "好的", "可以", "行", "执行", "同意",
                 "confirm", "yes", "ok", "okay", "proceed"]
CANCEL_WORDS = ["取消", "不要", "不用", "不行", "不能", "不必", "不需要",
                "算了", "不了", "no", "cancel"]


def classify_intent(text: str) -> str:
    """
    三分类：'greeting' | 'score_query' | 'unrelated'。

    顺序很重要：**先判问候语再判业务关键词**。
    原因（测试跑出来的真实 bug）："你是谁" 同时命中问候词表和业务词表里的 "谁"，
    如果业务优先，一句问候会被拖进 SQL 生成流程。

    已知局限（面试要主动说）：这是关键词 `in` 匹配，不是语义分类。
    它的作用只是**前置粗筛**，真正的安全边界是 validate_*_sql 那三层，
    所以即使分类判错，也不会导致越权写库。
    """
    lower = (text or "").lower().strip()
    if not lower:
        return "unrelated"
    if any(w in lower for w in GREETING_WORDS):
        return "greeting"
    if any(w in lower for w in SCORE_KEYWORDS):
        return "score_query"
    return "unrelated"


def is_confirmation(text: str) -> bool:
    """
    用户是否确认执行待定的写操作。

    两道否定优先检查（都是测试跑出来的真实 bug）：
      1. 整句等于否定词 → 判为否认，避免 "不行" 里的 "行" 被误判成确认；
      2. 整句**包含**否定词 → 也判为否认，避免 "算了吧不要了" 被确认识别吃掉。
    仍然拦不住的边角情况（要老实承认）："不是不行"、"我不确定，先确认一下" 这类
    双重否定/否定加肯定混写，纯关键词匹配分不出来。所以真正执行前，
    前端必须让用户**明确点"确认"按钮**，聊天文本只能当作辅助信号。
    """
    lower = (text or "").lower().strip()
    if not lower:
        return False
    if lower in CANCEL_WORDS or any(w in lower for w in CANCEL_WORDS):
        return False
    return any(w in lower for w in CONFIRM_WORDS)


def is_cancel(text: str) -> bool:
    """用户是否取消待定的写操作"""
    return any(w in (text or "").lower() for w in CANCEL_WORDS)
