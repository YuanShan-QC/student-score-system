#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 adversarial 样本喂给真实安全层，导出判定结果（喂给 run_guard_eval.py）。

安全层是纯函数（backend/llm/security.py 只 import re），不碰数据库，
所以这个脚本不需要起服务、不需要 LLM、几百毫秒跑完。

用例格式：
  {"id":1,"category":"ddl","channel":"write","expect":"block","sql":"DROP TABLE students"}
  channel: read → validate_read_sql；write → validate_write_sql
  expect:  block 应拦截 / allow 应放行（放行样本用来量误拦率）
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.abspath(os.path.join(HERE, "..", "backend"))
sys.path.insert(0, BACKEND)

from llm.security import validate_read_sql, validate_write_sql   # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default=os.path.join(HERE, "guard_cases.jsonl"))
    ap.add_argument("--out", default=os.path.join(HERE, "guard_results.jsonl"))
    args = ap.parse_args()

    results = []
    with open(args.cases, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            c = json.loads(line)
            sql = c["sql"]
            if c.get("channel") == "read":
                ok, detail = validate_read_sql(sql, c.get("params"))
            else:
                ok, detail = validate_write_sql(sql)
            results.append({
                "id": c["id"],
                "decision": "allow" if ok else "block",
                "reason": detail if not ok else "通过",
            })

    with open(args.out, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    blocked = sum(1 for r in results if r["decision"] == "block")
    print(f"写入 {args.out}：{len(results)} 条，拦 {blocked} 条，放行 {len(results) - blocked} 条")


if __name__ == "__main__":
    main()
