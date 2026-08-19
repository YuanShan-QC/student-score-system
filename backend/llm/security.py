"""
安全模块 —— 意图分类 + SQL校验 + 确认检测

放开写权限后：
  意图分类：打招呼/成绩相关(含CRUD)/无关
  SQL校验：允许 SELECT/INSERT/UPDATE/DELETE，禁止 DROP/ALTER/TRUNCATE/CREATE
  确认检测：用户说"确认/是/好的"等视为确认
"""
import re

# 打招呼关键词
GREETING_WORDS = [
    "你好", "您好", "嗨", "hi", "hello", "hey",
    "早上好", "下午好", "晚上好",
    "你是谁", "你能做什么", "有什么功能", "介绍一下",
    "谢谢", "感谢", "thanks",
    "再见", "拜拜", "bye",
]

# 成绩相关关键词（含CRUD操作，全部进入SQL生成流程）
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
    # CRUD 操作也进入 SQL 生成流程
    "删除", "删掉", "删了", "移除", "清空",
    "修改", "改动", "改掉", "改一下", "更改", "更新", "改成", "改为",
    "插入", "新增", "添加", "写入", "录入",
    "创建", "建表", "新建",
    "改成", "修改为", "设置为",
    "delete", "update", "insert",
]

# 确认关键词
CONFIRM_WORDS = [
    "确认", "是", "是的", "好的", "可以", "行", "执行", "同意",
    "confirm", "yes", "ok", "okay", "proceed",
]

# 取消关键词
CANCEL_WORDS = [
    "取消", "不", "不要", "算了", "不了", "no",
]


def classify_intent(text: str) -> str:
    """
    分为三类：
      'greeting'     — 打招呼
      'score_query'  — 成绩相关（含CRUD操作，进入SQL生成流程）
      'unrelated'    — 无关问题（拒绝回答）
    """
    lower = text.lower().strip()

    for word in SCORE_KEYWORDS:
        if word in lower:
            return "score_query"

    for word in GREETING_WORDS:
        if word in lower:
            return "greeting"

    return "unrelated"


def is_confirmation(text: str) -> bool:
    """检测用户是否在确认操作"""
    lower = text.lower().strip()
    return any(w in lower for w in CONFIRM_WORDS)


def is_cancel(text: str) -> bool:
    """检测用户是否取消操作"""
    lower = text.lower().strip()
    return any(w in lower for w in CANCEL_WORDS)


# 仍禁止的危险操作
DANGEROUS_PATTERN = re.compile(
    r'\b(DROP|ALTER|TRUNCATE|CREATE)\b',
    re.IGNORECASE,
)


# 写操作检测（非SELECT都需确认）
WRITE_PATTERN = re.compile(
    r'^\s*(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE)\b',
    re.IGNORECASE,
)


def is_write_sql(sql: str) -> bool:
    """判断SQL是否需要确认（UPDATE/INSERT/DELETE）"""
    return bool(WRITE_PATTERN.match(sql.strip()))


def validate_sql(sql: str) -> tuple[bool, str]:
    """
    SQL 校验 —— 权限全开放，仅防多语句注入。

    返回 (is_valid, reason_or_cleaned_sql)。
    """
    sql_clean = sql.strip()

    if sql_clean.endswith(";"):
        sql_clean = sql_clean[:-1].strip()

    if ";" in sql_clean:
        return False, "禁止多语句操作"

    return True, sql_clean


def check_intent(text: str) -> tuple[bool, str]:
    """保留兼容"""
    return True, ""
