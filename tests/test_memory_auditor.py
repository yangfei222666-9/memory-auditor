#!/usr/bin/env python3
"""stdlib-only unit tests for memory-auditor (audit_markdown / audit_jsonl core judgment logic).

Zero dependencies: unittest from the standard library only. Run:
    python3 -m unittest discover -s tests -v
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

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

    def test_negated_match_does_not_hide_later_same_pattern(self):
        path = self._write(
            "- 禁止使用最强这种表述；中性说明一二三四五六七八九十甲乙丙丁戊己庚辛壬癸。"
            "我们的模型最强。\n"
        )
        findings = ma.audit_markdown(path)
        self.assertEqual([f["issue"] for f in findings], ["overclaim"])

    def test_nel_at_edges_is_not_silently_trimmed_into_a_list_item(self):
        path = self._write("\u0085- 备份迁移问题已解决,马上关闭工单吧\u0085\n")
        self.assertEqual(ma.audit_markdown(path), [])

    def test_nel_does_not_count_as_pattern_whitespace(self):
        path = self._write("我们的系统已达\u0085AGI 水平,自主运行一切任务。\n")
        self.assertEqual(ma.audit_markdown(path), [])

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

    def test_non_object_json_records_are_flagged_without_crashing(self):
        path = self._write("null\n[]\n42\n\"text\"\n")
        findings = ma.audit_jsonl(path)
        self.assertEqual([f["issue"] for f in findings], ["bad_json"] * 4)

    def test_nel_only_jsonl_line_is_bad_json_not_blank(self):
        path = self._write("\u0085\n")
        findings = ma.audit_jsonl(path)
        self.assertEqual([f["issue"] for f in findings], ["bad_json"])


class TestPythonCliContract(unittest.TestCase):

    def setUp(self):
        folder = tempfile.TemporaryDirectory(prefix="memory-auditor-cli-")
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        self.cli = Path(ROOT) / "memory_auditor.py"

    def _invoke(self, input_path, output_path=None):
        command = [sys.executable, "-B", str(self.cli), str(input_path)]
        if output_path is not None:
            command += ["--json-out", str(output_path)]
        return subprocess.run(command, capture_output=True, text=True)

    def _input(self, name="input.md"):
        path = self.folder / name
        path.write_text("- 备份迁移问题已解决,马上关闭工单吧\n", encoding="utf-8")
        return path

    def _assert_alias_rejected(self, alias_kind):
        source = self._input(alias_kind + ".md")
        original = source.read_bytes()
        if alias_kind == "same-path":
            output = source
        elif alias_kind == "hard-link":
            output = self.folder / "hard-link.json"
            os.link(source, output)
        else:
            output = self.folder / "symbolic-link.json"
            output.symlink_to(source)

        result = self._invoke(source, output)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(source.read_bytes(), original)
        self.assertIn("错误:", result.stderr)

    def test_missing_input_exits_nonzero_without_clean_report(self):
        result = self._invoke(self.folder / "missing.md")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("共 0 条候选发现", result.stdout)

    def test_invalid_utf8_input_exits_nonzero_without_clean_report(self):
        source = self.folder / "invalid.md"
        source.write_bytes(b"\xff\n")
        result = self._invoke(source)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("共 0 条候选发现", result.stdout)

    def test_json_output_same_path_is_rejected_without_mutating_input(self):
        self._assert_alias_rejected("same-path")

    def test_json_output_hard_link_is_rejected_without_mutating_input(self):
        self._assert_alias_rejected("hard-link")

    def test_json_output_symbolic_link_is_rejected_without_mutating_input(self):
        self._assert_alias_rejected("symbolic-link")

    def test_json_output_aliasing_second_input_is_rejected(self):
        first = self._input("first.md")
        second = self._input("second.md")
        original = second.read_bytes()
        command = [
            sys.executable, "-B", str(self.cli), str(first), str(second),
            "--json-out", str(second),
        ]

        result = subprocess.run(command, capture_output=True, text=True)

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(second.read_bytes(), original)

    def test_existing_unrelated_output_is_not_replaced(self):
        source = self._input()
        output = self.folder / "existing.json"
        output.write_bytes(b"existing report must remain\n")

        result = self._invoke(source, output)

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(output.read_bytes(), b"existing report must remain\n")

    def test_report_uses_supplied_path_and_escapes_control_characters(self):
        source = self.folder / "nested-input.md"
        source.write_text("- 备份迁移问题已解决,马上关闭工单吧\x1b[31mINJECT\n", encoding="utf-8")

        result = self._invoke(source)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(str(source) + ":1", result.stdout)
        self.assertNotIn("\x1b", result.stdout)
        self.assertIn("\\u001b", result.stdout)

    def test_read_error_escapes_control_characters_in_path(self):
        result = self._invoke(self.folder / "missing\x1b[31m.md")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("\x1b", result.stderr)
        self.assertTrue("\\u001b" in result.stderr or "\\\\x1b" in result.stderr)

    def test_argument_error_escapes_control_characters(self):
        source = self._input()
        command = [sys.executable, "-B", str(self.cli), str(source), "--bad\x1b[31m"]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("\x1b", result.stderr)
        self.assertIn("\\u001b", result.stderr)

    def test_atomic_writer_does_not_publish_when_link_fails(self):
        output = self.folder / "report.json"
        with mock.patch.object(ma.os, "link", side_effect=OSError("synthetic link failure")):
            with self.assertRaises(OSError):
                ma.write_json_atomic(output, [{"issue": "synthetic"}])
        self.assertFalse(output.exists())
        self.assertEqual(list(self.folder.iterdir()), [])

    def test_atomic_writer_preserves_primary_error_when_cleanup_also_fails(self):
        output = self.folder / "report.json"
        primary = OSError("PRIMARY_LINK")
        with mock.patch.object(ma.os, "link", side_effect=primary), \
             mock.patch.object(ma.os, "unlink", side_effect=OSError("CLEANUP_UNLINK")):
            with self.assertRaises(RuntimeError) as caught:
                ma.write_json_atomic(output, [{"issue": "synthetic"}])
        self.assertIn("PRIMARY_LINK", str(caught.exception))
        self.assertIn("CLEANUP_UNLINK", str(caught.exception))
        self.assertIs(caught.exception.__cause__, primary)
        self.assertFalse(output.exists())

    def test_atomic_writer_reports_published_output_when_cleanup_fails(self):
        output = self.folder / "report.json"
        with mock.patch.object(ma.os, "unlink", side_effect=OSError("CLEANUP_UNLINK")):
            with self.assertRaisesRegex(RuntimeError, "已发布.*CLEANUP_UNLINK"):
                ma.write_json_atomic(output, [{"issue": "synthetic"}])
        self.assertEqual(json.loads(output.read_text(encoding="utf-8")), [{"issue": "synthetic"}])


if __name__ == "__main__":
    unittest.main()
