"""
成绩系统 API 接口契约测试（替代原来的脚本式 test_12api.py）。

和旧的 test_12api.py 的差别 —— 这几条正是面试会问的"测试怎么写才靠得住"：

| 旧脚本的问题 | 现在的做法 |
|---|---|
| 模块级 import 就构造 TestClient、直接跑断言 | 用 pytest 函数组织，夹具负责准备和清理 |
| 非幂等：第二次跑就崩（BIO 科目残留 → 409） | 每个用例用唯一编号，并在 finally 里清理自己造的数据 |
| 断言写错：造了 001 格式的学号，却去查 2024001 | 断言基于夹具真实造出来的数据 |
| 直接写开发库 | 用 DATABASE_URL 指向临时库，不污染演示数据 |
| 失败即中断（第一个错就看不到后面） | pytest 每个用例独立，一个失败不影响其他 |

跑法：pytest student-score-system -v
"""

import os
import sys
from pathlib import Path

# ============================================================================
# 【必须放在所有 import 之前】测试库环境准备
#
# 为什么写在模块顶部而不是 fixture 里：
#   database.py 在 **import 时**就 create_engine(...)，用当时读到的环境变量。
#   如果等 fixture 才设置，那么只要有任何代码在收集阶段先 import 了 database
#   （实测确实会发生），engine 就已经指向默认库了。
#   模块顶部是唯一能保证"先于一切"的位置。
#
# 为什么不用 tempfile 建临时目录（踩过的坑）：
#   SQLAlchemy 打不开系统 Temp 下的 sqlite 文件（报 unable to open database file），
#   而同一个目录用 sqlite3 直接写是可以的 —— 受限环境对 Temp 有额外限制。
#   所以测试库固定放在仓库根目录的 .pytest_db/（已在 .gitignore 里），能稳定工作。
#
# 为什么路径必须 as_posix()：
#   Windows 路径的反斜杠拼进 "sqlite:///" 会让 SQLAlchemy 解析 URL 失败。
# ============================================================================
_REPO_ROOT = Path(__file__).resolve().parents[2]
_TEST_DB_DIR = _REPO_ROOT / ".pytest_db"
_TEST_DB_DIR.mkdir(parents=True, exist_ok=True)
_TEST_DB_FILE = _TEST_DB_DIR / "score_api_test.db"
if _TEST_DB_FILE.exists():          # 每次运行都从干净库开始，保证可重复
    _TEST_DB_FILE.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_FILE.as_posix()}"
os.environ.setdefault("DEEPSEEK_API_KEY", "test-key-not-used")

import pytest  # noqa: E402


@pytest.fixture(scope="module")
def client():
    """
    启动测试用的 API client（指向模块顶部准备好的测试库）。

    注意：**不能用 `import main`**。
    两个项目各有一个 main.py，而两个 backend 都在 sys.path 上，谁被导入取决于
    路径顺序 —— 实测会命中 tarkov-helper 的 main.py，表现是 GET / 返回一段
    塔科夫前端的 HTML。所以这里按文件路径精确加载。
    """
    backend_dir = Path(__file__).resolve().parents[1] / "backend"
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))

    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "score_system_main", backend_dir / "main.py"
    )
    main = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(main)  # 这里会建表 + 灌种子数据到测试库

    from fastapi.testclient import TestClient

    with TestClient(main.app) as c:
        yield c


class TestSubjects:
    def test_列表返回种子科目(self, client):
        r = client.get("/api/subjects")
        assert r.status_code == 200
        names = {s["name"] for s in r.json()}
        assert {"语文", "数学", "英语"} <= names

    def test_增删改查完整闭环(self, client):
        created_id = None
        try:
            r = client.post("/api/subjects", json={"code": "TST1", "name": "测试科目"})
            assert r.status_code == 201, r.text
            body = r.json()
            created_id = body["id"]
            assert body["code"] == "TST1"

            r = client.put(f"/api/subjects/{created_id}", json={"name": "改过的名字"})
            assert r.status_code == 200
            assert r.json()["name"] == "改过的名字"
        finally:
            if created_id:
                assert client.delete(f"/api/subjects/{created_id}").status_code == 204

    def test_重复_code_返回_409(self, client):
        created_id = None
        try:
            r = client.post("/api/subjects", json={"code": "TST2", "name": "A"})
            created_id = r.json()["id"]
            r2 = client.post("/api/subjects", json={"code": "TST2", "name": "B"})
            assert r2.status_code == 409
        finally:
            if created_id:
                client.delete(f"/api/subjects/{created_id}")


