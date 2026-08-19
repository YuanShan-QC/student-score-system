"""
科目路由 —— /api/subjects（4 个 REST 接口）
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from schemas import SubjectCreate, SubjectUpdate, SubjectResponse
import crud

router = APIRouter(prefix="/api/subjects", tags=["科目管理"])


@router.get("", response_model=list[SubjectResponse])
def list_subjects(db: Session = Depends(get_db)):
    """获取全部科目"""
    return crud.get_subjects(db)


@router.post("", response_model=SubjectResponse, status_code=201)
def create_subject(data: SubjectCreate, db: Session = Depends(get_db)):
    """新增科目"""
    # 科目代码唯一性校验
    existing = crud.get_subject_by_code(db, data.code)
    if existing:
        raise HTTPException(409, f"科目代码 {data.code} 已存在")
    return crud.create_subject(db, data.code, data.name)


@router.put("/{sub_id}", response_model=SubjectResponse)
def update_subject(sub_id: int, data: SubjectUpdate, db: Session = Depends(get_db)):
    """修改科目（只传要改的字段）"""
    sub = crud.update_subject(db, sub_id, **data.model_dump(exclude_unset=True))
    if not sub:
        raise HTTPException(404, "科目不存在")
    return sub


@router.delete("/{sub_id}", status_code=204)
def delete_subject(sub_id: int, db: Session = Depends(get_db)):
    """删除科目"""
    ok = crud.delete_subject(db, sub_id)
    if not ok:
        raise HTTPException(404, "科目不存在")
