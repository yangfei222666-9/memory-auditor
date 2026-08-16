#!/usr/bin/env python3
# memory-auditor v0.1 —— AI agent 记忆审计器(2026-08-16 夜班)
# 双层:①静态规则层(零成本秒出)②--deep 四视角评审层(复用 multi_model_review.py)
# 设计铁律:报告是"候选",不是判决;每条发现带行号与原文,人工复核后才算数。
# 用法:python3 memory_auditor.py 文件1 [文件2 ...] [--kind md|jsonl|auto] [--deep] [--env <env文件>]
import argparse, json, os, re, subprocess, sys

OVERCLAIM_PATTERNS = [
    r"已达\s*AGI", r"接近\s*AGI", r"实现(了)?\s*AGI", r"通用人工智能水平", r"AGI[-\s]?(级别|级|水平)?的?自主",
    r"最强(的)?(模型|系统|方案)?", r"碾压(所有|同行)?", r"100%\s*成功", r"永不失败", r"从不出错",
    r"完全自动化(无需|零)人工", r"绝无(意外|风险|失败)", r"史无前例", r"遥遥领先",
]
EVIDENCE_HINTS = ["证据", "receipt", "evidence", "回执", "哈希", "sha", "命令输出", "报错原文", "复现"]
DONE_WITHOUT_EVIDENCE = re.compile(r"(已解决|已修复|已完成|搞定|闭环|全清|全部完成|全线通过)")

def read_lines(path):
    try:
        return open(path, encoding="utf-8").read().splitlines()
    except Exception as e:
        print(f"⚠️ 无法读取 {path}: {e}", file=sys.stderr)
        return None

def audit_markdown(path):
    """逐行静态审计:overclaim + 无证据完成声明 + 重复条款"""
    lines = read_lines(path)
    if lines is None: return []
    out = []
    seen = {}
    for i, line in enumerate(lines, 1):
        s = line.strip()
        if len(s) < 12: continue
        # 1) overclaim
        for p in OVERCLAIM_PATTERNS:
            m = re.search(p, s, re.I)
            if m and not re.search(r"(禁|不|勿|拒绝|永不|避免|不得|防)", s[max(0,m.start()-30):m.start()]) and not re.search(r"(禁|不|勿|拒绝|永不|避免|不得|防)", s[m.end():m.end()+30]):
                out.append({"file": path, "line": i, "issue": "overclaim",
                            "excerpt": s[:100], "hint": f"命中表述:{p[:24]}…请核对是否可辩护,或改为分级表述"})
                break
        # 2) 完成声明但无证据词
        if DONE_WITHOUT_EVIDENCE.search(s) and not any(h in s for h in EVIDENCE_HINTS):
            if re.match(r"^\s*[-*]|\d+\.", s):  # 列表条目才算,正文叙述放过
                out.append({"file": path, "line": i, "issue": "done_without_evidence",
                            "excerpt": s[:100], "hint": "完成类声明未附证据词(证据/receipt/哈希…);若为规则文本可忽略"})
        # 3) 重复条款(规范化后全库比对;表格行豁免)
        if s.startswith("|"): continue
        norm = re.sub(r"\s+", "", s)[:60]
        if norm in seen:
            out.append({"file": path, "line": i, "issue": "duplicate",
                        "excerpt": s[:100], "hint": f"与第 {seen[norm]} 行近似重复"})
        else:
            seen[norm] = i
    return out

def audit_jsonl(path):
    """对 LESSONS.jsonl 类:检查每条的 evidence 字段"""
    lines = read_lines(path)
    if lines is None: return []
    out = []
    for i, line in enumerate(lines, 1):
        if not line.strip(): continue
        try:
            d = json.loads(line)
        except Exception:
            out.append({"file": path, "line": i, "issue": "bad_json",
                        "excerpt": line[:80], "hint": "非 JSON 行"})
            continue
        ev = d.get("evidence") or d.get("证据")
        if not ev or len(str(ev).strip()) < 20:
            out.append({"file": path, "line": i, "issue": "no_evidence",
                        "excerpt": str(d.get("claim") or d.get("id") or "")[:80],
                        "hint": "教训缺 evidence 或证据 <20 字符(无证据不写教训)"})
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--kind", choices=["md", "jsonl", "auto"], default="auto")
    ap.add_argument("--json-out", default=None, help="结果写 JSON 文件")
    args = ap.parse_args()
    findings = []
    for f in args.files:
        kind = args.kind
        if kind == "auto":
            kind = "jsonl" if f.endswith((".jsonl", ".json")) else "md"
        if kind == "jsonl":
            findings += audit_jsonl(f)
        else:
            findings += audit_markdown(f)
    print(f"# 记忆审计报告 v0.1:共 {len(findings)} 条候选发现(候选≠判决,逐条复核)")
    from collections import Counter
    c = Counter(x["issue"] for x in findings)
    print("按类型:", dict(c))
    for x in findings:
        print(f"\n[{x['issue']}] {os.path.basename(x['file'])}:{x['line']}")
        print(f"  原文: {x['excerpt']}")
        print(f"  提示: {x['hint']}")
    if args.json_out:
        json.dump(findings, open(args.json_out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"\nJSON 报告: {args.json_out}")

if __name__ == "__main__":
    main()
