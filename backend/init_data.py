"""
建表 + 插入演示数据（执行一次即可，重复执行不会重复插入）
"""
from database import engine, SessionLocal, Base
from models import Student, Subject, Score

# ===== 第一步：建表（已存在的表不会重复创建）=====
print("正在建表...")
Base.metadata.create_all(bind=engine)
print("建表完成！")

# ===== 第二步：插入种子数据 =====
db = SessionLocal()
try:
    if db.query(Student).count() > 0:
        print("数据已存在，跳过初始化。")
    else:
        # ---- 科目（6 科）----
        subjects_data = [
            Subject(code="CHN",  name="语文"),
            Subject(code="MATH", name="数学"),
            Subject(code="ENG",  name="英语"),
            Subject(code="PHY",  name="物理"),
            Subject(code="CHEM", name="化学"),
            Subject(code="BIO",  name="生物"),
        ]
        db.add_all(subjects_data)
        db.flush()  # 先 flush 让科目获得 id，后续成绩插入需要 subject_id

        # 建立 code → Subject 对象的映射
        sub_map = {s.code: s for s in subjects_data}

        # ---- 学生（5 人）----
        students_data = [
            Student(student_id="001", name="张三", gender="男", age=18),
            Student(student_id="002", name="李四", gender="女", age=19),
            Student(student_id="003", name="王五", gender="男", age=18),
            Student(student_id="004", name="赵六", gender="女", age=20),
            Student(student_id="005", name="钱七", gender="男", age=19),
        ]
        db.add_all(students_data)

        # ---- 成绩（25 条：每人 5 科，含不及格和优秀分）----
        # 分数刻意包含：不及格(<60)、及格(60-79)、良好(80-89)、优秀(≥90)
        scores_data = [
            # 张三：数学不及格，物理优秀
            ("001", "CHN",  85), ("001", "MATH", 55),
            ("001", "ENG",  78), ("001", "PHY",  92),
            ("001", "CHEM", 67),
            # 李四：英语不及格，化学优秀
            ("002", "CHN",  72), ("002", "MATH", 88),
            ("002", "ENG",  45), ("002", "PHY",  76),
            ("002", "CHEM", 90),
            # 王五：语文优秀，物理不及格
            ("003", "CHN",  95), ("003", "MATH", 62),
            ("003", "ENG",  81), ("003", "PHY",  58),
            ("003", "CHEM", 73),
            # 赵六：数学优秀，化学不及格
            ("004", "CHN",  68), ("004", "MATH", 91),
            ("004", "ENG",  74), ("004", "PHY",  85),
            ("004", "CHEM", 53),
            # 钱七：数学不及格，化学优秀
            ("005", "CHN",  77), ("005", "MATH", 49),
            ("005", "ENG",  88), ("005", "PHY",  69),
            ("005", "CHEM", 94),
        ]
        for student_id, code, score_val in scores_data:
            db.add(Score(
                student_id=student_id,
                subject_id=sub_map[code].id,
                score=score_val,
            ))

        db.commit()
        print("Init done: 5 subjects, 5 students, 25 scores")
finally:
    db.close()
