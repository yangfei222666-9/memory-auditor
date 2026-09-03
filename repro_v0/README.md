# memory-auditor 复现包 v0 格式（本地候选 revision v5）

`package_state_at_build=local_candidate_unpublished` 只记录 v5 建包时的本地快照，不代表阅读时的发布状态，也不是“10 分钟可复现”或公开验证。当前状态必须由 `publication_status_authority=external_git_release_ci_and_human_receipts` 指向的外部 Git、release、CI 和人类验收证据共同判定；本文不凭包内文字提供下载位置或升级状态。只 clone 固定审计器 SHA **不会**得到这个包装入口。

两个独立版本锁：审计器 `e64d2f31d93726e2e8ea1879e61cdfd392d2fb04`；复现包版本由 `MANIFEST.json` 的 SHA256 表示。`historical_public_head_at_v0_build=8c083d501302e0f8389b684584e05040cffc33b2` 仅保留最初 v0 的历史公开快照；本地 v5 构建绑定 `local_repo_head_at_v5_build=cc5762a69dc212a9a67ab57a3615b46a031c72ae`。建包时未查询 live remote，因此 `live_public_head_at_v5_build=null`，不能把本地 tracking ref 写成公开现状。`embedded_package_commit_sha=null` 同样只是构建快照，不表示当前是否存在公开包 commit。若外部证据已确认公开包 SHA，通过可选参数 `--package-commit FULL40HEX` 传入，不写回包内文件或改变 manifest；`FULL40HEX` 必须替换为经确认的完整 40 位十六进制公开包 commit SHA。

## 执行前完整性核验（不运行包内 Python）

先从与 ZIP 分离的可信交付记录取得完整 ZIP SHA256 与 `MANIFEST.json` SHA256。不得只相信 ZIP 内部或聊天里重复的值。拿到 ZIP 后，在执行下列第一条命令前启动外部秒表；该计时范围是“取得产物之后的完整性核验、解压、README阅读与collector执行”，不包含产物下载/传输时间。设置变量后执行：

```bash
MA_TIMER_SCOPE=post_acquisition_verification_and_execution
: "${MA_ARCHIVE:?set MA_ARCHIVE to the downloaded ZIP path}"
: "${MA_ARCHIVE_SHA256:?set MA_ARCHIVE_SHA256 from the trusted delivery record}"
: "${MA_MANIFEST_SHA256:?set MA_MANIFEST_SHA256 from the trusted delivery record}"
ma_actual_archive_sha256="$(shasum -a 256 "$MA_ARCHIVE" | awk '{print $1}')"
test "$ma_actual_archive_sha256" = "$MA_ARCHIVE_SHA256"
ma_actual_manifest_sha256="$(unzip -p "$MA_ARCHIVE" memory-auditor-repro-v0/MANIFEST.json | shasum -a 256 | awk '{print $1}')"
test "$ma_actual_manifest_sha256" = "$MA_MANIFEST_SHA256"
unzip -t "$MA_ARCHIVE"
ma_run_dir="$(mktemp -d "${TMPDIR:-/tmp}/memory-auditor-repro-v5.XXXXXX")"
unzip -q "$MA_ARCHIVE" -d "$ma_run_dir"
cd "$ma_run_dir/memory-auditor-repro-v0"
```

任一 `test` 或 `unzip -t` 非零就停止，不运行任何包内 Python。当前本地 sidecar validation 只能辅助核对；正式复跑须从单独授权的公开发布记录取得两个 hash。

## 环境与三种人类运行模式

需要 Python 3.9+ 与 Git；执行前完整性核验还要求 POSIX shell、`shasum`、`awk`、`unzip`、`mktemp`。Python 依赖仅使用标准库。没有 pip/npm/Node、DSH、provider、密钥、sudo、全局安装、常驻进程或服务端口。构建验证环境为 macOS arm64 / Python 3.9.6；真实 owner cold run、Linux、其他 Python 版本均未验证。

外部秒表应已在上一节完整性核验的第一条命令前启动；进入本节后不要重启或暂停。程序另用单调时钟记录自身入口之后的 `program_elapsed_seconds`，它不能替代外部总计时。完整性核验、解压、README阅读、clone失败、操作错误及等待断网均计入；产物下载/传输时间另记，本包不能据此宣称端到端下载加复现小于等于600秒。

```bash
python3 -B owner_run.py --tester-role owner
```

