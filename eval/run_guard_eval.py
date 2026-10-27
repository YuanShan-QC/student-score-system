#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SQL 安全护栏评测：拦截率 / 误拦率 / 分类别表现。

输入：
  --cases   eval/guard_cases.jsonl
            {"id":1,"category":"ddl","expect":"block","input":"DROP TABLE 学生"}
  --result  eval/guard_results.jsonl  你的护栏实际判定
            {"id":1,"decision":"block","reason":"命中 DDL 黑名单"}

用法：
  python run_guard_eval.py --cases guard_cases.example.jsonl --result mock
  python run_guard_eval.py --cases eval/guard_cases.jsonl \
        --result eval/guard_results.jsonl --out eval/guard_report.md
"""
import argparse
import json
import random
import sys
from collections import defaultdict


def load_jsonl(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for ln, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                sys.exit(f"{path}:{ln} JSON 解析失败：{e}")
    return rows


def synth(cases):
    random.seed(7)
    out = []
    for c in cases:
        exp = c["expect"]
        # 拦截率高、误拦低——模拟一个已经不错的护栏
        correct = random.random() < (0.92 if exp == "block" else 0.90)
        decision = exp if correct else ("allow" if exp == "block" else "block")
        out.append({"id": c["id"], "decision": decision, "reason": "mock"})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", required=True)
    ap.add_argument("--result", required=True, help="判定结果文件，或写 mock")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    cases = load_jsonl(args.cases)
    if args.result.strip().lower() == "mock":
        results = synth(cases)
        print("[提示] 当前是 mock 数据，只用于检查报表格式。\n")
    else:
        results = load_jsonl(args.result)
    res_map = {r["id"]: r for r in results}

    tp = fn = fp = tn = 0
    per_cat = defaultdict(lambda: {"n": 0, "caught": 0, "expect_block": 0})
    misses, false_pos = [], []

    for c in cases:
        if c["id"] not in res_map:
            continue
        dec = res_map[c["id"]].get("decision")
        exp = c["expect"]
        cat = c.get("category", "other")
        per_cat[cat]["n"] += 1
        if exp == "block":
            per_cat[cat]["expect_block"] += 1
            if dec == "block":
                tp += 1
                per_cat[cat]["caught"] += 1
            else:
                fn += 1
                misses.append((c, dec))
        else:
            if dec == "block":
                fp += 1
                false_pos.append((c, dec))
            else:
                tn += 1

    block_total = tp + fn
    allow_total = fp + tn
    if block_total == 0 and allow_total == 0:
        sys.exit("没有可评测的样本")

    L = []
    L.append("# 护栏评测报告\n")
    L.append(f"- 样本：应拦截 {block_total} 条，应放行 {allow_total} 条，共 {tp+fn+fp+tn} 条")
    L.append("- 口径：拦截率 = 拦对/应拦；**误拦率 = 误拦/应放行**（只报拦截率不算评测）\n")
    if block_total:
        L.append(f"**拦截率 = {tp/block_total:.1%}（{tp}/{block_total}）**")
    if allow_total:
        L.append(f"**误拦率 = {fp/allow_total:.1%}（{fp}/{allow_total}）**")
    L.append("")
    L.append("| 类别 | 样本 | 应拦 | 拦对 | 该类拦截率 |")
    L.append("|---|---|---|---|---|")
    for cat in sorted(per_cat):
        s = per_cat[cat]
        if s["expect_block"] == 0:
            L.append(f"| {cat}（应放行） | {s['n']} | 0 | - | - |")
        else:
            L.append(f"| {cat} | {s['n']} | {s['expect_block']} | {s['caught']} | "
                     f"{s['caught']/s['expect_block']:.0%} |")
    L.append("")
    if misses:
        L.append(f"## 漏拦（{len(misses)} 条，直接暴露护栏缺口）\n")
        L.append("| id | 类别 | 输入 |")
        L.append("|---|---|---|")
        for c, _ in misses:
            L.append(f"| {c['id']} | {c.get('category','')} | `{c.get('input') or c.get('sql','')}` |")
        L.append("")
    if false_pos:
        L.append(f"## 误拦（{len(false_pos)} 条，说明护栏太粗）\n")
        L.append("| id | 类别 | 输入 |")
        L.append("|---|---|---|")
        for c, _ in false_pos:
            L.append(f"| {c['id']} | {c.get('category','')} | `{c.get('input') or c.get('sql','')}` |")
        L.append("")
    report = "\n".join(L)
    print(report)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\n报表已写入 {args.out}")


if __name__ == "__main__":
    main()
