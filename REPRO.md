# 10-Minute Reproduction

## 前置

仅需 Node.js >= 20；不需要 Python、数据库、容器或常驻服务。

```bash
npm install --ignore-scripts --no-audit --no-fund
```

## 数据

`examples/sample-ledger.jsonl` 内置 10 条完全虚构的账本记录。所有 ID、声明和证据均为演示内容，不含真实用户内容、密钥、令牌、主机名或文件路径。其中 4 条故意缺少证据或证据过短，用于产生可复核候选。

## 运行

在仓库根目录执行以下两条命令：

```bash
npm run audit -- examples/sample-ledger.jsonl
npm run audit -- examples/sample-ledger.jsonl --json-out report.json
```

第一条在终端输出审计结果；第二条同时生成机器可读的 `report.json`。

## 期望输出

以下摘要来自 2026-08-25 的干净临时目录冷跑，不是手写模拟结果：

```text
# 记忆审计报告 v0.1:共 4 条候选发现(候选≠判决,逐条复核)
按类型: {"no_evidence":4}

[no_evidence] sample-ledger.jsonl:3
[no_evidence] sample-ledger.jsonl:6
[no_evidence] sample-ledger.jsonl:8
[no_evidence] sample-ledger.jsonl:10

JSON 报告: report.json
```

本次生成的 `report.json` 为 868 bytes，SHA-256 为 `f07a22b87748ea88fa3d8768e755eff9057d0d9ee7b21c6d8879438acda88cd4`。发现是候选项，不是事实判决。

## 回滚

删除克隆目录即可恢复干净状态。安装只在仓库内生成/使用 npm 元数据，不写系统级配置，不启动服务，也不修改输入样例。

## 已知限制

- 不增量：每次运行都重新读取全部输入文件，没有增量索引或变更检测。
- 不做语义检索：静态规则只做词法匹配和字段检查，不使用向量库、embedding 或模型推理。
- Markdown 边界：完成声明只检查列表项；短于 12 字符的行跳过；否定语境使用正负 30 字符启发式窗口，存在误报和漏报。
- JSONL 边界：只检查每行 JSON 是否可解析，以及 `evidence`/`证据` 字段是否存在且至少 20 字符；不验证证据真实性、可访问性或与声明的因果关系。
- 重复检测边界：仅在单个 Markdown 文件内按去空白后的前 60 字符比较，表格行跳过；不做跨文件或语义重复检测。
- 输出边界：报告是人工复核候选，不可直接升级为事实、PASS、运行就绪或生产结论。
- 运行边界：Node 入口覆盖当前静态层；README 中规划的 `--deep` 深度层尚未实现。

## Receipt

```text
event_id: memory-auditor-repro-20260825T050310+0800
scope: Node-only 10-minute reproduction package; local candidate workspace only
input_evidence: main@e64d2f31d93726e2e8ea1879e61cdfd392d2fb04; source worktree already contained the seven untracked candidate paths listed below when this run began; staged set empty
environment: macOS; Node v24.16.0; required floor Node >=20
commands_run:
  1. git clone --no-hardlinks https://github.com/yangfei222666-9/memory-auditor /tmp/memory-auditor-repro/repo
  2. copy the explicit uncommitted candidate files into the temporary clone
  3. npm install --ignore-scripts --no-audit --no-fund
  4. npm run audit -- examples/sample-ledger.jsonl
  5. npm run audit -- examples/sample-ledger.jsonl --json-out report.json
  6. npm test
timing:
  clone: 0.04s
  install: 0.32s
  stdout audit: 0.14s
  JSON audit: 0.14s
  Node tests: 0.20s
validation:
  install_exit: 0
  stdout_audit_exit: 0
  json_audit_exit: 0
  node_tests: 7 passed, 0 failed
  findings: 4 no_evidence candidates at lines 3, 6, 8, 10
  report_sha256: f07a22b87748ea88fa3d8768e755eff9057d0d9ee7b21c6d8879438acda88cd4
changed_files: REPRO.md; examples/sample-ledger.jsonl; memory-auditor.mjs; package.json; package-lock.json; tests/test_memory_auditor.mjs; receipts/repro-2026-08-25.log
hash_or_SHA: source HEAD e64d2f31d93726e2e8ea1879e61cdfd392d2fb04; sample SHA-256 1ebd8c931d61aa0e783ea9928f619b3cb2ec48e6e9b2972f15c51c24864abb75
verdict: PASS (local cold reproduction scope only)
blocker: none for local reproduction
cannot_claim: remote repository contains these files; npm registry publication; CI PASS; semantic correctness; production readiness
next_gate: human review, then separately authorized stage/commit/push if desired
```

冷跑采用“clone 当前 HEAD + 覆盖接手时已有的七个未提交候选文件”，因为本任务明确禁止 push，且未授权 commit。实际临时目录为 `/tmp/memory-auditor-repro`，验证后已删除。它证明当前本地候选包可在干净目录安装和运行；不证明远端仓库已包含这些改动。

### 2026-08-25 当前回合独立复核

```text
event_id: memory-auditor-repro-codex-verify-20260825T051042+0800
commands_run:
  1. git clone --no-hardlinks https://github.com/yangfei222666-9/memory-auditor /tmp/memory-auditor-repro/repo
  2. copy REPRO.md, sample, Node entry, package metadata, and Node test into the clone
  3. npm install --ignore-scripts --no-audit --no-fund
  4. npm run audit -- examples/sample-ledger.jsonl
  5. npm run audit -- examples/sample-ledger.jsonl --json-out report.json
  6. npm test
environment: Node v24.16.0; npm 11.17.0
timing: clone 0.04s; install 0.29s; stdout audit 0.12s; JSON audit 0.11s; tests 0.16s
validation: install and both audit commands exited 0; 4 no_evidence candidates at lines 3, 6, 8, 10; 7 tests passed, 0 failed; sample sensitive-pattern scan PASS
hash_or_SHA: source HEAD e64d2f31d93726e2e8ea1879e61cdfd392d2fb04; sample SHA-256 1ebd8c931d61aa0e783ea9928f619b3cb2ec48e6e9b2972f15c51c24864abb75; report SHA-256 f07a22b87748ea88fa3d8768e755eff9057d0d9ee7b21c6d8879438acda88cd4
verdict: PASS_LOCAL_COLD_REPRO
cannot_claim: remote repository contains candidate files; CI PASS; publication; semantic correctness; production readiness
```

