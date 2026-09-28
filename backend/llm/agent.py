"""
ReAct 自主 Agent —— LLM 思考→行动→观察 循环

Agent 不依赖关键词路由，而是根据知识库+工具描述自主决定：
  1. 当前需要什么信息
  2. 调用哪个工具获取
  3. 结果是否足够，要不要再查/再问
  4. 是否需要用户确认
"""
import json, re, traceback
from sqlalchemy import text
from sqlalchemy.orm import Session
from models import Student, Subject

try:  # 包内导入（正常情况）
    from .security import validate_read_sql, validate_write_sql
except ImportError:  # 直接以脚本方式运行 backend/llm/agent.py 时的兜底
    from security import validate_read_sql, validate_write_sql

# ===== Agent 系统提示词 =====
SYSTEM_PROMPT = """你是学生成绩管理系统的自主智能体。你可以独立思考、调用工具、维护任务状态。

## 你的能力
- 查询学生、科目、成绩数据
- 新增/修改/删除数据（会先跟你确认）
- 记住任务中间结果，多步完成任务
- 主动检查信息是否完整，不足时向用户提问

## 可用工具
1. check_exists(type, name) — 检查学生或科目是否存在，type 是 'student' 或 'subject'。**仅用于存在性判断，不查数据**
2. query_db(sql) — 执行 SELECT 查询，返回 JSON 数组。**仅在需要罗列/展示数据时使用，如成绩列表、排名、统计**
3. modify_db(sql, reason) — 修改数据库，参数: sql(完整SQL语句), reason(修改原因说明)。必须用户确认后才执行。
4. ask_user(question) — 向用户提问，等待回复后继续

## 工具选择
- 判断存在性 → check_exists，不要用 query_db
- 展示列表/排名/统计 → query_db（会自动渲染表格）
- 修改数据 → modify_db

## 数据库表结构
- students: student_id(VARCHAR 学号), name, gender(男/女), age → **INSERT 必须包含全部四列: student_id,name,gender,age**
- subjects: code(VARCHAR), name → INSERT 必须包含 code 和 name
- scores: student_id(VARCHAR 引用 students.student_id), subject_id(INT 引用 subjects.id), score(FLOAT) → **scores.student_id 是 VARCHAR 学号，不是 INT id**
- 学生: 张三(001) 李四(002) 王五(003) 赵六(004) 钱七(005)
- 科目: 语文 数学 英语 物理 化学 生物

## 响应格式
每轮你只能输出一个 ACT 执行一个工具，或输出一个 DONE 结束任务。
工具执行后你会收到 OBSERVATION，你可以继续思考下一步。

格式：
```
THOUGHT: <分析当前状态，决定下一步做什么，为什么>
ACT: tool_name({"arg": "value"})
```

或结束任务：
```
THOUGHT: <总结任务已完成>
DONE: <给用户的最终回复，自然语言>
```

## 重要规则
- **每轮只有一个 ACT 或一个 DONE**
- 先 check_exists 再操作，不要假设数据存在
- **写操作（INSERT/UPDATE/DELETE）禁止子查询**：安全层会拒绝。需要 subject_id 时直接用对照表 语文=1 数学=2 英语=3 物理=4 化学=5 生物=6
- **SQL 里不能出现注释和分号**（注释和多语句会被安全层直接拦截）
- 修改数据用 modify_db，系统会自动确认
- 对查到的数据，根据分数等级分析：A(90-100) B(80-89) C(70-79) D(60-69) 不及格(<60)
- 多步任务时记住前面步骤的结果
- 信息不完整时主动建议和引导，用商量语气
- **你是引导者，不是命令者**。禁止"请回复"、"告诉我"、"输入"等命令式用语。用"要不..."、"可以..."、"需要帮你..."这类建议式表达
- DONE 时给出简洁自然的回复，不要啰嗦
- **DONE 回复中禁止用 Markdown 表格（|---|），只用自然语言总结，数据会由系统自动渲染成表格展示**"""


