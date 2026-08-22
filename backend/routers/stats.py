"""
统计路由 —— /api/stats（数据看板用）
返回学生数、科目数、成绩数、平均分、及格率、各科目平均分、分数段分布
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
from models import Student, Subject, Score

router = APIRouter(prefix="/api/stats", tags=["数据统计"])


@router.get("")
def get_stats(db: Session = Depends(get_db)):
    """聚合统计数据，供首页数据看板展示"""
    student_count = db.query(func.count(Student.id)).scalar() or 0
    subject_count = db.query(func.count(Subject.id)).scalar() or 0
    score_count = db.query(func.count(Score.id)).scalar() or 0

    # 平均分、最高分、最低分
    avg_score = db.query(func.avg(Score.score)).scalar()
    max_score = db.query(func.max(Score.score)).scalar()
    min_score = db.query(func.min(Score.score)).scalar()

    # 及格率（>=60 为及格）
    pass_count = db.query(func.count(Score.id)).filter(Score.score >= 60).scalar() or 0
    pass_rate = round(pass_count / score_count * 100, 1) if score_count else 0.0

    # 各科目平均分
    subject_avg = (
        db.query(Subject.name, func.avg(Score.score), func.count(Score.id))
        .join(Score, Score.subject_id == Subject.id)
        .group_by(Subject.id, Subject.name)
        .order_by(Subject.id)
        .all()
    )
    subject_stats = [
        {
            "name": name,
            "avg": round(avg, 1) if avg is not None else 0.0,
            "count": cnt,
        }
        for name, avg, cnt in subject_avg
    ]

    # 分数段分布
    brackets = [
        ("不及格(0-59)", 0, 60),
        ("及格(60-69)", 60, 70),
        ("中等(70-79)", 70, 80),
        ("良好(80-89)", 80, 90),
        ("优秀(90-100)", 90, 101),
    ]
    distribution = []
    for label, low, high in brackets:
        cnt = (
            db.query(func.count(Score.id))
            .filter(Score.score >= low, Score.score < high)
            .scalar()
            or 0
        )
        distribution.append({"label": label, "count": cnt})

    return {
        "student_count": student_count,
        "subject_count": subject_count,
        "score_count": score_count,
        "avg_score": round(avg_score, 1) if avg_score is not None else 0.0,
        "max_score": round(max_score, 1) if max_score is not None else 0.0,
        "min_score": round(min_score, 1) if min_score is not None else 0.0,
        "pass_rate": pass_rate,
        "subject_stats": subject_stats,
        "distribution": distribution,
    }
