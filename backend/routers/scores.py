"""
成绩路由 —— /api/scores（4 个 REST + 2 个 Excel 接口）

异常分类：
  UNIQUE 约束冲突（学生+科目重复） → 409
  外键不存在（学生或科目不存在）    → 404
"""
import sqlite3
from io import BytesIO
from urllib.parse import quote
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
from database import get_db
from schemas import ScoreCreate, ScoreUpdate, ScoreResponse, ScoreDetail
from models import Score
import crud

router = APIRouter(prefix="/api/scores", tags=["成绩管理"])


@router.get("", response_model=list[ScoreDetail])
def list_scores(
    student_id: str = Query(..., description="学号（必填）"),
    db: Session = Depends(get_db),
):
    """按学号查该学生的全部成绩（含科目名和分数）"""
    rows = crud.get_scores_by_student(db, student_id)
    return [ScoreDetail(**r) for r in rows]


@router.post("", response_model=ScoreResponse, status_code=201)
def create_score(data: ScoreCreate, db: Session = Depends(get_db)):
    """
    录入成绩。

    异常：
      UNIQUE 冲突（该生该科已有成绩） → 409
      FK 不存在（学生或科目不存在）    → 404
    """
    try:
        return crud.create_score(db, data.student_id, data.subject_id, data.score)
    except Exception as e:
        db.rollback()
        # SQLite IntegrityError 的错误信息示例：
        #   UNIQUE constraint failed: scores.student_id, scores.subject_id
        #   FOREIGN KEY constraint failed
        raw = str(e)
        if "UNIQUE" in raw:
            raise HTTPException(
                409, f"学生 {data.student_id} 的该科目已有成绩"
            )
        if "FOREIGN KEY" in raw:
            raise HTTPException(
                404, f"学生 {data.student_id} 或科目 {data.subject_id} 不存在"
            )
        raise HTTPException(500, f"未知错误: {raw}")


@router.put("/{score_id}", response_model=ScoreResponse)
def update_score(score_id: int, data: ScoreUpdate, db: Session = Depends(get_db)):
    """修改成绩分数"""
    sc = crud.update_score(db, score_id, data.score)
    if not sc:
        raise HTTPException(404, "成绩记录不存在")
    return sc


@router.delete("/{score_id}", status_code=204)
def delete_score(score_id: int, db: Session = Depends(get_db)):
    """删除成绩"""
    ok = crud.delete_score(db, score_id)
    if not ok:
        raise HTTPException(404, "成绩记录不存在")


# ================================================================
#  Excel 导出 / 导入
# ================================================================

# --- 公共样式 ---
HEADER_FILL = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)
THIN_BORDER = Border(
    left=Side(style="thin"), right=Side(style="thin"),
    top=Side(style="thin"), bottom=Side(style="thin"),
)
CENTER = Alignment(horizontal="center", vertical="center")