不带公开包 SHA 调用此命令时，receipt 模式标记为 owner rehearsal，不能与后续 independent receipt 合并为正式双人验收。公开包冻结后，owner 和 independent 都须重新运行并追加同一个真实的 `--package-commit FULL40HEX`；independent 缺少此参数直接返回 `3=INVALID_INPUT`。

正式 owner acceptance（只在公开包 commit 已存在并经单独授权后）：

```bash
python3 -B owner_run.py --tester-role owner --package-commit FULL40HEX
```

正式 independent acceptance（由未参与建包且只看 README 的测试者执行）：

```bash
python3 -B owner_run.py --tester-role independent --package-commit FULL40HEX
```

三条命令不能互相替代。包内 `embedded_package_commit_sha=null` 不是当前状态声明；无 `--package-commit` 的运行按契约标记为 rehearsal，formal owner/independent acceptance 候选必须绑定经外部证据确认的同一完整 SHA。

按屏幕提示如实回答是否接触过项目、是否首次 clone、是否已有仓库/虚拟环境/缓存、是否得到作者帮助、是否只按 README 操作。未知填 `unknown`，不清全机缓存，不把热缓存写成冷机。作者口头解释/成功演示也算帮助。

仅获取阶段运行 `git ls-remote` 和 `git clone --no-checkout`，声明的远程只有 `https://github.com/yangfei222666-9/memory-auditor.git`。程序比较本次 clone 的 tracking HEAD 与获取开始时读取的 live remote HEAD；clone 后按提示断开**所有**网络接口，再确认 `yes`。若提供公开包 SHA，程序要求它是可从该 live HEAD 到达的 commit，核对该 commit 根 `LICENSE` 为普通 `100644` 文件且字节与包内许可证一致，并验证 `repro_v0/` 恰好由 `MANIFEST.json` 与清单列出的普通 `100644` 文件组成，逐项比较 manifest 和文件 hash。填入 SHA 本身不构成验证。随后离线 checkout 固定审计器 SHA、核对历史源码许可证、分别审计 problem/clean，并记录 Git tree 与包 hash。程序禁用 Git 全局配置和 credential helper，不读取密钥；不继承代理配置，网络不可达时保留失败而不重试。

扫描子进程用 Python audit hook 拒绝 socket/子进程调用，但这不是 OS 网络隔离或抓包。`network_observed` 明示用户断网确认及未观测部分，不能自动把“未尝试”写成“全机无外联”。真正网络验收需人工复核，发现额外外联记 blocker。

成功执行两份 fixture 后，输入从完整性核验第一条命令前开始的外部秒表总秒数。外部总秒数未知时，`within_600_seconds=null`，不能靠程序内部计时认定通过；NaN、Inf 和负数拒绝作为有效计时。程序计时或任何已知总计时超过 600 秒均记 `FAILED`、返回 4。程序打印这次新建临时目录内 `receipt.json` 的路径；保留整个目录和失败记录。即使上述 formal Git 与包校验全部成功，collector 仍只收集证据，receipt 默认 `PENDING`，不自动签署冷跑 PASS；公开 archive URL 与内容 hash 读回、exact-SHA CI 成功及 owner/independent 双人 receipt 验收仍由外部 gate 判定，网络、环境与独立性也须人工审核。

## 单一退出码表

| code | 意义 |
|---|---|
| 0 | CLEAN：输入有效、报告落盘、候选数为 0 |
| 2 | CANDIDATE_FINDINGS：输入有效、报告落盘、有候选；不是执行失败 |
| 3 | INVALID_INPUT：不存在/不合规/fixture 或源码 hash 不符；无新成功报告 |
| 4 | EXECUTION_ERROR：未预期错误、输出/receipt 写失败、超时或契约不符 |

内层 problem 命令预期 **2**，clean 预期 **0**；完整 collector 返回 **2**，因为总结果包含 problem 候选。各子命令、原始 stdout/stderr、预期/实际退出码均写 receipt；信号、超时、未声明码不能算通过。CLI `--help` 是说明，不是一次审计。

`problem.md` 有 10 条人工合成记忆：行 1 `done_without_evidence`、行 2 `overclaim`、行 4 `duplicate`，共 3 个候选。`clean.md` 是这 10 条的干净对照，应为 0。报告必须同时保留两份结果，输出明示 **candidate, not verdict / 候选，不是判决**。没有复制真实记忆、主机路径或私人账本。

