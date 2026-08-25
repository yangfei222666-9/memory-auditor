import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import test from 'node:test';

import { auditJsonl, auditMarkdown } from '../memory-auditor.mjs';

async function withFile(t, suffix, content) {
  const dir = await mkdtemp(path.join(tmpdir(), 'memory-auditor-test-'));
  t.after(() => rm(dir, { recursive: true, force: true }));
  const file = path.join(dir, `input.${suffix}`);
  await writeFile(file, content, 'utf8');
  return file;
}

test('detects an overclaim', async (t) => {
  const file = await withFile(t, 'md', '我们的系统已达 AGI 水平,自主运行一切任务。\n');
  const findings = await auditMarkdown(file);
  assert.equal(findings.length, 1);
  assert.equal(findings[0].issue, 'overclaim');
  assert.equal(findings[0].line, 1);
});

test('exempts negated overclaims', async (t) => {
  const file = await withFile(t, 'md', '纪律:禁用已达 AGI 之类的表述,永不宣称最强。\n');
  assert.deepEqual(await auditMarkdown(file), []);
});

test('detects list-item completion without evidence', async (t) => {
  const file = await withFile(t, 'md', '- 备份迁移问题已解决,不用再看了\n');
  const findings = await auditMarkdown(file);
  assert.deepEqual(findings.map(({ issue }) => issue), ['done_without_evidence']);
});

test('accepts completion with evidence', async (t) => {
  const file = await withFile(t, 'md', '- 备份迁移问题已解决,receipt 已入账,哈希可查\n');
  assert.deepEqual(await auditMarkdown(file), []);
});

test('detects duplicate clauses', async (t) => {
  const file = await withFile(t, 'md', '- 每天 08:00 巡检备份状态\n- 每天 08:00 巡检备份状态\n');
  const findings = await auditMarkdown(file);
  assert.equal(findings[0].issue, 'duplicate');
  assert.equal(findings[0].line, 2);
});

test('detects missing, short, and malformed JSONL evidence', async (t) => {
  const file = await withFile(t, 'jsonl', [
    JSON.stringify({ id: 'L1', claim: '无证据教训' }),
    JSON.stringify({ id: 'L2', evidence: '短' }),
    'not-json',
    JSON.stringify({ id: 'L3', evidence: '复现步骤与命令输出均已记录在公开测试工件中' }),
  ].join('\n'));
  const findings = await auditJsonl(file);
  assert.deepEqual(findings.map(({ issue }) => issue), ['no_evidence', 'no_evidence', 'bad_json']);
});

test('bundled sample has ten synthetic records and four review candidates', async () => {
  const sample = new URL('../examples/sample-ledger.jsonl', import.meta.url);
  const lines = readFileSync(sample, 'utf8').trim().split('\n');
  assert.equal(lines.length, 10);
  assert.ok(lines.every((line) => JSON.parse(line).sample === true));
  assert.equal(auditJsonl(sample).length, 4);
});