class TestStudents:
    def test_分页查询返回总数字段(self, client):
        r = client.get("/api/students", params={"page": 1, "page_size": 20})
        assert r.status_code == 200
        body = r.json()
        assert body["total"] >= 5        # 种子数据 5 个学生
        assert body["page"] == 1
        assert len(body["items"]) >= 5

    def test_新增重复学号返回_409(self, client):
        created = []
        try:
            payload = {"student_id": "T9001", "name": "测试甲", "gender": "男", "age": 20}
            r = client.post("/api/students", json=payload)
            assert r.status_code == 201, r.text
            created.append(payload["student_id"])

            r2 = client.post("/api/students", json={**payload, "name": "重复"})
            assert r2.status_code == 409
        finally:
            for sid in created:
                client.delete(f"/api/students/{sid}")

    def test_删除学生会级联清掉其成绩(self, client):
        """级联删除是数据完整性的关键行为，必须测"""
        sid = "T9002"
        try:
            r = client.post("/api/students", json={
                "student_id": sid, "name": "测试乙", "gender": "女", "age": 19})
            assert r.status_code == 201, r.text

            subs = client.get("/api/subjects").json()
            r = client.post("/api/scores", json={
                "student_id": sid, "subject_id": subs[0]["id"], "score": 88})
            assert r.status_code == 201, r.text

            assert client.delete(f"/api/students/{sid}").status_code == 204
            assert len(client.get(f"/api/scores?student_id={sid}").json()) == 0
            sid = None
        finally:
            if sid:
                client.delete(f"/api/students/{sid}")


class TestScores:
    def test_同一学生同一科目不能重复录入(self, client):
        sid = "T9003"
        subject_id = None
        try:
            client.post("/api/students", json={
                "student_id": sid, "name": "测试丙", "gender": "男", "age": 21})
            subs = client.get("/api/subjects").json()
            subject_id = subs[-1]["id"]

            r = client.post("/api/scores", json={
                "student_id": sid, "subject_id": subject_id, "score": 99})
            assert r.status_code == 201, r.text

            r2 = client.post("/api/scores", json={
                "student_id": sid, "subject_id": subject_id, "score": 80})
            assert r2.status_code == 409      # UNIQUE(student_id, subject_id)
        finally:
            for sc in client.get(f"/api/scores?student_id={sid}").json():
                client.delete(f"/api/scores/{sc['id']}")
            client.delete(f"/api/students/{sid}")

    def test_更新分数(self, client):
        sid = "T9004"
        try:
            client.post("/api/students", json={
                "student_id": sid, "name": "测试丁", "gender": "女", "age": 20})
            subs = client.get("/api/subjects").json()
            r = client.post("/api/scores", json={
                "student_id": sid, "subject_id": subs[0]["id"], "score": 60})
            score_id = r.json()["id"]

            r = client.put(f"/api/scores/{score_id}", json={"score": 86})
            assert r.status_code == 200
            assert r.json()["score"] == 86
        finally:
            for sc in client.get(f"/api/scores?student_id={sid}").json():
                client.delete(f"/api/scores/{sc['id']}")
            client.delete(f"/api/students/{sid}")


class TestStats:
    def test_统计接口可用(self, client):
        r = client.get("/api/stats")
        assert r.status_code == 200
        body = r.json()
        assert body["student_count"] >= 5      # 种子数据 5 个学生
        assert body["subject_count"] >= 5
        assert "pass_rate" in body
        assert len(body["subject_stats"]) >= 5


class TestHealth:
    def test_健康检查(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert r.json()["message"] == "API running"
