"""
Schema + Prompt 生成 —— 返回 DDL 建表语句和自然语言转 SQL 的提示词
"""
from sqlalchemy.orm import Session
from models import Subject


def get_schema_info(db: Session | None = None) -> tuple[str, str]:
    """
    返回 (DDL, Prompt模板)。

    如果传入 db session，会从数据库动态读取所有科目；
    否则使用硬编码默认值。
    """

    # 读取真实科目
    if db is not None:
        try:
            subs = db.query(Subject).all()
            sub_names = [s.name for s in subs]
            sub_codes = [s.code for s in subs]
        except Exception:
            sub_names = ["语文", "数学", "英语", "物理", "化学"]
            sub_codes = ["CHN", "MATH", "ENG", "PHY", "CHEM"]
    else:
        sub_names = ["语文", "数学", "英语", "物理", "化学"]
        sub_codes = ["CHN", "MATH", "ENG", "PHY", "CHEM"]

    sub_list = "/".join([f"{n}({c})" for n, c in zip(sub_names, sub_codes)])

    ddl = f"""
CREATE TABLE students (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id VARCHAR(20) NOT NULL UNIQUE,
    name       VARCHAR(50) NOT NULL,
    gender     VARCHAR(2) NOT NULL,
    age        INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE subjects (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    code VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(50) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE scores (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id VARCHAR(20) NOT NULL,
    subject_id INTEGER NOT NULL,
    score      REAL NOT NULL CHECK(score >= 0 AND score <= 100),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(student_id),
    FOREIGN KEY (subject_id) REFERENCES subjects(id),
    UNIQUE (student_id, subject_id)
);
""".strip()

    prompt = f"""你是 SQL 生成器。根据用户输入生成一条 SQL（SELECT/INSERT/UPDATE/DELETE）。

## 数据库
{ddl}

## 当前数据
- 学生: 张三(001)/李四(002)/王五(003)/赵六(004)/钱七(005)
- 科目: {sub_list}
- 成绩范围: 45~98

## 规则（表名只有 students、subjects、scores 三个）
1. 支持 SELECT/INSERT/UPDATE/DELETE 全部操作
2. FROM/JOIN 必须完整，ON 条件不能省
3. <60 不及格，≥90 为A级
4. scores 别名 sc，students 别名 s，subjects 别名 su
5. **查询科目成绩时必须 JOIN subjects 表，scores 表没有 name/code/subject 列，只有 subject_id**
6. students列: id,student_id,name,gender,age  |  subjects列: id,code,name  |  scores列: id,student_id,subject_id,score
7. **CRITICAL: scores.student_id 引用 students.student_id（VARCHAR学号如'001'），不是 students.id（INT自增）！写 INSERT 时子查询用 SELECT student_id FROM students，不是 SELECT id FROM students**

## 重要
- 用户明确说"添加"/"新建"/"录入"/"插入" → 生成对应的 INSERT（不管数据是否已存在，都用 INSERT）
- 用户说"改成"/"修改"/"改为"/"更新" → 生成 UPDATE
- 用户说"删除"/"删掉" → 生成 DELETE
- 用户只是查询 → 只生成 SELECT，即使数据不存在也只查不建

## 示例
示例1 → 查询数学不及格的学生
SELECT s.student_id, s.name, sc.score FROM students s JOIN scores sc ON s.student_id=sc.student_id JOIN subjects su ON sc.subject_id=su.id WHERE su.name='数学' AND sc.score<60

示例2 → 把张三的数学成绩改成80分
UPDATE scores SET score=80 WHERE student_id='001' AND subject_id=(SELECT id FROM subjects WHERE name='数学')

示例3 → 添加一个新学生王小明，学号006
INSERT INTO students (student_id, name, gender, age) VALUES ('006', '王小明', '男', 20)

示例4 → 删除学号006的学生
DELETE FROM students WHERE student_id='006'

示例5 → 添加科目生物
INSERT INTO subjects (code, name) VALUES ('BIO', '生物')

示例6 → 录入张三的生物成绩89分
INSERT INTO scores (student_id, subject_id, score) VALUES ('001', (SELECT id FROM subjects WHERE name='生物'), 89)

## 用户查询
{{query}}

只输出一条 SQL，不要解释、不要 markdown、不要任何自然语言。"""
    return ddl, prompt
