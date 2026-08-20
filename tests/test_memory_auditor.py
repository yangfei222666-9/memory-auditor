#!/usr/bin/env python3
"""stdlib-only unit tests for memory-auditor (audit_markdown / audit_jsonl core judgment logic).

Zero dependencies: unittest from the standard library only. Run:
    python3 -m unittest discover -s tests -v
"""
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import memory_auditor as ma  # noqa: E402


class TestAuditMarkdown(unittest.TestCase):

    def _write(self, content):
        fd, path = tempfile.mkstemp(suffix=".md")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        self.addCleanup(os.unlink, path)
        return path

    def test_overclaim_detected(self):
        path = self._write("我们的系统已达 AGI 水平,自主运行一切任务。\n")
        findings = ma.audit_markdown(path)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["issue"], "overclaim")
        self.assertEqual(findings[0]["line"], 1)

    def test_overclaim_negation_exempt_before(self):
        # 否定语境(前窗)豁免:规则文本"禁用已达 AGI"
        path = self._write("纪律:禁用已达 AGI 之类的表述,永不宣称最强。\n")
        findings = ma.audit_markdown(path)
        self.assertEqual([f["issue"] for f in findings], [])

    def test_overclaim_negation_exempt_after(self):
        # 否定语境(后窗)豁免
        path = self._write("100% 成功 这类话不允许出现在记忆里。\n")
        findings = ma.audit_markdown(path)
        self.assertEqual(findings, [])

    def test_done_without_evidence_list_item(self):
        # 列表条目 + 完成类声明 + 无证据词 → 命中
        path = self._write("- 备份迁移问题已解决,不用再看了\n")
        findings = ma.audit_markdown(path)
        self.assertEqual([f["issue"] for f in findings], ["done_without_evidence"])

    def test_done_with_evidence_not_flagged(self):
        # 完成声明带了证据词(receipt/哈希)→ 不命中
        path = self._write("- 备份迁移问题已解决,receipt 已入账,哈希可查\n")
        findings = ma.audit_markdown(path)
        self.assertEqual(findings, [])

    def test_done_prose_not_flagged(self):
        # 正文叙述(非列表条目)完成声明 → 放过
        path = self._write("这批问题昨天已解决,接下来看新任务。\n")
        findings = ma.audit_markdown(path)
        self.assertEqual(findings, [])

    def test_duplicate_detected(self):
        path = self._write("- 每天 08:00 巡检备份状态\n- 每天 08:00 巡检备份状态\n")
        findings = ma.audit_markdown(path)
        dups = [f for f in findings if f["issue"] == "duplicate"]
        self.assertEqual(len(dups), 1)
        self.assertEqual(dups[0]["line"], 2)
        self.assertIn("第 1 行", dups[0]["hint"])

    def test_table_rows_exempt_from_duplicate(self):
        # 表格行豁免:表头重复不算 duplicate
        path = self._write("| 列 | 说明 |\n|---|---|\n| 列 | 说明 |\n")
        findings = ma.audit_markdown(path)
        self.assertEqual(findings, [])

    def test_short_lines_skipped(self):
        # <12 字符的行不做检测
        path = self._write("已完成\n")
        findings = ma.audit_markdown(path)
        self.assertEqual(findings, [])


class TestAuditJsonl(unittest.TestCase):

    def _write(self, content):
        fd, path = tempfile.mkstemp(suffix=".jsonl")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        self.addCleanup(os.unlink, path)
        return path

    def test_evidence_ok(self):
        path = self._write(json.dumps(
            {"id": "L1", "claim": "教训一", "evidence": "复现步骤与命令输出截图链接,长度足够超过二十个字符"},
            ensure_ascii=False) + "\n")
        findings = ma.audit_jsonl(path)
        self.assertEqual(findings, [])

    def test_no_evidence_flagged(self):
        path = self._write(json.dumps(
            {"id": "L2", "claim": "无证据教训"}, ensure_ascii=False) + "\n")
        findings = ma.audit_jsonl(path)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["issue"], "no_evidence")

    def test_short_evidence_flagged(self):
        # evidence <20 字符 → 命中
        path = self._write(json.dumps(
            {"id": "L3", "evidence": "短"}, ensure_ascii=False) + "\n")
        findings = ma.audit_jsonl(path)
        self.assertEqual([f["issue"] for f in findings], ["no_evidence"])

    def test_bad_json_flagged(self):
        path = self._write("这不是 JSON 行\n")
        findings = ma.audit_jsonl(path)
        self.assertEqual([f["issue"] for f in findings], ["bad_json"])

    def test_blank_line_skipped(self):
        path = self._write("\n")
        findings = ma.audit_jsonl(path)
        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
