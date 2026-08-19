"""
Pydantic 模型 —— 请求/响应 Schema（10 个模型）

命名规则：
  XxxCreate  : POST 请求体
  XxxUpdate  : PUT  请求体（全部 Optional）
  XxxResponse: GET  响应体（from_attributes=True，可直接从 ORM 对象转换）

注意：PaginatedResponse.items 必须明确标注 list[StudentResponse]，
      只写 list 会导致 Pydantic v2 无法序列化 ORM 实例 → 500 错误。
"""
from datetime import datetime
from pydantic import BaseModel, ConfigDict


# ================================================================
#  Subject（科目）
# ================================================================
class SubjectCreate(BaseModel):
    """新增科目"""
    code: str
    name: str


class SubjectUpdate(BaseModel):
    """修改科目（所有字段可选，只传要改的）"""
    code: str | None = None
    name: str | None = None


class SubjectResponse(BaseModel):
    """科目响应 —— 可直接 from_orm"""
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    name: str
    created_at: datetime | None = None


# ================================================================
#  Student（学生）
# ================================================================
class StudentCreate(BaseModel):
    """新增学生"""
    student_id: str  # 学号（必填，唯一）
    name: str
    gender: str
    age: int


class StudentUpdate(BaseModel):
    """修改学生（学号不可改，其余 Optional）"""
    name: str | None = None
    gender: str | None = None
    age: int | None = None


class StudentResponse(BaseModel):
    """学生响应"""
    model_config = ConfigDict(from_attributes=True)
    id: int
    student_id: str
    name: str
    gender: str
    age: int
    created_at: datetime | None = None


# ================================================================
#  Score（成绩）
# ================================================================
class ScoreCreate(BaseModel):
    """录入成绩"""
    student_id: str   # 学号
    subject_id: int   # 科目 ID
    score: float      # 分数


class ScoreUpdate(BaseModel):
    """修改成绩（只允许改分数）"""
    score: float


class ScoreResponse(BaseModel):
    """成绩响应"""
    model_config = ConfigDict(from_attributes=True)
    id: int
    student_id: str
    subject_id: int
    score: float
    created_at: datetime | None = None


class ScoreDetail(BaseModel):
    """
    成绩详情（带学生姓名和科目名，用于列表展示）
    字段来自 CRUD 层 JOIN 查询 → 手工构造 dict → **dict 传参，
    from_attributes 保留以便后续直接映射 Row 对象。
    """
    model_config = ConfigDict(from_attributes=True)
    id: int
    student_id: str
    subject_id: int
    score: float
    student_name: str = ""
    subject_name: str = ""
    created_at: datetime | None = None


# ================================================================
#  分页响应
# ================================================================
class PaginatedResponse(BaseModel):
    """
    分页响应 —— items 必须明确类型！
    只写 list 会丢失泛型信息，Pydantic v2 无法对 ORM 对象调用 model_validate。
    """
    total: int
    page: int
    page_size: int
    items: list[StudentResponse]
