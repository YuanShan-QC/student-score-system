"""
学校知识库 —— 为智能查询智能体提供成绩等级规则
"""

# ===== 学校配置 =====
SCHOOL_CONFIG = {
    "name": "湖南科技大学",
    "subjects": ["语文", "数学", "英语", "物理", "化学", "生物"],
}

# ===== 分数等级标准 =====
SCORE_THRESHOLDS = """
等级：
- 90-100：A（优秀）
- 80-89：B（良好）
- 70-79：C（中等）
- 60-69：D（及格）
- <60：不及格
"""

# ===== 等级对应的建议 =====
IMPROVEMENT_STRATEGIES = """
- A级（90-100）：优秀，可担任课代表或助教
- B级（80-89）：良好，可推荐参加学科竞赛
- C级（70-79）：中等，可适当布置拔高题查漏补缺
- D级（60-69）：及格，建议加强基础练习
- 不及格（<60）：建议重点关注，安排课后辅导或补考
"""


def get_knowledge_base() -> str:
    school = SCHOOL_CONFIG
    return f"""
## 分数等级
{SCORE_THRESHOLDS.strip()}

## 等级建议
{IMPROVEMENT_STRATEGIES.strip()}
"""


def get_analysis_prompt(query: str, sql: str, data: list, count: int, history: str = "") -> str:
    kb = get_knowledge_base()
    data_sample = json.dumps(data[:5], ensure_ascii=False) if data else "无数据"
    name = SCHOOL_CONFIG["name"]

    context = f"对话历史:\n{history}" if history.strip() else ""

    if count == 0:
        return f"""{context}

你是{name}的成绩管理助手，性格友好但不啰嗦，回答不要总是用模板句式。

用户刚问：{query}
数据库里没有查到任何结果。

请你根据自己的判断，用自然的口吻回复用户。比如：
- 如果是不存在的科目 → 告诉用户没有，问要不要新建
- 如果是不存在的学生 → 告诉用户没找到，可以帮忙添加
- 如果是缺成绩数据 → 说还没录入，问要不要帮忙录
- 其他情况 → 简单说明没查到

关键是说话要有变化，不要每次都一样。不超过40字。"""

    return f"""{context}

{kb}

## 当前查询
用户问题：{query}
查询结果：共 {count} 条，前5条：{data_sample}

## 你的角色
你是{name}的成绩管理助手，回复风格友好但不啰嗦，说话不要总是套模板。
根据成绩等级标准给出分析。

注意：回复尽量简短，2-3句话以内，点出关键信息和一条建议就够了。"""
