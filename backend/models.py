"""
ORM 模型 —— Student（学生）、Subject（科目）、Score（成绩）三表

关系：Student 1↔N Score N↔1 Subject
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime,
    ForeignKey, CheckConstraint, UniqueConstraint, func
)
from sqlalchemy.orm import relationship
from database import Base


class Student(Base):
    """学生表"""
    __tablename__ = "students"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(String(20), unique=True, nullable=False, comment="学号")
    name       = Column(String(50), nullable=False, comment="姓名")
    gender     = Column(String(2), nullable=False, comment="性别")
    age        = Column(Integer, nullable=False, comment="年龄")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")

    # 表级约束
    __table_args__ = (
        CheckConstraint("gender IN ('男','女')", name="ck_student_gender"),
        CheckConstraint("age BETWEEN 1 AND 150", name="ck_student_age"),
    )

    # 一对多：一个学生有多条成绩
    scores = relationship("Score", cascade="all, delete-orphan", back_populates="student")


class Subject(Base):
    """科目表"""
    __tablename__ = "subjects"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    code       = Column(String(20), unique=True, nullable=False, comment="科目代码")
    name       = Column(String(50), nullable=False, comment="科目名称")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")

    # 一对多：一个科目有多条成绩
    scores = relationship("Score", cascade="all, delete-orphan", back_populates="subject")


class Score(Base):
    """成绩表 —— 学生与科目的多对多中间表（带分数属性）"""
    __tablename__ = "scores"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(
        String(20),
        ForeignKey("students.student_id", ondelete="CASCADE"),  # 关联学号（注意：不是 students.id），级联删除
        nullable=False,
        comment="学号"
    )
    subject_id = Column(
        Integer,
        ForeignKey("subjects.id", ondelete="CASCADE"),  # 级联删除
        nullable=False,
        comment="科目ID"
    )
    score      = Column(Float, nullable=False, comment="分数")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")

    # 表级约束
    __table_args__ = (
        UniqueConstraint("student_id", "subject_id", name="uq_student_subject"),
        CheckConstraint("score BETWEEN 0 AND 100", name="ck_score_range"),
    )

    # 多对一：每条成绩属于一个学生
    student = relationship("Student", back_populates="scores")
    # 多对一：每条成绩属于一个科目
    subject = relationship("Subject", back_populates="scores")
