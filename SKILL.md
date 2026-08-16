---
name: memory-auditor
description: 记忆审计技能:对 AI agent 的记忆文件(MEMORY.md/LESSONS.jsonl/规则库)做静态体检,扫出越界宣称(已达 AGI/最强/100% 成功)、无证据完成声明、重复条款;报告是候选不是判决,每条带行号与原文供人工复核。适用:审计自己或他人的 agent 记忆、季度记忆体检、向团队展示记忆质量时。
whenToUse: 用户要求审计 agent 记忆质量、怀疑某份记忆文件有过度推广或假完成、或需要客观证据证明记忆可信度时。
---

# 记忆审计器

```bash
python3 memory_auditor.py MEMORY.md LESSONS.jsonl rules.md
python3 memory_auditor.py 记忆.md --json-out report.json
```

- 三类检测:overclaim / done_without_evidence / duplicate
- 铁律:候选≠判决;否定语境(禁用/永不/禁止±30字符)与表格行已豁免
- 深度层(--deep,四视角评审)规划中;静态层零依赖零成本
- 自校准实录见 README(7→2→1→0,顺手修掉自家 MEMORY 的一条真问题)
