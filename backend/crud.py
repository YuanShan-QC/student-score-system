"""
CRUD 操作 —— 14 个函数，按科目→学生→成绩分组

所有函数接收 db: Session 和 Pydantic Schema，返回 dict 或 ORM 对象。
异常（如 UNIQUE 冲突、FK 不存在）统一在路由层捕获处理。
"""
from sqlalchemy.orm import Session, joinedload
from models import Subject, Student, Score


# ================================================================
#  科目（4 个）
# ================================================================
def get_subjects(db: Session) -> list[Subject]:
    """获取全部科目"""
    return db.query(Subject).order_by(Subject.id).all()


def get_subject_by_code(db: Session, code: str) -> Subject | None:
    """按代码查科目（唯一性校验用）"""
    return db.query(Subject).filter(Subject.code == code).first()


def create_subject(db: Session, code: str, name: str) -> Subject:
    """新增科目"""
    sub = Subject(code=code, name=name)
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


def update_subject(db: Session, sub_id: int, **kwargs) -> Subject | None:
    """修改科目（kwargs 传入要改的字段）"""
    sub = db.query(Subject).get(sub_id)
    if not sub:
        return None
    for k, v in kwargs.items():
        if v is not None:
            setattr(sub, k, v)
    db.commit()
    db.refresh(sub)
    return sub


def delete_subject(db: Session, sub_id: int) -> bool:
    """删除科目"""
    sub = db.query(Subject).get(sub_id)
    if not sub:
        return False
    db.delete(sub)
    db.commit()
    return True


# ================================================================
#  学生（5 个）
# ================================================================
def get_students(
    db: Session,
    page: int = 1,
    page_size: int = 10,
    keyword: str | None = None,
) -> tuple[list[Student], int]:
    """
    分页查询学生，支持 keyword 模糊搜索（姓名或学号）。
    返回 (学生列表, 总条数)。
    """
    query = db.query(Student)
    if keyword:
        pattern = f"%{keyword}%"
        from sqlalchemy import or_
        query = query.filter(
            or_(
                Student.name.contains(keyword),
                Student.student_id.contains(keyword),
            )
        )
    total = query.count()
    students = query.order_by(Student.id)\
                    .offset((page - 1) * page_size)\
                    .limit(page_size)\
                    .all()
    return students, total


def get_student_by_id(db: Session, student_id: str) -> Student | None:
    """按学号查学生"""
    return db.query(Student).filter(Student.student_id == student_id).first()


def create_student(db: Session, student_id: str, name: str,
                   gender: str, age: int) -> Student | None:
    """新增学生（调用前应先检查学号是否重复）"""
    stu = Student(student_id=student_id, name=name, gender=gender, age=age)
    db.add(stu)
    db.commit()
    db.refresh(stu)
    return stu


def update_student(db: Session, student_id: str, **kwargs) -> Student | None:
    """按学号修改学生"""
    stu = db.query(Student).filter(Student.student_id == student_id).first()
    if not stu:
        return None
    for k, v in kwargs.items():
        if v is not None:
            setattr(stu, k, v)
    db.commit()
    db.refresh(stu)
    return stu


def delete_student(db: Session, student_id: str) -> bool:
    """按学号删除学生（级联删除成绩）"""
    stu = db.query(Student).filter(Student.student_id == student_id).first()
    if not stu:
        return False
    db.delete(stu)
    db.commit()
    return True


# ================================================================
#  成绩（5 个）
# ================================================================
def get_scores_by_student(db: Session, student_id: str) -> list[dict]:
    """
    按学号查该学生的全部成绩，带学生名和科目名。
    返回 dict 列表，key 与 ScoreDetail schema 对齐。
    """
    scores = (
        db.query(Score)
        .options(joinedload(Score.student), joinedload(Score.subject))
        .filter(Score.student_id == student_id)
        .order_by(Score.subject_id)
        .all()
    )
    return [
        {
            "id": sc.id,
            "student_id": sc.student_id,
            "subject_id": sc.subject_id,
            "score": sc.score,
            "created_at": sc.created_at,
            "student_name": sc.student.name if sc.student else "",
            "subject_name": sc.subject.name if sc.subject else "",
        }
        for sc in scores
    ]


def get_score_by_pk(db: Session, score_id: int) -> Score | None:
    """按主键查单条成绩"""
    return db.query(Score).get(score_id)


def create_score(
    db: Session, student_id: str, subject_id: int, score: float
) -> Score:
    """录入成绩（调用前应检查 UNIQUE 和 FK）"""
    sc = Score(student_id=student_id, subject_id=subject_id, score=score)
    db.add(sc)
    db.commit()
    db.refresh(sc)
    return sc


def update_score(db: Session, score_id: int, score: float) -> Score | None:
    """修改成绩分数"""
    sc = db.query(Score).get(score_id)
    if not sc:
        return None
    sc.score = score
    db.commit()
    db.refresh(sc)
    return sc


def delete_score(db: Session, score_id: int) -> bool:
    """删除成绩"""
    sc = db.query(Score).get(score_id)
    if not sc:
        return False
    db.delete(sc)
    db.commit()
    return True