## 解压即跑布局 smoke（两条命令）

以下仅验证 ZIP 布局、固定引擎、两份 fixture 和退出码契约，不执行 clone，也不是 owner cold run。请在解压后的本包目录原样运行；每条命令各自创建新的临时报告目录：

```bash
ma_problem_dir="$(mktemp -d "${TMPDIR:-/tmp}/memory-auditor-problem.XXXXXX")"; python3 -B audit.py --engine pinned-engine.py --fixture fixtures/problem.md --output "$ma_problem_dir/problem.json"; ma_problem_code=$?; test "$ma_problem_code" -eq 2
ma_clean_dir="$(mktemp -d "${TMPDIR:-/tmp}/memory-auditor-clean.XXXXXX")"; python3 -B audit.py --engine pinned-engine.py --fixture fixtures/clean.md --output "$ma_clean_dir/clean.json"; ma_clean_code=$?; test "$ma_clean_code" -eq 0
```

两条 shell 命令最终都应返回 0；其中内层 problem 审计仍按契约返回 2，clean 返回 0。保留打印出的候选与报告 hash；不能把这段 builder smoke 当作 owner/independent receipt。

## Receipt、限制与公开门

receipt 包括固定 SHA/公开 HEAD、包/中英 README/fixture/许可证/report/stdout/stderr hash，OS/架构、Python/Git、完整命令、退出码、候选数、计时、Git tree、网络和独立性声明。未知不补造；报告已有则拒绝覆盖。清单列出包内全部文件，唯独不自哈希 `MANIFEST.json`，它自身的 hash 单列进 receipt。

词法匹配不是语义判决：存在假阳性/假阴性、短行跳过、否定窗口近似、证据关键词可被误用、无法验证真实证据。不是生产安全工具，不能证明整个管家或所有平台可复现。包装器只接受这两份冻结 Markdown fixture；不扩充原算法、不执行 `--deep`。

本包采用 MIT；[LICENSE](LICENSE) 的署名为 `Copyright (c) 2026 yangfei222666-9`。`pinned-engine.py` 是固定 commit 中 `memory_auditor.py` 的逐字节副本，只用于 builder/布局自检；其来源、用途与分发授权见 [FIXTURE_LICENSE.md](FIXTURE_LICENSE.md) 和 `pinned.json`。固定历史源码 commit 仍带原占位 notice，`source_repo_license_sha256` 与当前包的 `package_license_sha256` 分开记录，不能互相替代。包内 LICENSE 与仓库工作树根 LICENSE 已在本地 v5 对齐；任一公开 commit 的根 LICENSE、包文件和发布状态只能由 formal 运行及 `publication_status_authority` 指向的外部证据证明。

owner 冷跑必须由小九执行，Codex 的 builder tests 不算。发布单独授权并固定公开包 commit/README 后，小九和未参与建包、未看过演示的陌生人须分别重新运行相同命令，仅 role 分别为 `owner` 和 `independent`，并传入同一公开包 SHA。先前无公开包 SHA 的 rehearsal 不计入这两份 receipt。两次须同一审计器 SHA、同一包清单与 fixture，真实总用时均 ≤600 秒；陌生人不能得到 README 之外帮助。回帖/截图只能指向完整 receipt，不代替它。公开 URL 内容 hash 读回之前不宣称 verified_public。

失败保留原 run_id；修包重跑另建目录、另记“协助后重跑”，不覆盖失败。回滚无需系统卸载：确认程序已退出后，仅把本次打印的 `memory-auditor-repro-v0-*` 临时目录移到废纸篓，先保存 receipt，不碰其他目录。

## 解压布局自检（不是冷跑）

在解压后的本包目录运行第二条 README 命令：

```bash
REPRO_TEST_ENGINE=./pinned-engine.py python3 -B -m unittest discover -s . -p test_contract.py -v
```

`pinned-engine.py` 只用于 builder 自检，内容来自固定审计器 commit，SHA256 必须与 `pinned.json` 一致；owner 流程仍从本次 clone 的 Git 对象读取引擎。collector 测试仅使用全 mock 的 Git/进程/输入，临时模拟 receipt 随测试清理，不能当真人验收。没有真实 clone 或 owner cold run。规范末尾旧 Node 条款与正文冲突，本包采用更窄的 Python-only 边界。