### 2026-08-25 最终冷跑复核

```text
event_id: memory-auditor-repro-final-verify-20260825T051607+0800
commands_run:
  1. git clone --no-hardlinks <local-repo> <temporary-directory>/repo
  2. copy the explicit candidate files into the clone
  3. npm install --ignore-scripts --no-audit --no-fund
  4. npm run audit -- examples/sample-ledger.jsonl
  5. npm run audit -- examples/sample-ledger.jsonl --json-out report.json
  6. npm test
environment: Node v24.16.0; npm 11.17.0
timing: clone 0.03s; install 0.27s; stdout audit 0.10s; JSON audit 0.11s; tests 0.15s
validation: install and both audit commands exited 0; 4 no_evidence candidates at lines 3, 6, 8, 10; 7 tests passed, 0 failed; sample contains 10 valid synthetic records; sensitive-pattern scan PASS
hash_or_SHA: source HEAD e64d2f31d93726e2e8ea1879e61cdfd392d2fb04; sample SHA-256 1ebd8c931d61aa0e783ea9928f619b3cb2ec48e6e9b2972f15c51c24864abb75; report SHA-256 f07a22b87748ea88fa3d8768e755eff9057d0d9ee7b21c6d8879438acda88cd4
verdict: PASS_LOCAL_COLD_REPRO
cannot_claim: remote repository contains candidate files; CI PASS; publication; semantic correctness; production readiness
temporary_clone: created with mktemp and deleted after validation
```

### 2026-08-25 本轮交付复核

```text
event_id: memory-auditor-repro-root-verify-20260825T052035+0800
scope: existing local candidate package; independent clean-directory reproduction
input_evidence: main@e64d2f31d93726e2e8ea1879e61cdfd392d2fb04; staged set empty; candidate files were already untracked before this verification
commands_run:
  1. git clone --no-hardlinks <local-repo> /tmp/memory-auditor-repro/repo
  2. copy the explicit untracked candidate files into the temporary clone
  3. npm install --ignore-scripts --no-audit --no-fund
  4. npm run audit -- examples/sample-ledger.jsonl
  5. npm run audit -- examples/sample-ledger.jsonl --json-out report.json
  6. npm test
environment: macOS; Node v24.16.0; npm 11.17.0; required floor Node >=20
timing: clone 0.06s; install 0.28s; stdout audit 0.13s; JSON audit 0.12s; tests 0.16s
validation: all commands exited 0; 7 tests passed, 0 failed; 10 valid synthetic records; 4 no_evidence candidates at lines 3, 6, 8, 10; sensitive-pattern scan PASS
hash_or_SHA: source HEAD e64d2f31d93726e2e8ea1879e61cdfd392d2fb04; sample SHA-256 1ebd8c931d61aa0e783ea9928f619b3cb2ec48e6e9b2972f15c51c24864abb75; report SHA-256 f07a22b87748ea88fa3d8768e755eff9057d0d9ee7b21c6d8879438acda88cd4
verdict: PASS_LOCAL_COLD_REPRO
blocker: none for local reproduction
cannot_claim: files are in remote repository; CI PASS; publication; semantic correctness; production readiness
next_gate: human review; stage, commit, and push remain separately unauthorized
```

本轮完整摘要另存为 `receipts/repro-2026-08-25-root-verify.log`。公开文档将本机源仓库绝对路径写作 `<local-repo>`；临时目录路径保留用于本轮审计，验证后采用可恢复方式清理。

### 2026-08-25 当前交付冷跑

```text
event_id: memory-auditor-repro-turn-verify-20260825
commands_run:
  1. git clone --no-hardlinks <local-repo> /tmp/memory-auditor-repro/repo
  2. copy the explicit Node candidate files and sample into the clone
  3. npm install --ignore-scripts --no-audit --no-fund
  4. npm run audit -- examples/sample-ledger.jsonl
  5. npm run audit -- examples/sample-ledger.jsonl --json-out report.json
  6. npm test
environment: Node v24.16.0; npm 11.17.0
timing: clone 0.04s; install 0.26s; stdout audit 0.10s; JSON audit 0.12s; tests 0.17s
validation: all commands exited 0; 7 tests passed, 0 failed; 10/10 records marked synthetic; sensitive-pattern scan PASS; 4 no_evidence candidates at lines 3, 6, 8, 10
hash_or_SHA: source HEAD e64d2f31d93726e2e8ea1879e61cdfd392d2fb04; sample SHA-256 1ebd8c931d61aa0e783ea9928f619b3cb2ec48e6e9b2972f15c51c24864abb75; report SHA-256 f07a22b87748ea88fa3d8768e755eff9057d0d9ee7b21c6d8879438acda88cd4
verdict: PASS_LOCAL_COLD_REPRO
blocker: source worktree remains dirty with pre-existing untracked candidate files
cannot_claim: remote repository contains candidate files; CI PASS; npm publication; semantic correctness; production readiness
cleanup: temporary directory moved to macOS Trash and remains recoverable
```

完整日志：`receipts/repro-2026-08-25-turn-verify.log`。
