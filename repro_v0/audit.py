#!/usr/bin/env python3
"""Pinned-source, stdlib-only candidate audit; never a semantic verdict.

This wrapper does not change the pinned detector or the worktree detector.
It only accepts the two hash-locked synthetic Markdown fixtures.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent


class InvalidInput(Exception):
    pass


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise InvalidInput(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def manifest_check(root=ROOT):
    raw = (root / 'MANIFEST.json').read_bytes()
    manifest = json.loads(raw)
    expected = manifest['files']
    paths = list(root.rglob('*'))
    if any(path.is_symlink() for path in paths):
        raise InvalidInput('package symlinks are forbidden')
    actual = sorted(str(p.relative_to(root)) for p in paths if p.is_file() and p.relative_to(root).as_posix() != 'MANIFEST.json')
    if actual != sorted(expected):
        raise InvalidInput('package file set differs from manifest')
    for name, value in expected.items():
        path = root / name
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()) or digest(path.read_bytes()) != value:
            raise InvalidInput('package file hash mismatch: ' + name)
    return digest(raw)


def atomic_json(path, value):
    """Publish a complete new report without ever replacing an earlier report."""
    data = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=str(path.parent), prefix='.repro-', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(str(temporary), str(path))
    finally:
        if temporary is not None:
            temporary.unlink()


def network_guard():
    blocked = []

    def guard(name, args):
        if name.startswith('socket.') or name in ('subprocess.Popen', 'os.system', 'os.posix_spawn', 'os.exec', 'pty.spawn'):
            blocked.append(name)
            raise RuntimeError('network/process attempt forbidden during audit')

    sys.addaudithook(guard)
    return blocked


def run_one(engine, fixture, output):
    package_hash = manifest_check()
    pin = json.loads((ROOT / 'pinned.json').read_text(encoding='utf-8'))
    expected = pin['fixtures'].get(fixture.name)
    if expected is None or fixture.is_symlink() or not fixture.is_file():
        raise InvalidInput('only the two declared fixture files are accepted')
    raw = fixture.read_bytes()
    if digest(raw) != expected['sha256']:
        raise InvalidInput('fixture hash mismatch')
    try:
        lines = raw.decode('utf-8').splitlines()
    except UnicodeDecodeError:
        raise InvalidInput('fixture is not UTF-8')
    if len(lines) != 10 or any(not line.startswith('- ') for line in lines):
        raise InvalidInput('fixture must contain ten Markdown list records')
    if engine.is_symlink() or not engine.is_file():
        raise InvalidInput('pinned detector missing or hash mismatch')
    engine_bytes = engine.read_bytes()
    if digest(engine_bytes) != pin['engine_sha256']:
        raise InvalidInput('pinned detector hash mismatch')
    output = output.resolve()
    if not output.is_relative_to(Path(tempfile.gettempdir()).resolve()):
        raise InvalidInput('report must stay under the system temporary directory')
    if not output.parent.is_dir():
        raise InvalidInput('report parent directory does not exist')
    if output.exists():
        raise FileExistsError('report already exists; use a new run directory')
    namespace = {'__name__': 'memory_auditor_pinned', '__file__': str(engine)}
    exec(compile(engine_bytes, str(engine), 'exec'), namespace)
    findings = namespace['audit_markdown'](str(fixture))
    # The detector historically swallows read failures. Inputs were prevalidated;
    # recheck bytes after the call and fail closed on any mutation.
    if digest(fixture.read_bytes()) != expected['sha256']:
        raise InvalidInput('fixture changed while scanning')
    for finding in findings:
        finding['file'] = 'fixtures/' + fixture.name
    observed = [[finding['line'], finding['issue']] for finding in findings]
    if observed != expected['findings']:
        raise RuntimeError('pinned fixture finding contract mismatch')
    code = 2 if findings else 0
    report = {
        'candidate_not_verdict': True,
        'auditor_commit_sha': pin['auditor_commit_sha'],
        'package_manifest_sha256': package_hash,
        'fixture_sha256': expected['sha256'],
        'finding_count': len(findings),
        'findings': findings,
        'exit_code': code,
        'runtime_dependencies': 'stdlib_only',
    }
    atomic_json(output, report)
    print('candidate, not verdict / 候选，不是判决')
    for finding in findings:
        print('{file}:{line} [{issue}] {excerpt}'.format(**finding))
    print(json.dumps({'finding_count': len(findings), 'exit_code': code, 'report_sha256': digest(output.read_bytes())}))
    return code


def main(argv=None):
    try:
        parser = Parser(description=__doc__)
        parser.add_argument('--engine', type=Path, required=True)
        parser.add_argument('--fixture', type=Path, required=True)
        parser.add_argument('--output', type=Path, required=True)
        args = parser.parse_args(argv)
        network_guard()
        return run_one(args.engine, args.fixture, args.output)
    except (InvalidInput, UnicodeError, json.JSONDecodeError) as error:
        print('INVALID_INPUT: ' + str(error), file=sys.stderr)
        return 3
    except Exception as error:
        print('EXECUTION_ERROR: ' + type(error).__name__, file=sys.stderr)
        return 4


if __name__ == '__main__':
    sys.exit(main())
