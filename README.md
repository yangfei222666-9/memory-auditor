# memory-auditor · AI 记忆审计器

扫描 AI agent 的记忆和教训文件，找出**无证据声明、越界宣称、重复条款**。每条结果包含文件、行号、原文和提示，供人逐条复核。

**报告是候选，不是判决。** 静态审计使用 Python 标准库，不调用模型或 provider API，不需要 API Key，也不修改输入文件。下面先用仓库自带的虚构数据试跑。

## 首次试用

需要 Git 和 Python 3.9+；无需 pip、npm、DSH 或后台服务。在准备存放项目的目录执行：

```bash
git clone https://github.com/yangfei222666-9/memory-auditor.git
cd memory-auditor
python3 -B memory_auditor.py examples/sample-ledger.jsonl
```

只有获取仓库的 `git clone` 需要联网。克隆后，这条审计命令可离线运行，只读取本地样例并把结果打印到终端。

样例含 10 条虚构记录，预期输出开头为：

```text
# 记忆审计报告 v0.1:共 4 条候选发现(候选≠判决,逐条复核)
按类型: {'no_evidence': 4}
```

后续四条发现分别指向 `examples/sample-ledger.jsonl` 的 **3、6、8、10 行**，原因是缺少 `evidence` 或该字段不足 20 字符。样例中的证据也都是虚构文字；这个结果只验证字段检查，不验证证据真实性。

根目录的 Python CLI 在审计正常结束时返回 **0，即使发现候选也是如此**。参数错误返回 2；文件读取、JSON 输出等已捕获错误返回 1。正式复现包有自己的退出码约定，见下方入口。

需要保存结果时，在仓库根目录执行：

```bash
python3 -B memory_auditor.py examples/sample-ledger.jsonl --json-out sample-report.json
```

这会新建 `sample-report.json`，内容是四条候选组成的 JSON 数组，不写回样例。输出文件已存在时会拒绝覆盖；再次保存请换一个新文件名。

## 检查自己的文件

在仓库根目录把下面的路径替换成你的文件路径；含空格时保留引号：

```bash
python3 -B memory_auditor.py "/path/to/MEMORY.md" "/path/to/LESSONS.jsonl"
```

程序只读取指定文件，不搜索其他目录、不修改用户记忆。终端结果和可选 JSON 报告会包含命中的原文；分享报告前请检查其中的私人内容。

默认按扩展名选择格式：`.jsonl` 和 `.json` 按每行一个 JSON 对象处理，其余按 Markdown 处理。支持 `--kind md` 或 `--kind jsonl` 手动指定；完整参数可用 `python3 -B memory_auditor.py --help` 查看。

| 输入 | 候选类型 | 检查内容 |
|---|---|---|
| Markdown | `overclaim` | “已达/接近 AGI”“最强”“100% 成功”等表述，带启发式否定语境豁免 |
| Markdown | `done_without_evidence` | 列表项中的完成声明未附证据词 |
| Markdown | `duplicate` | 同文件内规范化后前 60 字符相同的条款，表格行豁免 |
| JSONL | `no_evidence` | `evidence` / `证据` 字段缺失或去除首尾空格、制表符后不足 20 字符 |
| JSONL | `bad_json` | 行内容无法解析为 JSON 对象 |

深度模型评审仍在规划中；当前 CLI **没有 `--deep` 参数**。相关独立工具见 [multi-model-review](https://github.com/yangfei222666-9/dsh-skill-multi-model-review)。

## 正式复现包与验收

完成上面的功能试用后，如果要核对固定源码、归档完整性和 owner / independent 冷跑凭据，进入：

- [中文说明](repro_v0/README.md)
- [English guide](repro_v0/README.en.md)

本页试用运行的是根目录的当前审计器，不产生 owner / independent 验收 receipt。`repro_v0` 保留构建时的本地候选元数据；当前发布状态、精确提交上的 CI、归档内容和双人冷跑验收，以对应的 Git / release / CI / 人工凭据为准。

## 自校准实录(2026-08-16 夜班首跑)

| 轮次 | 结果 |
|---|---|
| v0.1 | 7 条:1 真(完成声明无证据词)+ 2 假(规则文本"禁用已达 AGI"被误报)+ 4 假(表格表头重复) |
| v0.2 | 表格行豁免 → 剩 2 条 |
| v0.3 | 双向否定窗口(禁/不/勿/永不 ±30 字符)→ 剩 1 条真发现 |
| 修掉真发现 | 重跑 = **0 条** |

## 已知边界

- 静态层是词法级,不读语义;深度层上线前,复杂误导仍会漏
- 中文否定语境复杂("不是不宣称"),±30 字符窗口是启发式
- Markdown 中短于 12 字符的行会跳过；JSONL 中存在证据字段也不代表证据真实或支持结论
- 上述自校准实录来自历史单一语料；0 条候选不等于内容正确，也不证明其他文件的误报率或漏报率

## 开发验证

在仓库根目录运行标准库测试：

```bash
python3 -B -m unittest discover -s tests -v
```

## 许可证

[MIT License](LICENSE) — Copyright (c) 2026 yangfei222666-9
