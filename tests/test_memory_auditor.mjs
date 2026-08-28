import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { link, mkdtemp, readFile, rm, symlink, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

import * as auditor from '../memory-auditor.mjs';

const { auditJsonl, auditMarkdown } = auditor;

const NODE_CLI = fileURLToPath(new URL('../memory-auditor.mjs', import.meta.url));
const PYTHON_CLI = fileURLToPath(new URL('../memory_auditor.py', import.meta.url));
const IMPLEMENTATIONS = [
  { name: 'node', command: process.execPath, prefix: [NODE_CLI] },
  { name: 'python', command: process.env.PYTHON || 'python3', prefix: ['-B', PYTHON_CLI] },
];

function invoke(implementation, args) {
  return spawnSync(implementation.command, [...implementation.prefix, ...args], {
    encoding: 'utf8',
  });
}

async function withDirectory(t) {
  const dir = await mkdtemp(path.join(tmpdir(), 'memory-auditor-contract-'));
  t.after(() => rm(dir, { recursive: true, force: true }));
  return dir;
}

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

test('continues after a negated match to a later overclaim pattern', async (t) => {
  const text = '- 禁止宣称已达 AGI；这是用于隔开否定窗口的中性说明文字一二三四五六七八九十甲乙丙丁戊己庚辛壬癸。我们的模型最强。\n';
  const file = await withFile(t, 'md', text);
  assert.deepEqual(auditMarkdown(file).map(({ issue }) => issue), ['overclaim']);
});

test('continues after a negated match to the same later overclaim pattern', async (t) => {
  const text = '- 禁止使用最强这种表述；中性说明一二三四五六七八九十甲乙丙丁戊己庚辛壬癸。我们的模型最强。\n';
  const file = await withFile(t, 'md', text);
  assert.deepEqual(auditMarkdown(file).map(({ issue }) => issue), ['overclaim']);
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

test('flags non-object JSON records without crashing', async (t) => {
  const file = await withFile(t, 'jsonl', 'null\n[]\n42\n"text"\n');
  const findings = auditJsonl(file);
  assert.deepEqual(findings.map(({ issue }) => issue), Array(4).fill('bad_json'));
});

test('differential contract keeps Python and Node findings identical', async (t) => {
  const dir = await withDirectory(t);
  const fixtures = [
    {
      name: 'records.jsonl',
      kind: 'jsonl',
      content: 'null\n[]\n{"id":"missing"}\n{"id":"ok","evidence":"复现步骤与命令输出均已记录在公开测试工件中"}\n',
    },
    {
      name: 'claims.md',
      kind: 'md',
      content: '- 禁止宣称已达 AGI；这是用于隔开否定窗口的中性说明文字一二三四五六七八九十甲乙丙丁戊己庚辛壬癸。我们的模型最强。\n',
    },
    {
      name: 'nel.jsonl',
      kind: 'jsonl',
      content: '{"id":"a"}\u0085{"id":"b"}\n',
    },
    {
      name: 'nel-only.jsonl',
      kind: 'jsonl',
      content: '\u0085\n',
    },
    {
      name: 'nel-edges.md',
      kind: 'md',
      content: '\u0085- 备份迁移问题已解决,马上关闭工单吧\u0085\n',
    },
    {
      name: 'nel-spacing.md',
      kind: 'md',
      content: '我们的系统已达\u0085AGI 水平,自主运行一切任务。\n',
    },
  ];

  for (const fixture of fixtures) {
    const input = path.join(dir, fixture.name);
    await writeFile(input, fixture.content, 'utf8');
    const reports = [];
    for (const implementation of IMPLEMENTATIONS) {
      const output = path.join(dir, `${implementation.name}-${fixture.name}.json`);
      const result = invoke(implementation, ['--kind', fixture.kind, input, '--json-out', output]);
      assert.equal(result.status, 0, `${implementation.name}: ${result.stderr}`);
      reports.push(JSON.parse(await readFile(output, 'utf8')));
    }
    assert.deepEqual(reports[0], reports[1], fixture.name);
  }
});

test('both CLIs fail closed when any input cannot be read', async (t) => {
  const dir = await withDirectory(t);
  const valid = path.join(dir, 'valid.md');
  const missing = path.join(dir, 'missing\u001b[31m.md');
  await writeFile(valid, '- 普通且足够长的有效输入文本用于读取顺序测试。\n', 'utf8');
  for (const implementation of IMPLEMENTATIONS) {
    const result = invoke(implementation, [valid, missing]);
    assert.notEqual(result.status, 0, implementation.name);
    assert.doesNotMatch(result.stdout, /共 0 条候选发现/, implementation.name);
    assert.doesNotMatch(result.stderr, /\u001b/, implementation.name);
    assert.match(result.stderr, /(?:\\u001b|\\\\x1b)/, implementation.name);
  }
});

test('both CLIs fail closed on invalid UTF-8', async (t) => {
  const dir = await withDirectory(t);
  const invalid = path.join(dir, 'invalid.md');
  await writeFile(invalid, Buffer.from([0xff, 0x0a]));
  for (const implementation of IMPLEMENTATIONS) {
    const result = invoke(implementation, [invalid]);
    assert.notEqual(result.status, 0, implementation.name);
    assert.doesNotMatch(result.stdout, /共 0 条候选发现/, implementation.name);
  }
});

test('both CLIs escape control characters in argument errors', async (t) => {
  const dir = await withDirectory(t);
  const input = path.join(dir, 'input.md');
  await writeFile(input, '- 普通且足够长的有效输入文本用于参数测试。\n', 'utf8');
  for (const implementation of IMPLEMENTATIONS) {
    const result = invoke(implementation, [input, '--bad\u001b[31m']);
    assert.notEqual(result.status, 0, implementation.name);
    assert.doesNotMatch(result.stderr, /\u001b/, implementation.name);
    assert.match(result.stderr, /\\u001b/, implementation.name);
  }
});

test('both CLI reports keep the supplied path and escape control characters', async (t) => {
  const dir = await withDirectory(t);
  const input = path.join(dir, 'nested-input.md');
  await writeFile(input, '- 备份迁移问题已解决,马上关闭工单吧\u001b[31mINJECT\n', 'utf8');
  for (const implementation of IMPLEMENTATIONS) {
    const result = invoke(implementation, [input]);
    assert.equal(result.status, 0, `${implementation.name}: ${result.stderr}`);
    assert.ok(result.stdout.includes(`${input}:1`), implementation.name);
    assert.doesNotMatch(result.stdout, /\u001b/, implementation.name);
    assert.match(result.stdout, /\\u001b/, implementation.name);
  }
});

test('Node rejects same-path, hard-link, symbolic-link, and existing outputs', async (t) => {
  const dir = await withDirectory(t);
  const node = IMPLEMENTATIONS[0];
  const cases = ['same-path', 'hard-link', 'symbolic-link', 'existing'];

  for (const kind of cases) {
    const input = path.join(dir, `${kind}.md`);
    const original = '- 备份迁移问题已解决,马上关闭工单吧\n';
    await writeFile(input, original, 'utf8');
    let output = path.join(dir, `${kind}.json`);
    if (kind === 'same-path') output = input;
    else if (kind === 'hard-link') await link(input, output);
    else if (kind === 'symbolic-link') await symlink(input, output);
    else await writeFile(output, 'existing report must remain\n', 'utf8');

    const result = invoke(node, [input, '--json-out', output]);

    assert.notEqual(result.status, 0, kind);
    assert.equal(await readFile(input, 'utf8'), original, kind);
    if (kind === 'existing') {
      assert.equal(await readFile(output, 'utf8'), 'existing report must remain\n');
    }
  }
});

test('both CLIs reject JSON output aliasing the second input', async (t) => {
  const dir = await withDirectory(t);
  for (const implementation of IMPLEMENTATIONS) {
    const first = path.join(dir, `${implementation.name}-first.md`);
    const second = path.join(dir, `${implementation.name}-second.md`);
    const original = '- 备份迁移问题已解决,马上关闭工单吧\n';
    await writeFile(first, original, 'utf8');
    await writeFile(second, original, 'utf8');

    const result = invoke(implementation, [first, second, '--json-out', second]);

    assert.notEqual(result.status, 0, implementation.name);
    assert.equal(await readFile(second, 'utf8'), original, implementation.name);
  }
});

test('Node atomic writer preserves the primary error when cleanup also fails', async (t) => {
  const dir = await withDirectory(t);
  const output = path.join(dir, 'report.json');
  let caught;
  try {
    auditor.writeJsonAtomic(output, [{ issue: 'synthetic' }], {
      linkSync() { throw new Error('PRIMARY_LINK'); },
      unlinkSync() { throw new Error('CLEANUP_UNLINK'); },
      rmdirSync() { throw new Error('CLEANUP_RMDIR'); },
    });
  } catch (error) {
    caught = error;
  }
  assert.ok(caught);
  assert.match(caught.message, /PRIMARY_LINK/);
  assert.match(caught.message, /CLEANUP_UNLINK/);
  assert.match(caught.message, /CLEANUP_RMDIR/);
  assert.equal(caught.cause?.message, 'PRIMARY_LINK');
});

test('Node atomic writer reports when output was published but cleanup failed', async (t) => {
  const dir = await withDirectory(t);
  const output = path.join(dir, 'report.json');
  assert.throws(() => auditor.writeJsonAtomic(output, [{ issue: 'synthetic' }], {
    unlinkSync() { throw new Error('CLEANUP_UNLINK'); },
    rmdirSync() { throw new Error('CLEANUP_RMDIR'); },
  }), /已发布.*CLEANUP_UNLINK.*CLEANUP_RMDIR/);
  assert.deepEqual(JSON.parse(await readFile(output, 'utf8')), [{ issue: 'synthetic' }]);
});

test('bundled sample has ten synthetic records and four review candidates', async () => {
  const sample = new URL('../examples/sample-ledger.jsonl', import.meta.url);
  const lines = readFileSync(sample, 'utf8').trim().split('\n');
  assert.equal(lines.length, 10);
  assert.ok(lines.every((line) => JSON.parse(line).sample === true));
  assert.equal(auditJsonl(sample).length, 4);
});
