#!/usr/bin/env python3
# memory-auditor v0.1 —— AI agent 记忆审计器(2026-08-16 夜班)
# 静态规则层：Markdown 声明检查与 JSONL 证据字段检查。
# 设计铁律:报告是"候选",不是判决;每条发现带行号与原文,人工复核后才算数。
# 用法:python3 memory_auditor.py 文件1 [文件2 ...] [--kind md|jsonl|auto] [--json-out report.json]
import argparse, json, os, re, sys, tempfile

OVERCLAIM_PATTERNS = [
    r"已达[ \t]*AGI", r"接近[ \t]*AGI", r"实现(了)?[ \t]*AGI", r"通用人工智能水平", r"AGI[- \t]?(级别|级|水平)?的?自主",
    r"最强(的)?(模型|系统|方案)?", r"碾压(所有|同行)?", r"100%[ \t]*成功", r"永不失败", r"从不出错",
    r"完全自动化(无需|零)人工", r"绝无(意外|风险|失败)", r"史无前例", r"遥遥领先",
]
EVIDENCE_HINTS = ["证据", "receipt", "evidence", "回执", "哈希", "sha", "命令输出", "报错原文", "复现"]
DONE_WITHOUT_EVIDENCE = re.compile(r"(已解决|已修复|已完成|搞定|闭环|全清|全部完成|全线通过)")
CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def escape_terminal(value):
    """Render untrusted text without allowing terminal control sequences."""
    text = str(value).replace("\\", "\\\\")
    named = {"\b": r"\b", "\t": r"\t", "\n": r"\n", "\f": r"\f", "\r": r"\r"}
    return CONTROL_CHARACTERS.sub(
        lambda match: named.get(match.group(0), f"\\u{ord(match.group(0)):04x}"),
        text,
    )


def trim_ascii(value):
    return str(value).strip(" \t")


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, f"错误: {escape_terminal(message)}\n")

def read_lines(path):
    with open(path, encoding="utf-8") as f:
        return re.split(r"\r?\n", f.read())


def validate_json_output(path, input_paths):
    """Reject existing outputs, with a specific guard for input aliases."""
    if not os.path.lexists(path):
        return
    try:
        output_stat = os.stat(path)
    except FileNotFoundError as error:
        raise FileExistsError(f"JSON 输出路径已存在且不可跟随,拒绝覆盖: {path}") from error
    for input_path in input_paths:
        if os.path.samestat(output_stat, os.stat(input_path)):
            raise ValueError(f"JSON 输出不得与输入指向同一文件: {path}")
    raise FileExistsError(f"JSON 输出已存在,拒绝覆盖: {path}")


def write_json_atomic(path, value):
    """Publish a complete JSON file atomically without replacing a target."""
    output = os.fspath(path)
    parent = os.path.dirname(os.path.abspath(output))
    data = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    temporary = None
    primary_error = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=parent, prefix=".memory-auditor-", delete=False
        ) as stream:
            temporary = stream.name
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, output)
    except BaseException as error:
        primary_error = error
    cleanup_error = None
    if temporary is not None:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        except BaseException as error:
            cleanup_error = error
    if primary_error is not None:
        if cleanup_error is not None:
            raise RuntimeError(
                f"{primary_error}; 临时文件清理失败: {cleanup_error}"
            ) from primary_error
        raise primary_error
    if cleanup_error is not None:
        raise RuntimeError(f"JSON 报告已发布,但临时文件清理失败: {cleanup_error}") from cleanup_error

def audit_markdown(path):
    """逐行静态审计:overclaim + 无证据完成声明 + 重复条款"""
    lines = read_lines(path)
    out = []
    seen = {}
    for i, line in enumerate(lines, 1):
        s = trim_ascii(line)
        if len(s) < 12: continue
        # 1) overclaim
        overclaim_found = False
        for p in OVERCLAIM_PATTERNS:
            for m in re.finditer(p, s, re.I):
                before = s[max(0, m.start() - 30):m.start()]
                after = s[m.end():m.end() + 30]
                if re.search(r"(禁|不|勿|拒绝|永不|避免|不得|防)", before) or re.search(
                    r"(禁|不|勿|拒绝|永不|避免|不得|防)", after
                ):
                    continue
                out.append({"file": path, "line": i, "issue": "overclaim",
                            "excerpt": s[:100], "hint": f"命中表述:{p[:24]}…请核对是否可辩护,或改为分级表述"})
                overclaim_found = True
                break
            if overclaim_found:
                break
        # 2) 完成声明但无证据词
        if DONE_WITHOUT_EVIDENCE.search(s) and not any(h in s for h in EVIDENCE_HINTS):
            if re.match(r"^(?:[-*]|\d+\.)", s):  # 列表条目才算,正文叙述放过
                out.append({"file": path, "line": i, "issue": "done_without_evidence",
                            "excerpt": s[:100], "hint": "完成类声明未附证据词(证据/receipt/哈希…);若为规则文本可忽略"})
        # 3) 重复条款(规范化后全库比对;表格行豁免)
        if s.startswith("|"): continue
        norm = re.sub(r"[ \t]+", "", s)[:60]
        if norm in seen:
            out.append({"file": path, "line": i, "issue": "duplicate",
                        "excerpt": s[:100], "hint": f"与第 {seen[norm]} 行近似重复"})
        else:
            seen[norm] = i
    return out

def audit_jsonl(path):
    """对 LESSONS.jsonl 类:检查每条的 evidence 字段"""
    lines = read_lines(path)
    out = []
    for i, line in enumerate(lines, 1):
        if not trim_ascii(line): continue
        try:
            d = json.loads(line)
        except Exception:
            out.append({"file": path, "line": i, "issue": "bad_json",
                        "excerpt": line[:80], "hint": "非 JSON 行"})
            continue
        if not isinstance(d, dict):
            out.append({"file": path, "line": i, "issue": "bad_json",
                        "excerpt": line[:80], "hint": "JSON 顶层必须是对象"})
            continue
        ev = d.get("evidence") or d.get("证据")
        if not ev or len(trim_ascii(ev)) < 20:
            out.append({"file": path, "line": i, "issue": "no_evidence",
                        "excerpt": str(d.get("claim") or d.get("id") or "")[:80],
                        "hint": "教训缺 evidence 或证据 <20 字符(无证据不写教训)"})
    return out

def main():
    ap = SafeArgumentParser(prog=escape_terminal(sys.argv[0]))
    ap.add_argument("files", nargs="+")
    ap.add_argument("--kind", choices=["md", "jsonl", "auto"], default="auto")
    ap.add_argument("--json-out", default=None, help="结果写 JSON 文件")
    args = ap.parse_args()
    if args.json_out:
        validate_json_output(args.json_out, args.files)
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
        print(f"\n[{x['issue']}] {escape_terminal(x['file'])}:{x['line']}")
        print(f"  原文: {escape_terminal(x['excerpt'])}")
        print(f"  提示: {escape_terminal(x['hint'])}")
    if args.json_out:
        write_json_atomic(args.json_out, findings)
        print(f"\nJSON 报告: {escape_terminal(args.json_out)}")

if __name__ == "__main__":
    try:
        main()
    except (OSError, UnicodeError, ValueError, RuntimeError) as error:
        print(f"错误: {escape_terminal(error)}", file=sys.stderr)
        sys.exit(1)
