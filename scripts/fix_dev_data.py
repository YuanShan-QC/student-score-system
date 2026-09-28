# -*- coding: utf-8 -*-
"""
修复开发库中的测试残留数据。

背景（真实发生过）：
    backend/test_12api.py 是脚本式测试，**直接写开发库、且不幂等**。
    它跑崩的那次留下了这些脏数据：
      · 多出一个科目：code=BIO / name=Biology 之外的残留（种子数据只有 6 科）
      · 学生 005(钱七) 被 DELETE —— 因为脚本会删掉自己造的学生，
        但崩溃后没走完清理流程
    这让"演示数据"和 init_data.py 宣称的"5 学生 6 科目 25 条成绩"对不上，
    面试时如果打开页面看到数据缺失，会被追问。

本脚本做的事：把开发库恢复成 init_data.py 定义的状态（不删表、不动其他数据）。

用法：
    student-score-system\\backend\\.venv\\Scripts\\python.exe student-score-system\\scripts\\fix_dev_data.py

安全设计：
    · 先打印将要做的每件事，再执行
    · 学生/科目只补不删（多出来的科目只报告，不自动删）
    · 成绩会删除"不在种子集合内"的残留行 —— 因为旧脚本的
      `PUT /api/scores/1 {"score":86}` 这类调用会把种子数据**改掉**，
      留着就是数据损坏（实测把 001/MATH 从 55 改成了 95）
    · 用 --dry-run 可以只看不改
"""
import sqlite3
import sys
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / "data" / "scores.db"

# ===== init_data.py 定义的"应有状态" =====
SUBJECTS = [
    ("CHN", "语文"), ("MATH", "数学"), ("ENG", "英语"),
    ("PHY", "物理"), ("CHEM", "化学"), ("BIO", "生物"),
]
STUDENTS = [
    ("001", "张三", "男", 18), ("002", "李四", "女", 19), ("003", "王五", "男", 18),
    ("004", "赵六", "女", 20), ("005", "钱七", "男", 19),
]
SCORES = [
    ("001", "CHN", 85), ("001", "MATH", 55), ("001", "ENG", 78), ("001", "PHY", 92), ("001", "CHEM", 67),
    ("002", "CHN", 72), ("002", "MATH", 88), ("002", "ENG", 45), ("002", "PHY", 76), ("002", "CHEM", 90),
    ("003", "CHN", 95), ("003", "MATH", 62), ("003", "ENG", 81), ("003", "PHY", 58), ("003", "CHEM", 73),
    ("004", "CHN", 68), ("004", "MATH", 91), ("004", "ENG", 74), ("004", "PHY", 85), ("004", "CHEM", 53),
    ("005", "CHN", 77), ("005", "MATH", 49), ("005", "ENG", 88), ("005", "PHY", 69), ("005", "CHEM", 94),
]


def main():
    dry_run = "--dry-run" in sys.argv
    if not DB.exists():
        print(f"[跳过] 数据库不存在：{DB}")
        return 1

    con = sqlite3.connect(DB)
    con.execute("PRAGMA foreign_keys=ON")
    cur = con.cursor()
    changed = 0

    print(f"数据库：{DB}")
    print(f"模式：{'只看不改（--dry-run）' if dry_run else '实际修改'}\n")

    # ---------- 1. 科目 ----------
    print("=== 科目 ===")
    for code, name in SUBJECTS:
        row = cur.execute("SELECT id, name FROM subjects WHERE code = ?", (code,)).fetchone()
        if row is None:
            cur.execute("INSERT INTO subjects (code, name) VALUES (?, ?)", (code, name))
            print(f"  [补] 缺科目 {code}/{name}")
            changed += 1
        elif row[1] != name:
            print(f"  [!] 科目 {code} 名称不同：库里是 {row[1]!r}，种子是 {name!r}（不覆盖，请人工确认）")

    # 列出多出来的科目（不在种子里的）
    seed_codes = {c for c, _ in SUBJECTS}
    for sid, code, name in cur.execute("SELECT id, code, name FROM subjects").fetchall():
        if code not in seed_codes:
            print(f"  [!] 多出科目 id={sid} {code}/{name}（测试残留？确认后手工删除）")

    # ---------- 2. 学生 ----------
    print("\n=== 学生 ===")
    for student_id, name, gender, age in STUDENTS:
        row = cur.execute("SELECT name FROM students WHERE student_id = ?", (student_id,)).fetchone()
        if row is None:
            cur.execute(
                "INSERT INTO students (student_id, name, gender, age) VALUES (?, ?, ?, ?)",
                (student_id, name, gender, age),
            )
            print(f"  [补] 缺学生 {student_id}/{name}")
            changed += 1

    # ---------- 3. 成绩 ----------
    print("\n=== 成绩 ===")
    sub_map = {code: sid for sid, code in cur.execute("SELECT id, code FROM subjects").fetchall()}
    code_by_id = {sid: code for code, sid in sub_map.items()}
    seed_set = {(sid, sub_map[code], score) for sid, code, score in SCORES if code in sub_map}

    # 3a. 先删掉"不在种子集合里"的残留行（旧脚本改过或加过的）
    extras = []
    for row_id, sid, subj, score in cur.execute(
        "SELECT id, student_id, subject_id, score FROM scores ORDER BY student_id, subject_id"
    ).fetchall():
        if (sid, subj, float(score)) not in {(a, b, float(c)) for a, b, c in seed_set}:
            extras.append((row_id, sid, code_by_id.get(subj, subj), score))
    if extras:
        for row_id, sid, code, score in extras:
            print(f"  [删] 残留成绩 id={row_id} 学生{sid} 科目{code} 分数{score}")
            if not dry_run:
                cur.execute("DELETE FROM scores WHERE id = ?", (row_id,))
            changed += 1
    else:
        print("  [OK] 没有残留成绩")

    # 3b. 再补齐缺失的种子成绩
    missing = []
    for student_id, code, score in SCORES:
        subject_id = sub_map.get(code)
        if subject_id is None:
            print(f"  [!] 找不到科目 {code}，跳过 {student_id} 的成绩")
            continue
        row = cur.execute(
            "SELECT id FROM scores WHERE student_id = ? AND subject_id = ?",
            (student_id, subject_id),
        ).fetchone()
        if row is None:
            if not dry_run:
                cur.execute(
                    "INSERT INTO scores (student_id, subject_id, score) VALUES (?, ?, ?)",
                    (student_id, subject_id, score),
                )
            missing.append(f"{student_id}/{code}={score}")
            changed += 1
    if missing:
        print("  [补] " + "、".join(missing))
    else:
        print("  [OK] 种子成绩无缺失")

    if not dry_run:
        con.commit()

    # ---------- 4. 结果 ----------
    print("\n=== 修复后 ===")
    print("  学生:", cur.execute("SELECT COUNT(*) FROM students").fetchone()[0],
          "| 科目:", cur.execute("SELECT COUNT(*) FROM subjects").fetchone()[0],
          "| 成绩:", cur.execute("SELECT COUNT(*) FROM scores").fetchone()[0])
    con.close()

    print(f"\n共修改 {changed} 处。" if changed else "\n无需修改。")
    print("期望状态：5 学生 / 6 科目 / 25 条成绩")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
