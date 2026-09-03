# memory-auditor · AI Agent Memory Auditor

A static "health check" for AI agent memory files: scans for **done-without-evidence claims, overclaims, and duplicate clauses**. Two layers:

- **Static rule layer** (zero cost, instant): pure Python standard library, three detections
  - `overclaim` — indefensible phrases such as "reached/close to AGI", "the strongest", "100% success" (negation contexts are exempt)
  - `done_without_evidence` — completion statements (fixed/resolved/done) with no evidence word nearby
  - `duplicate` — near-duplicate clauses (table rows exempt)
- **Deep layer (planned)**: `--deep` sends findings to a four-view review (reuses [multi-model-review](../dsh-skill-multi-model-review))

Design rule: **the report is a candidate, not a verdict** — every finding carries the file, line number, original text, and a hint; a human reviews each one before it counts. That is exactly the principle this tool exists to defend: distrust yourself first, then distrust others.

## Current reproduction package

- [中文说明](repro_v0/README.md)
- [English guide](repro_v0/README.en.md)

The metadata embedded in `repro_v0` records its local-candidate state at build time. Current publication, exact-commit CI success, archive-content identity, and dual-human cold-run acceptance must be established from the corresponding Git, release, CI, and human receipts. File presence or local test output alone does not establish those states.

## Usage

```bash
python3 memory_auditor.py MEMORY.md LESSONS.jsonl rules.md GROWTH.md
python3 memory_auditor.py MEMORY.md --json-out report.json
```

## Self-calibration record (first night-shift run, 2026-08-16)

| Round | Result |
|---|---|
| v0.1 | 7 findings: 1 true (done-without-evidence) + 2 false (rule text "禁用已达 AGI" false-positive) + 4 false (table header duplicates) |
| v0.2 | Table rows exempt → 2 findings left |
| v0.3 | Bidirectional negation window (禁/不/勿/永不 ±30 chars) → 1 true finding left |
| Fixed the true finding | Re-run = **0 findings** |

## Known limits

- The static layer is lexical, not semantic; complex misleading text will slip through until the deep layer ships
- Chinese negation contexts are complex ("不是不宣称"); the ±30-character window is a heuristic

## Development

```bash
python3 -m unittest discover -s tests -v
```

## License

[MIT License](LICENSE) — Copyright (c) 2026 yangfei222666-9

## Known limitations (honest)

- The self-calibration table's "re-run = 0 findings" only proves the rules were updated, **not** that detection capability improved. Treat it as a regression guard, not a benchmark.
- Rules were tuned and validated on one night-shift snapshot of one corpus. False-positive/negative rates on other memory files are unknown.
- The ±30-character negation window is a lexical heuristic; complex sentences or double negations may still slip through.