class ReActAgent:
    """ReAct 自主 Agent —— 维护对话状态，执行工具调用循环"""

    def __init__(self, client, db_session: Session):
        self.client = client          # OpenAI 客户端
        self.db = db_session          # 数据库 session
        self.scratchpad = []          # [{"role":"thought","content":"..."}, {"role":"act",...}, {"role":"obs",...}]
        self.pending_write = None     # {"sql": str, "reason": str}  待确认的写操作
        self.last_question = None     # Agent 上轮向用户提的问题（用于上下文续接）
        self.state = "thinking"       # thinking | waiting_user | done
        self.user_reply = None        # 用户对 ask_user 的回复

    # ===== 工具实现 =====

    def _tool_query_db(self, args: dict) -> str:
        """执行 SELECT 查询 —— 必须先过 security.validate_read_sql（白名单 + 自动补 LIMIT）"""
        sql = args.get("sql", "").strip()
        ok, result = validate_read_sql(sql)
        if not ok:
            return f"SQL 被安全策略拒绝: {result}"
        try:
            rows = [dict(r._mapping) for r in self.db.execute(text(result)).fetchall()]
            if not rows:
                return "查询结果: 0 条记录"
            sample = rows[:20]
            return f"DATA:{len(rows)}:{json.dumps(sample, ensure_ascii=False, default=str)}"
        except Exception as e:
            return f"查询失败: {str(e)[:200]}"

    def _tool_modify_db(self, args: dict) -> str:
        """修改数据库 —— 校验通过后只挂起，等用户确认才落库"""
        sql = args.get("sql", "").strip()
        reason = args.get("reason", "无")
        ok, result = validate_write_sql(sql)
        if not ok:
            return f"SQL 被安全策略拒绝: {result}"

        self.pending_write = {"sql": result, "reason": reason}
        self.state = "waiting_user"
        return f"PENDING_CONFIRM: 即将 {result[:80]}... 原因: {reason}。等待用户确认。"

    def _tool_check_exists(self, args: dict) -> str:
        """检查学生/科目是否存在"""
        typ = args.get("type", "")
        name = args.get("name", "")
        if typ == "student":
            s = self.db.query(Student).filter(Student.name == name).first()
            return f"学生 '{name}' {'存在，学号: ' + s.student_id if s else '不存在'}"
        elif typ == "subject":
            s = self.db.query(Subject).filter(Subject.name == name).first()
            return f"科目 '{name}' {'存在，代码: ' + s.code if s else '不存在'}"
        return "错误: type 必须是 'student' 或 'subject'"

    def _tool_ask_user(self, args: dict) -> str:
        """向用户提问"""
        question = args.get("question", "")
        self.state = "waiting_user"
        self._pending_question = question
        return f"ASK_USER: {question}"

    # ===== 工具调度 =====

    def _execute_tool(self, tool_name: str, args: dict) -> str:
        """执行工具并返回观察结果"""
        tools = {
            "query_db": self._tool_query_db,
            "modify_db": self._tool_modify_db,
            "check_exists": self._tool_check_exists,
            "ask_user": self._tool_ask_user,
        }
        if tool_name in tools:
            return tools[tool_name](args)
        return f"错误: 未知工具 '{tool_name}'，可用: {list(tools.keys())}"

    # ===== 主循环 =====

    def step(self, user_input: str = None) -> dict:
        """
        执行一步 Agent 循环。返回:
          {"type": "thinking", "content": "..."}
          {"type": "acting", "tool": "...", "args": {...}}
          {"type": "observation", "content": "..."}
          {"type": "done", "reply": "..."}
          {"type": "waiting_user", "question": "..."}
          {"type": "confirm_required", "sql": "...", "reason": "..."}
          {"type": "error", "content": "..."}
        """
        # 如果上次是 ask_user 等待回复，现在用户回复了
        if self.state == "waiting_user" and user_input:
            # 用户回复了 ask_user 的问题
            self.user_reply = user_input
            self.scratchpad.append({"role": "obs", "content": f"用户回复: {user_input}"})
            self.state = "thinking"
            user_input = None  # 不要重复处理
        elif self.state == "waiting_user" and not user_input:
            return {"type": "waiting_user", "question": getattr(self, '_pending_question', '请回复')}

        # 构建对话
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        # 添加历史记录
        history_text = self._build_history()
        if history_text:
            messages.append({"role": "user", "content": history_text})

        if user_input:
            messages.append({"role": "user", "content": f"用户最新输入: {user_input}"})

        messages.append({"role": "user", "content": "请输出你的下一步 THOUGHT 和 ACT（或 DONE）："})

        # 调用 LLM
        try:
            resp = self.client.chat.completions.create(
                model="deepseek-v4-pro",
                messages=messages,
                max_tokens=800,
                stop=["\n\n\n"],  # 防止无意义空行导致提前截断
                extra_body={"thinking": {"type": "disabled"}},
            )
            content = resp.choices[0].message.content.strip()
        except Exception as e:
            return {"type": "error", "content": f"Agent 调用失败: {str(e)[:100]}"}

        # 解析 LLM 输出
        return self._parse_response(content)

    def _build_history(self) -> str:
        """构建对话历史文本，限制总长度避免超出上下文窗口"""
        if not self.scratchpad:
            return ""
        lines = []
        total = 0
        # 从最新往前取，总字符数不超过 2000
        for entry in reversed(self.scratchpad):
            role = entry["role"]
            content = entry["content"]
            if role == "thought":
                line = f"THOUGHT: {content}"
            elif role == "act":
                line = f"ACT: {content}"
            elif role == "obs":
                line = f"OBSERVATION: {content[:300]}"  # 观察结果截断
            else:
                continue
            if total + len(line) > 2000:
                break
            lines.insert(0, line)
            total += len(line)
        if not lines:
            return ""
        # 清理 scratchpad，只保留最近使用的条目
        keep = min(len(lines) * 2, len(self.scratchpad))
        self.scratchpad = self.scratchpad[-keep:]
        return "## 任务记录\n" + "\n".join(lines)

    def _parse_response(self, content: str) -> dict:
        """解析 LLM 响应，提取 THOUGHT/ACT 或 DONE"""
        # 提取 THOUGHT
        thought_match = re.search(r'THOUGHT:\s*(.+?)(?=\nACT:|\nDONE:|$)', content, re.DOTALL)
        thought = thought_match.group(1).strip() if thought_match else ""

        # 提取 ACT —— 用括号深度匹配，避免 JSON 内部括号干扰
        act_match = re.search(r'ACT:\s*(\w+)\(', content)
        tool_name = None
        args = {}
        if act_match:
            tool_name = act_match.group(1).strip()
            # 从 ( 之后开始，逐字符匹配括号深度
            start = act_match.end()
            depth = 1
            end = start
            while end < len(content) and depth > 0:
                ch = content[end]
                if ch == '(':
                    depth += 1
                elif ch == ')':
                    depth -= 1
                end += 1
            args_str = content[start:end-1].strip()
            # 解析 JSON
            try:
                args = json.loads(args_str)
            except json.JSONDecodeError:
                args = self._parse_simple_args(args_str)
        # 提取 DONE
        done_match = re.search(r'DONE:\s*(.+)', content, re.DOTALL)

        if tool_name:
            # 记录思考
            if thought:
                self.scratchpad.append({"role": "thought", "content": thought})

            # 执行工具
            act_desc = f"{tool_name}({json.dumps(args, ensure_ascii=False)})"
            self.scratchpad.append({"role": "act", "content": act_desc})

            observation = self._execute_tool(tool_name, args)
            self.scratchpad.append({"role": "obs", "content": observation})

            # 提取表格数据（query_db 的 DATA: 前缀）
            tableData = None
            tableCount = 0
            obs_text = observation
            if observation.startswith("DATA:"):
                parts = observation[5:].split(":", 1)
                tableCount = int(parts[0])
                try:
                    tableData = json.loads(parts[1])
                except:
                    pass
                obs_text = f"查询结果: 共 {tableCount} 条"

            # 特殊处理
            if observation.startswith("PENDING_CONFIRM"):
                return {
                    "type": "confirm_required",
                    "thought": thought,
                    "sql": self.pending_write["sql"],
                    "reason": self.pending_write.get("reason", ""),
                    "tool": tool_name, "args": args
                }
            if observation.startswith("ASK_USER"):
                question = observation.replace("ASK_USER: ", "", 1)
                return {
                    "type": "waiting_user",
                    "thought": thought,
                    "question": question
                }

            return {
                "type": "observation",
                "thought": thought,
                "tool": tool_name, "args": args,
                "content": obs_text,
                "tableData": tableData,
                "tableCount": tableCount,
            }

        if done_match:
            if thought:
                self.scratchpad.append({"role": "thought", "content": thought})
            reply = done_match.group(1).strip()
            self.scratchpad.append({"role": "done", "content": reply})
            self.state = "done"
            # 检测是否向用户提了问题（含"？"或"吗"），记住用于上下文续接
            if "？" in reply or "吗" in reply:
                self.last_question = reply
            return {"type": "done", "thought": thought, "reply": reply}

        # 解析失败，把原始输出当 DONE
        if thought:
            self.scratchpad.append({"role": "thought", "content": thought})
        self.state = "done"
        return {"type": "done", "thought": thought, "reply": content[:200]}

    def _parse_simple_args(self, args_str: str) -> dict:
        """简易参数解析（JSON 解析失败时的后备）—— 更鲁棒地提取 key:value"""
        result = {}
        # 尝试提取 "sql": "..." 或 'sql': '...'
        for key in ["sql", "reason", "type", "name", "question"]:
            # 匹配 "key": "value" 或 'key': 'value'
            m = re.search(r'["\']' + key + r'["\']\s*:\s*["\'](.+?)["\']', args_str, re.DOTALL)
            if m and key not in result:
                result[key] = m.group(1)
            # 匹配 "key": 数字
            m = re.search(r'["\']' + key + r'["\']\s*:\s*(\d+)', args_str)
            if m and key not in result:
                result[key] = int(m.group(1))
        # 如果还是空，把整个字符串当 raw
        if not result and args_str.strip():
            return {"raw": args_str.strip()}
        return result

    def confirm_write(self, db: Session) -> str:
        """用户确认写操作后执行 —— 执行前再校验一次（不信任 pending_write 的内容）"""
        if not self.pending_write:
            return "没有待确认的操作"
        raw_sql = self.pending_write["sql"]
        ok, result = validate_write_sql(raw_sql)
        if not ok:
            self.pending_write = None
            self.state = "thinking"
            return f"已阻止执行: {result}"
        sql = result
        try:
            result = db.execute(text(sql))
            db.flush()
            rowcount = result.rowcount
            db.commit()
            self.scratchpad.append({"role": "obs", "content": f"修改已执行: {sql[:80]}... 影响 {rowcount} 行"})
            self.pending_write = None
            self.state = "thinking"
            return f"已修改 {rowcount} 条记录"
        except Exception as e:
            traceback.print_exc()
            try:
                db.rollback()
            except:
                pass
            self.scratchpad.append({"role": "obs", "content": f"修改失败: {str(e)[:200]}"})
            self.pending_write = None
            self.state = "thinking"
            return f"执行失败: {str(e)[:200]}"

    def cancel_write(self):
        """用户取消写操作"""
        if self.pending_write:
            self.scratchpad.append({"role": "obs", "content": "用户取消了修改操作"})
            self.pending_write = None
        self.state = "thinking"

    def reset(self):
        """重置 Agent 状态"""
        self.scratchpad = []
        self.pending_write = None
        self.state = "thinking"
        self.user_reply = None
