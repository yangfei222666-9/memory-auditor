#!/usr/bin/env node

import { readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { pathToFileURL } from 'node:url';

const OVERCLAIM_PATTERNS = [
  /已达\s*AGI/i, /接近\s*AGI/i, /实现(了)?\s*AGI/i, /通用人工智能水平/i,
  /AGI[-\s]?(级别|级|水平)?的?自主/i, /最强(的)?(模型|系统|方案)?/i,
  /碾压(所有|同行)?/i, /100%\s*成功/i, /永不失败/i, /从不出错/i,
  /完全自动化(无需|零)人工/i, /绝无(意外|风险|失败)/i, /史无前例/i, /遥遥领先/i,
];
const EVIDENCE_HINTS = ['证据', 'receipt', 'evidence', '回执', '哈希', 'sha', '命令输出', '报错原文', '复现'];
const DONE_WITHOUT_EVIDENCE = /(已解决|已修复|已完成|搞定|闭环|全清|全部完成|全线通过)/;
const NEGATION = /(禁|不|勿|拒绝|永不|避免|不得|防)/;

function readLines(file) {
  return readFileSync(file, 'utf8').split(/\r?\n/);
}

export function auditMarkdown(file) {
  const lines = readLines(file);
  const findings = [];
  const seen = new Map();

  lines.forEach((line, index) => {
    const lineNumber = index + 1;
    const text = line.trim();
    if (text.length < 12) return;

    for (const pattern of OVERCLAIM_PATTERNS) {
      const match = pattern.exec(text);
      if (!match) continue;
      const before = text.slice(Math.max(0, match.index - 30), match.index);
      const after = text.slice(match.index + match[0].length, match.index + match[0].length + 30);
      if (!NEGATION.test(before) && !NEGATION.test(after)) {
        findings.push({
          file,
          line: lineNumber,
          issue: 'overclaim',
          excerpt: text.slice(0, 100),
          hint: `命中表述:${pattern.source.slice(0, 24)}…请核对是否可辩护,或改为分级表述`,
        });
      }
      break;
    }

    if (DONE_WITHOUT_EVIDENCE.test(text)
      && !EVIDENCE_HINTS.some((hint) => text.includes(hint))
      && /^(?:[-*]|\d+\.)/.test(text)) {
      findings.push({
        file,
        line: lineNumber,
        issue: 'done_without_evidence',
        excerpt: text.slice(0, 100),
        hint: '完成类声明未附证据词(证据/receipt/哈希…);若为规则文本可忽略',
      });
    }

    if (text.startsWith('|')) return;
    const normalized = text.replace(/\s+/g, '').slice(0, 60);
    if (seen.has(normalized)) {
      findings.push({
        file,
        line: lineNumber,
        issue: 'duplicate',
        excerpt: text.slice(0, 100),
        hint: `与第 ${seen.get(normalized)} 行近似重复`,
      });
    } else {
      seen.set(normalized, lineNumber);
    }
  });
  return findings;
}

export function auditJsonl(file) {
  const findings = [];
  readLines(file).forEach((line, index) => {
    if (!line.trim()) return;
    let record;
    try {
      record = JSON.parse(line);
    } catch {
      findings.push({
        file,
        line: index + 1,
        issue: 'bad_json',
        excerpt: line.slice(0, 80),
        hint: '非 JSON 行',
      });
      return;
    }
    const evidence = record.evidence || record['证据'];
    if (!evidence || String(evidence).trim().length < 20) {
      findings.push({
        file,
        line: index + 1,
        issue: 'no_evidence',
        excerpt: String(record.claim || record.id || '').slice(0, 80),
        hint: '教训缺 evidence 或证据 <20 字符(无证据不写教训)',
      });
    }
  });
  return findings;
}

function parseArgs(argv) {
  const options = { files: [], kind: 'auto', jsonOut: null };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === '--kind') options.kind = argv[++index];
    else if (arg === '--json-out') options.jsonOut = argv[++index];
    else if (arg.startsWith('--')) throw new Error(`未知选项: ${arg}`);
    else options.files.push(arg);
  }
  if (!['auto', 'md', 'jsonl'].includes(options.kind)) throw new Error('--kind 必须是 auto、md 或 jsonl');
  if (options.files.length === 0) throw new Error('至少提供一个待审计文件');
  return options;
}

export function run(argv = process.argv.slice(2)) {
  const options = parseArgs(argv);
  const findings = [];
  for (const file of options.files) {
    const kind = options.kind === 'auto'
      ? (/\.jsonl?$/.test(file) ? 'jsonl' : 'md')
      : options.kind;
    findings.push(...(kind === 'jsonl' ? auditJsonl(file) : auditMarkdown(file)));
  }

  const counts = Object.fromEntries(
    [...new Set(findings.map(({ issue }) => issue))]
      .map((issue) => [issue, findings.filter((item) => item.issue === issue).length]),
  );
  console.log(`# 记忆审计报告 v0.1:共 ${findings.length} 条候选发现(候选≠判决,逐条复核)`);
  console.log(`按类型: ${JSON.stringify(counts)}`);
  for (const finding of findings) {
    console.log(`\n[${finding.issue}] ${path.basename(finding.file)}:${finding.line}`);
    console.log(`  原文: ${finding.excerpt}`);
    console.log(`  提示: ${finding.hint}`);
  }
  if (options.jsonOut) {
    writeFileSync(options.jsonOut, `${JSON.stringify(findings, null, 2)}\n`, 'utf8');
    console.log(`\nJSON 报告: ${options.jsonOut}`);
  }
  return findings;
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    run();
  } catch (error) {
    console.error(`错误: ${error.message}`);
    process.exitCode = 1;
  }
}