@router.get("/export")
def export_scores(
    mode: str = Query("template", description="template=模板（成绩列为空）/ full=导出已有数据"),
    db: Session = Depends(get_db),
):
    """
    Excel 导出。

    mode=template：学号+姓名有值，成绩列全空（发给学生填写）
    mode=full：    已有成绩回填到对应科目列

    中文文件名使用 filename*=UTF-8'' + URL 编码，
    只用 filename= 会导致 latin-1 编码崩溃。
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "成绩表"

    # --- 取科目和学生 ---
    subjects = crud.get_subjects(db)
    students, _ = crud.get_students(db, page=1, page_size=1000)

    # --- 表头行（学号 / 姓名 / 科目1 / 科目2 ...）---
    headers = ["学号", "姓名"] + [s.name for s in subjects]
    for col_idx, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=h)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.border = THIN_BORDER
        cell.alignment = CENTER

    # --- 数据行 ---
    for row_idx, student in enumerate(students, 2):
        ws.cell(row=row_idx, column=1, value=student.student_id).border = THIN_BORDER
        ws.cell(row=row_idx, column=2, value=student.name).border = THIN_BORDER
        ws.cell(row=row_idx, column=1).alignment = CENTER
        ws.cell(row=row_idx, column=2).alignment = CENTER

        if mode == "full":
            # 已有成绩回填
            score_list = crud.get_scores_by_student(db, student.student_id)
            score_map = {s["subject_name"]: s["score"] for s in score_list}
            for col_idx, sub in enumerate(subjects, 3):
                val = score_map.get(sub.name, "")
                cell = ws.cell(row=row_idx, column=col_idx, value=val)
                cell.border = THIN_BORDER
                cell.alignment = CENTER
        else:
            # 模板模式：成绩列留空
            for col_idx in range(3, len(subjects) + 3):
                cell = ws.cell(row=row_idx, column=col_idx)
                cell.border = THIN_BORDER
                cell.alignment = CENTER

    # --- 冻结首行 + 自适应列宽 ---
    ws.freeze_panes = "A2"
    col_widths = {"A": 14, "B": 10}  # 学号列、姓名列固定宽度
    for col_idx, sub in enumerate(subjects, 3):
        letter = chr(64 + col_idx) if col_idx <= 26 else "A" + chr(64 + col_idx - 26)
        col_widths[letter] = max(len(sub.name) * 2 + 2, 10)
    for letter, width in col_widths.items():
        ws.column_dimensions[letter].width = width

    # --- 输出为 BytesIO 流 ---
    output = BytesIO()
    wb.save(output)
    output.seek(0)

    filename = "成绩模板.xlsx" if mode == "template" else "成绩数据.xlsx"
    encoded_filename = quote(filename)

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
        },
    )


@router.post("/import")
async def import_scores(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Excel 导入成绩。

    流程：
      1) 读取上传的 .xlsx
      2) 解析表头（第 3 列起为科目名），验证科目存在
      3) 第一遍预校验（不写库）：学号是否存在、成绩是否为数字、0-100
      4) 全通过后用事务批量 upsert（存在更新、不存在插入）
      5) 有错则返回 {total, success_count: 0, errors:[...]}
    """
    # --- 读取文件 ---
    contents = await file.read()
    wb = load_workbook(BytesIO(contents))
    ws = wb.active

    # --- 解析表头 ---
    header_row = [cell.value for cell in ws[1]]
    if not header_row or len(header_row) < 3:
        raise HTTPException(400, "表头至少需要 3 列：学号、姓名、科目…")

    subjects = crud.get_subjects(db)
    subject_name_to_id = {s.name: s.id for s in subjects}

    # 第 3 列起映射为科目
    subject_columns = []
    for col_idx, h in enumerate(header_row[2:], 3):
        if h not in subject_name_to_id:
            raise HTTPException(400, f"科目「{h}」在系统中不存在，请先创建该科目")
        subject_columns.append((col_idx, subject_name_to_id[h]))

    # --- 第一遍：预校验 ---
    errors = []
    valid_rows = []
    raw_count = 0

    for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), 2):
        if not row or not row[0]:
            continue  # 跳过空行
        raw_count += 1

        student_id = str(row[0]).strip()

        # 学号存在性
        student = crud.get_student_by_id(db, student_id)
        if not student:
            errors.append(f"第{row_idx}行: 学号「{student_id}」不存在")
            continue

        row_scores = []
        row_has_error = False
        for col_idx, sub_id in subject_columns:
            val = row[col_idx - 1]  # row 是 0-indexed
            if val is None or str(val).strip() == "":
                continue

            try:
                score_val = float(val)
                if score_val < 0 or score_val > 100:
                    errors.append(f"第{row_idx}行 第{col_idx}列: 成绩 {score_val} 不在 0~100 范围")
                    row_has_error = True
                else:
                    row_scores.append((student_id, sub_id, score_val))
            except (ValueError, TypeError):
                errors.append(f"第{row_idx}行 第{col_idx}列: 「{val}」不是有效数字")
                row_has_error = True

        if not row_has_error and row_scores:
            valid_rows.append(row_scores)

    # 有错返回
    if errors:
        return {"total": raw_count, "success_count": 0, "errors": errors}

    # --- 第二遍：事务批量写入（upsert）---
    imported = 0
    try:
        for row_scores in valid_rows:
            for sid, sub_id, score_val in row_scores:
                existing = (
                    db.query(Score)
                    .filter(Score.student_id == sid, Score.subject_id == sub_id)
                    .first()
                )
                if existing:
                    existing.score = score_val
                else:
                    db.add(Score(student_id=sid, subject_id=sub_id, score=score_val))
                imported += 1
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"导入写入失败: {str(e)}")

    return {"total": imported, "success_count": imported, "errors": []}
