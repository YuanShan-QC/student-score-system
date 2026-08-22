#!/usr/bin/env python
"""
FastAPI 应用入口 —— 学生成绩管理系统 API
启动：cd backend && python main.py
文档：http://localhost:8080/docs
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ===== 数据库初始化（首次启动时建表+种子数据）=====
from database import engine, Base, SessionLocal
from models import Student, Subject, Score  # 确保模型注册

Base.metadata.create_all(bind=engine)

# 种子数据（表空时才插入）
db_init = SessionLocal()
try:
    if db_init.query(Student).count() == 0:
        import random
        random.seed(42)
        subjects_data = [
            Subject(code="CHN", name="语文"), Subject(code="MATH", name="数学"),
            Subject(code="ENG", name="英语"), Subject(code="PHY", name="物理"),
            Subject(code="CHEM", name="化学"), Subject(code="BIO", name="生物"),
        ]
        db_init.add_all(subjects_data)
        db_init.flush()
        sub_map = {s.code: s for s in subjects_data}
        students_data = [
            Student(student_id="001", name="张三", gender="男", age=18),
            Student(student_id="002", name="李四", gender="女", age=19),
            Student(student_id="003", name="王五", gender="男", age=18),
            Student(student_id="004", name="赵六", gender="女", age=20),
            Student(student_id="005", name="钱七", gender="男", age=19),
        ]
        db_init.add_all(students_data)
        scores_data = [
            ("001","CHN",85),("001","MATH",55),("001","ENG",78),("001","PHY",92),("001","CHEM",67),
            ("002","CHN",72),("002","MATH",88),("002","ENG",45),("002","PHY",76),("002","CHEM",90),
            ("003","CHN",95),("003","MATH",62),("003","ENG",81),("003","PHY",58),("003","CHEM",73),
            ("004","CHN",68),("004","MATH",91),("004","ENG",74),("004","PHY",85),("004","CHEM",53),
            ("005","CHN",77),("005","MATH",49),("005","ENG",88),("005","PHY",69),("005","CHEM",94),
        ]
        for sid, code, score_val in scores_data:
            db_init.add(Score(student_id=sid, subject_id=sub_map[code].id, score=score_val))
        db_init.commit()
        print("[INIT] 种子数据: 6科 5生 25条成绩")
    else:
        print("[INIT] 数据库已有数据，跳过种子初始化")
except Exception as e:
    db_init.rollback()
    print(f"[INIT] 种子数据失败: {e}")
finally:
    db_init.close()

# ===== FastAPI 应用初始化 =====
app = FastAPI(title="学生成绩管理系统")

# ===== CORS 中间件：Vite 开发服务器可能漂移到 5173/5174/5175 =====
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== 健康检查 =====
@app.get("/")
def root():
    """健康检查：确认 API 运行中，并告知文档地址"""
    return {"message": "API running", "docs": "/docs"}


# ===== 路由注册 =====
from routers import subjects, students, scores, ai, stats
app.include_router(subjects.router)
app.include_router(students.router)
app.include_router(scores.router)
app.include_router(ai.router)
app.include_router(stats.router)


# ===== 启动入口 =====
import uvicorn
uvicorn.run(app, host="0.0.0.0", port=8080)
