#!/usr/bin/env node

import { isUtf8 } from 'node:buffer';
import {
  closeSync,
  fsyncSync,
  linkSync,
  lstatSync,
  mkdtempSync,
  openSync,
  readFileSync,
  realpathSync,
  rmdirSync,
  statSync,
  unlinkSync,
  writeFileSync,
} from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';

const OVERCLAIM_PATTERNS = [
  /已达[ \t]*AGI/i, /接近[ \t]*AGI/i, /实现(了)?[ \t]*AGI/i, /通用人工智能水平/i,
  /AGI[- \t]?(级别|级|水平)?的?自主/i, /最强(的)?(模型|系统|方案)?/i,
  /碾压(所有|同行)?/i, /100%[ \t]*成功/i, /永不失败/i, /从不出错/i,
  /完全自动化(无需|零)人工/i, /绝无(意外|风险|失败)/i, /史无前例/i, /遥遥领先/i,
];
const EVIDENCE_HINTS = ['证据', 'receipt', 'evidence', '回执', '哈希', 'sha', '命令输出', '报错原文', '复现'];
const DONE_WITHOUT_EVIDENCE = /(已解决|已修复|已完成|搞定|闭环|全清|全部完成|全线通过)/;
const NEGATION = /(禁|不|勿|拒绝|永不|避免|不得|防)/;
const CONTROL_CHARACTERS = /[\u0000-\u001f\u007f-\u009f]/g;
const DEFAULT_FILE_OPERATIONS = {
  closeSync,
  fsyncSync,
  linkSync,
  mkdtempSync,
  openSync,
  rmdirSync,
  unlinkSync,
  writeFileSync,
};

function escapeTerminal(value) {
  const named = new Map([
    ['\b', '\\b'], ['\t', '\\t'], ['\n', '\\n'], ['\f', '\\f'], ['\r', '\\r'],
  ]);
  return String(value)
    .replaceAll('\\', '\\\\')
    .replace(CONTROL_CHARACTERS, (character) => (
      named.get(character) ?? `\\u${character.codePointAt(0).toString(16).padStart(4, '0')}`
    ));
}

function trimAscii(value) {
  return String(value).replace(/^[ \t]+|[ \t]+$/g, '');
}

function validateJsonOutput(output, inputFiles) {
  const entry = lstatSync(output, { throwIfNoEntry: false });
  if (entry === undefined) return;
  let outputStat;
  try {
    outputStat = statSync(output);
  } catch (error) {
    if (error.code === 'ENOENT') {
      throw new Error(`JSON 输出路径已存在且不可跟随,拒绝覆盖: ${output}`);
    }
    throw error;
  }
  for (const input of inputFiles) {
    const inputStat = statSync(input);
    if (outputStat.dev === inputStat.dev && outputStat.ino === inputStat.ino) {
      throw new Error(`JSON 输出不得与输入指向同一文件: ${output}`);
    }
  }
  throw new Error(`JSON 输出已存在,拒绝覆盖: ${output}`);
}

export function writeJsonAtomic(output, findings, overrides = {}) {
  const operations = { ...DEFAULT_FILE_OPERATIONS, ...overrides };
  const resolvedOutput = path.resolve(output);
  const temporaryDirectory = operations.mkdtempSync(
    path.join(path.dirname(resolvedOutput), '.memory-auditor-'),
  );
  const temporary = path.join(temporaryDirectory, 'report.json');
  let primaryError;
  try {
    const descriptor = operations.openSync(temporary, 'wx', 0o600);
    try {
      operations.writeFileSync(descriptor, `${JSON.stringify(findings, null, 2)}\n`, 'utf8');
      operations.fsyncSync(descriptor);
    } finally {
      operations.closeSync(descriptor);
    }
    operations.linkSync(temporary, resolvedOutput);
  } catch (error) {
    primaryError = error;
  }
  const cleanupErrors = [];
  try {
    operations.unlinkSync(temporary);
  } catch (error) {
    if (error.code !== 'ENOENT') cleanupErrors.push(error);
  }
  try {
    operations.rmdirSync(temporaryDirectory);
  } catch (error) {
    if (error.code !== 'ENOENT') cleanupErrors.push(error);
  }
  if (primaryError !== undefined) {
    if (cleanupErrors.length > 0) {
      throw new Error(
        `${primaryError.message}; 临时文件清理失败: ${cleanupErrors.map(({ message }) => message).join('; ')}`,
        { cause: primaryError },
      );
    }
    throw primaryError;
  }
  if (cleanupErrors.length > 0) {
    throw new Error(
      `JSON 报告已发布,但临时文件清理失败: ${cleanupErrors.map(({ message }) => message).join('; ')}`,
      { cause: cleanupErrors[0] },
    );
  }
}

