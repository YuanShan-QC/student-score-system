"""
学生路由 —— /api/students（4 个 REST 接口）
支持分页 + 关键字搜索，学号唯一性校验
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from database import get_db
from schemas import StudentCreate, StudentUpdate, StudentResponse, PaginatedResponse
import crud

router = APIRouter(prefix="/api/students", tags=["学生管理"])


@router.get("", response_model=PaginatedResponse)
def list_students(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页条数"),
    keyword: str | None = Query(None, description="搜索关键词（姓名或学号）"),
    db: Session = Depends(get_db),
):
    """分页查询学生，支持 keyword 模糊搜索"""
    rows, total = crud.get_students(db, page, page_size, keyword)
    return PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[StudentResponse.model_validate(r) for r in rows],
    )


@router.post("", response_model=StudentResponse, status_code=201)
def create_student(data: StudentCreate, db: Session = Depends(get_db)):
    """新增学生（学号重复 → 409）"""
    existing = crud.get_student_by_id(db, data.student_id)
    if existing:
        raise HTTPException(409, f"学号 {data.student_id} 已存在")
    return crud.create_student(db, data.student_id, data.name, data.gender, data.age)


@router.put("/{student_id}", response_model=StudentResponse)
def update_student(student_id: str, data: StudentUpdate, db: Session = Depends(get_db)):
    """按学号修改学生信息"""
    stu = crud.update_student(db, student_id, **data.model_dump(exclude_unset=True))
    if not stu:
        raise HTTPException(404, "学生不存在")
    return stu


@router.delete("/{student_id}", status_code=204)
def delete_student(student_id: str, db: Session = Depends(get_db)):
    """按学号删除学生（级联删除成绩）"""
    ok = crud.delete_student(db, student_id)
    if not ok:
        raise HTTPException(404, "学生不存在")