function readLines(file) {
  const data = readFileSync(file);
  if (!isUtf8(data)) throw new Error(`输入不是有效 UTF-8: ${file}`);
  return data.toString('utf8').split(/\r?\n/);
}

export function auditMarkdown(file) {
  const lines = readLines(file);
  const findings = [];
  const seen = new Map();

  lines.forEach((line, index) => {
    const lineNumber = index + 1;
    const text = trimAscii(line);
    if (text.length < 12) return;

    let overclaimFound = false;
    for (const pattern of OVERCLAIM_PATTERNS) {
      const matcher = new RegExp(pattern.source, `${pattern.flags.replace('g', '')}g`);
      for (const match of text.matchAll(matcher)) {
        const before = text.slice(Math.max(0, match.index - 30), match.index);
        const after = text.slice(match.index + match[0].length, match.index + match[0].length + 30);
        if (NEGATION.test(before) || NEGATION.test(after)) continue;
        findings.push({
          file,
          line: lineNumber,
          issue: 'overclaim',
          excerpt: text.slice(0, 100),
          hint: `命中表述:${pattern.source.slice(0, 24)}…请核对是否可辩护,或改为分级表述`,
        });
        overclaimFound = true;
        break;
      }
      if (overclaimFound) break;
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
    const normalized = text.replace(/[ \t]+/g, '').slice(0, 60);
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
    if (!trimAscii(line)) return;
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
    if (record === null || typeof record !== 'object' || Array.isArray(record)) {
      findings.push({
        file,
        line: index + 1,
        issue: 'bad_json',
        excerpt: line.slice(0, 80),
        hint: 'JSON 顶层必须是对象',
      });
      return;
    }
    const evidence = record.evidence || record['证据'];
    if (!evidence || trimAscii(evidence).length < 20) {
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
  if (options.jsonOut) validateJsonOutput(options.jsonOut, options.files);
  const findings = [];
  for (const file of options.files) {
    const kind = options.kind === 'auto'
      ? (/\.jsonl?$/.test(file) ? 'jsonl' : 'md')
      : options.kind;
    findings.push(...(kind === 'jsonl' ? auditJsonl(file) : auditMarkdown(file)));
  }

  const counts = {};
  for (const { issue } of findings) {
    counts[issue] = (counts[issue] ?? 0) + 1;
  }
  console.log(`# 记忆审计报告 v0.1:共 ${findings.length} 条候选发现(候选≠判决,逐条复核)`);
  console.log(`按类型: ${JSON.stringify(counts)}`);
  for (const finding of findings) {
    console.log(`\n[${finding.issue}] ${escapeTerminal(finding.file)}:${finding.line}`);
    console.log(`  原文: ${escapeTerminal(finding.excerpt)}`);
    console.log(`  提示: ${escapeTerminal(finding.hint)}`);
  }
  if (options.jsonOut) {
    writeJsonAtomic(options.jsonOut, findings);
    console.log(`\nJSON 报告: ${escapeTerminal(options.jsonOut)}`);
  }
  return findings;
}

function isDirectInvocation() {
  if (!process.argv[1]) return false;
  try {
    return realpathSync(fileURLToPath(import.meta.url)) === realpathSync(process.argv[1]);
  } catch {
    // An importing caller's argv may name a non-file, such as node --eval input.
    return false;
  }
}

if (isDirectInvocation()) {
  try {
    run();
  } catch (error) {
    console.error(`错误: ${escapeTerminal(error.message)}`);
    process.exitCode = 1;
  }
}
