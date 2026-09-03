#!/usr/bin/env python3
"""Human-run receipt collector. Codex must not run this as an owner cold run."""
import time
START_MONOTONIC = time.monotonic()
START_WALL = time.time()
import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import uuid

sys.dont_write_bytecode = True
from audit import ROOT, InvalidInput, Parser, atomic_json, digest, manifest_check


LOCAL_PUBLICATION_GATE = 'BLOCKED_PUBLIC_PACKAGE_COMMIT_ROOT_LICENSE_ARCHIVE_URL_CI_AND_DUAL_HUMAN_ACCEPTANCE'
FORMAL_PUBLICATION_GATE = 'BLOCKED_PUBLIC_ARCHIVE_URL_CONTENT_HASH_CI_AND_DUAL_HUMAN_ACCEPTANCE'


def utc(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat()


def answer(prompt):
    value = input(prompt + ' [yes/no/unknown]: ').strip().lower()
    return value if value in ('yes', 'no') else 'unknown'


def parse_nul_ls_tree(raw):
    """Parse `git ls-tree -z` output without losing unusual path separators."""
    if raw and not raw.endswith(b'\0'):
        raise InvalidInput('Git tree output is not NUL terminated')
    entries = []
    for record in raw.split(b'\0')[:-1]:
        try:
            metadata, path = record.split(b'\t', 1)
            mode, object_type, object_sha = metadata.decode('ascii').split()
            path_text = path.decode('utf-8')
        except (ValueError, UnicodeDecodeError):
            raise InvalidInput('Git tree output is malformed')
        if re.fullmatch(r'[0-9a-f]{40,64}', object_sha) is None:
            raise InvalidInput('Git tree object id is malformed')
        entries.append((mode, object_type, object_sha, path_text))
    return entries


def main(argv=None):
    work = None
    receipt = {
        'run_id': str(uuid.uuid4()), 'tester_role': 'unknown',
        'prior_project_exposure': 'unknown', 'first_clone': 'unknown',
        'prior_repo_or_environment_or_cache': 'unknown',
        'started_at': utc(START_WALL), 'ended_at': None,
        'elapsed_seconds': None, 'program_elapsed_seconds': None, 'external_stopwatch_seconds': None,
        'timer_method': 'monotonic from collector entry; external stopwatch starts before archive integrity preflight and includes verification/extraction/README/collector after artifact acquisition',
        'timer_scope': 'post_acquisition_verification_and_execution; artifact download or transfer excluded',
        'os_arch': platform.system() + ' ' + platform.release() + ' ' + platform.machine(),
        'python_version': platform.python_version(), 'git_version': None,
        'public_repo': None, 'public_ref': None, 'public_head_at_start': None,
        'clone_tracking_head': None, 'commit_sha': None,
        'package_commit_input_sha': None,
        'package_commit_sha': None, 'package_version_verified': False,
        'public_package_file_modes_verified': False,
        'public_package_root_license_sha256': None,
        'public_source_repo_license_aligned': None,
        'cold_run_mode': 'rehearsal', 'repo_tree_clean': None,
        'package_manifest_sha256': None, 'readme_sha256': {}, 'fixture_sha256': {},
        'package_license': 'MIT; Copyright (c) 2026 yangfei222666-9',
        'source_repo_license': 'MIT text at fixed detector commit; historical placeholder notice hash is recorded separately',
        'source_repo_license_sha256': None, 'package_license_sha256': None,
        'embedded_package_commit_sha': None,
        'publication_state_at_build': None,
        'publication_status_authority': None,
        'publication_preconditions': [],
        'publication_gate_current': LOCAL_PUBLICATION_GATE,
        'blocker_codes': [],
        'fixture_license': 'MIT', 'third_party_materials': [],
        'bundled_source_materials': [], 'candidate_revision': None,
        'runtime_dependencies': None, 'external_tools': [], 'commands': [],
        'expected_exit_codes': {'problem': 2, 'clean': 0, 'collector_success': 2},
        'actual_exit_codes': {}, 'stdout_sha256': {}, 'stderr_sha256': {},
        'output_path': 'results/', 'report_sha256': {}, 'finding_count': {},
        'secret_scan': 'hash-locked synthetic fixtures only; no private memory or secret paths are opened',
        'network_observed': {'clone_phase': 'not observed yet', 'runtime_offline_tester_confirmation': 'unknown',
                             'audit_process_guard': 'Python socket/process audit hook; not OS isolation or packet capture'},
        'author_help': 'unknown', 'readme_only_completion': 'unknown',
        'independent_eligibility': None, 'independence_failures': [],
        'verdict': 'PENDING', 'blocker': [], 'contract_checks': False,
    }
    result = 4
    commands = receipt['commands']
    env = {'PATH': str(Path(sys.executable).parent) + os.pathsep + os.defpath,
           'LANG': 'C', 'LC_ALL': 'C', 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8',
           'PYTHONDONTWRITEBYTECODE': '1',
           'GIT_TERMINAL_PROMPT': '0', 'GIT_CONFIG_NOSYSTEM': '1',
           'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_CONFIG_SYSTEM': os.devnull,
           'GIT_OPTIONAL_LOCKS': '0', 'GIT_ALLOW_PROTOCOL': 'https'}
    results = None

    def execute(label, command, expected=(0,)):
        entry = {'label': label, 'command': command, 'cwd': '.', 'expected': list(expected),
                 'actual': None, 'execution_state': 'not_started', 'error': None}
        commands.append(entry)
        receipt['actual_exit_codes'][label] = None
        remaining = 600 - (time.monotonic() - START_MONOTONIC)
        if remaining <= 0:
            entry['error'] = 'time budget exhausted before process creation'
            raise RuntimeError('ten-minute budget exhausted before ' + label)
        failure = None
        try:
            entry['execution_state'] = 'attempted'
            completed = subprocess.run(command, cwd=str(work), env=env, capture_output=True, timeout=remaining)
            code, stdout, stderr = completed.returncode, completed.stdout, completed.stderr
            entry['execution_state'] = 'exited'
        except subprocess.TimeoutExpired as error:
            code, stdout, stderr = None, error.stdout or b'', error.stderr or b''
            failure = 'TimeoutExpired'
            entry['execution_state'] = 'timed_out'
        except (Exception, KeyboardInterrupt) as error:
            code, stdout, stderr = None, b'', b''
            failure = type(error).__name__ + ': ' + str(error)
            entry['execution_state'] = 'failed_or_interrupted'
        entry['actual'] = code
        entry['error'] = failure
        receipt['actual_exit_codes'][label] = code
        receipt['stdout_sha256'][label] = digest(stdout)
        receipt['stderr_sha256'][label] = digest(stderr)
        (results / (label + '.stdout')).write_bytes(stdout)
        (results / (label + '.stderr')).write_bytes(stderr)
        if failure is not None:
            raise RuntimeError('process failed at ' + label + ': ' + failure)
        if code not in expected:
            raise RuntimeError('unexpected exit at ' + label + ': ' + str(code))
        return stdout.decode('utf-8', errors='replace').strip()

    git = ['git', '-c', 'credential.helper=', '-c', 'core.hooksPath=' + os.devnull, '-c', 'core.autocrlf=false']
    try:
        work = Path(tempfile.mkdtemp(prefix='memory-auditor-repro-v0-')).resolve()
        results = work / 'results'
        results.mkdir(mode=0o700)
        env['TMPDIR'] = str(work.parent)
        parser = Parser(description=__doc__)
        parser.add_argument('--tester-role', choices=('owner', 'independent'), required=True)
        parser.add_argument('--package-commit', help='external public package commit, full 40-character SHA')
        args = parser.parse_args(argv)
        receipt['tester_role'] = args.tester_role
        if sys.version_info < (3, 9):
            raise InvalidInput('Python 3.9+ required')
        receipt['package_manifest_sha256'] = manifest_check()
        pin = json.loads((ROOT / 'pinned.json').read_text(encoding='utf-8'))
        receipt['candidate_revision'] = pin['candidate_revision']
        receipt['runtime_dependencies'] = pin['runtime_dependencies']
        receipt['external_tools'] = pin['external_tools']
        receipt['bundled_source_materials'] = pin['bundled_source_materials']
        receipt['third_party_materials'] = pin['third_party_materials']
        receipt['source_repo_license_sha256'] = pin['source_repo_license_sha256']
        receipt['package_license_sha256'] = pin['package_license_sha256']
        receipt['embedded_package_commit_sha'] = pin['embedded_package_commit_sha']
        receipt['publication_state_at_build'] = pin['package_state_at_build']
        receipt['publication_status_authority'] = pin['publication_status_authority']
        receipt['publication_preconditions'] = pin['publication_preconditions']
        receipt['public_repo'] = pin['public_repo']
        receipt['public_ref'] = pin['public_ref']
        receipt['commit_sha'] = pin['auditor_commit_sha']
        receipt['package_commit_input_sha'] = args.package_commit
        if digest((ROOT / 'LICENSE').read_bytes()) != pin['package_license_sha256']:
            raise InvalidInput('package LICENSE hash mismatch against pinned package license')
        if args.package_commit is not None and re.fullmatch(r'[0-9a-f]{40}', args.package_commit) is None:
            raise InvalidInput('package commit must be a full lowercase 40-character SHA')
        receipt['fixture_sha256'] = {name: item['sha256'] for name, item in pin['fixtures'].items()}
        receipt['readme_sha256'] = {name: digest((ROOT / name).read_bytes()) for name in ('README.md', 'README.en.md')}
        receipt['locked_file_sha256'] = digest((ROOT / 'pinned.json').read_bytes())
        if args.tester_role == 'independent' and args.package_commit is None:
            raise InvalidInput('independent acceptance requires a published, separately pinned package; local candidate is not eligible')
        receipt['prior_project_exposure'] = answer('Have you previously used or helped build this project?')
        receipt['first_clone'] = answer('Is this your first clone of this repository on this machine?')
        receipt['prior_repo_or_environment_or_cache'] = answer('Did any prior repo, virtual environment or package cache exist already?')
        receipt['author_help'] = answer('Did the author give help beyond this README, including a successful demo recording?')
        receipt['readme_only_completion'] = answer('Are you following only the supplied README?')
        if args.tester_role == 'independent':
            required_answers = {
                'prior_project_exposure': 'no',
                'first_clone': 'yes',
                'prior_repo_or_environment_or_cache': 'no',
                'author_help': 'no',
                'readme_only_completion': 'yes',
            }
            receipt['independence_failures'] = [
                name + '=' + str(receipt[name]) + ',required=' + expected
                for name, expected in required_answers.items()
                if receipt[name] != expected
            ]
            receipt['independent_eligibility'] = not receipt['independence_failures']
            if not receipt['independent_eligibility']:
                raise InvalidInput('independent eligibility failed: ' + '; '.join(receipt['independence_failures']))
        else:
            receipt['independent_eligibility'] = 'not_applicable_owner_role'
        shutil.copytree(str(ROOT), str(work / 'package'))
        receipt['git_version'] = execute('git-version', ['git', '--version'])
        public_ref = pin['public_ref']
        remote = execute('public-head', git + ['ls-remote', pin['public_repo'], public_ref])
        tokens = remote.split()
        if len(tokens) != 2 or len(tokens[0]) != 40 or tokens[1] != public_ref:
            raise RuntimeError('public HEAD response malformed')
        receipt['public_head_at_start'] = tokens[0]
        execute('clone', git + ['clone', '--no-checkout', pin['public_repo'], 'auditor-source'])
        # Full clone above: no partial-clone/lazy fetch at checkout.
        receipt['network_observed']['clone_phase'] = 'GitHub HTTPS commands completed; actual network destinations were not packet-captured'
        receipt['clone_tracking_head'] = execute(
            'clone-tracking-head',
            git + ['-C', 'auditor-source', 'rev-parse', public_ref.replace('refs/heads/', 'refs/remotes/origin/', 1)],
        )
        if receipt['clone_tracking_head'] != receipt['public_head_at_start']:
            raise InvalidInput('public ref changed between ls-remote and clone; rerun from a fresh package')
        offline = answer('Clone finished. Disconnect ALL network interfaces now. Are they disconnected?')
        receipt['network_observed']['runtime_offline_tester_confirmation'] = offline
        if offline != 'yes':
            raise InvalidInput('runtime requires explicit offline confirmation; no audit commands run')
        if args.package_commit is not None:
            object_type = execute(
                'public-package-object-type',
                git + ['-C', 'auditor-source', 'cat-file', '-t', args.package_commit],
            )
            if object_type != 'commit':
                raise InvalidInput('package SHA must identify a commit object')
            reachability_label = 'public-package-commit-reachable'
            execute(
                reachability_label,
                git + ['-C', 'auditor-source', 'merge-base', '--is-ancestor',
                       args.package_commit, receipt['public_head_at_start']],
                (0, 1),
            )
            if receipt['actual_exit_codes'][reachability_label] != 0:
                raise InvalidInput('package commit is not reachable from declared public ref ' + public_ref)
            execute(
                'public-root-license-entry',
                git + ['-C', 'auditor-source', 'ls-tree', '-z', args.package_commit, '--', 'LICENSE'],
            )
            license_entries = parse_nul_ls_tree((results / 'public-root-license-entry.stdout').read_bytes())
            if len(license_entries) != 1 or license_entries[0][0:2] != ('100644', 'blob') or license_entries[0][3] != 'LICENSE':
                receipt['public_source_repo_license_aligned'] = False
                raise InvalidInput('public package commit root LICENSE is missing or not a regular 100644 blob')
            execute('public-root-license', git + ['-C', 'auditor-source', 'show', args.package_commit + ':LICENSE'])
            receipt['public_package_root_license_sha256'] = digest((results / 'public-root-license.stdout').read_bytes())
            if receipt['public_package_root_license_sha256'] != pin['package_license_sha256']:
                receipt['public_source_repo_license_aligned'] = False
                raise InvalidInput('public package commit root LICENSE differs from supplied package LICENSE')
            receipt['public_source_repo_license_aligned'] = True
            execute(
                'public-package-file-set',
                git + ['-C', 'auditor-source', 'ls-tree', '-r', '-z', args.package_commit, '--', 'repro_v0'],
            )
            tree_entries = parse_nul_ls_tree((results / 'public-package-file-set.stdout').read_bytes())
            manifest = json.loads((ROOT / 'MANIFEST.json').read_text(encoding='utf-8'))
            expected_files = {'repro_v0/' + name for name in manifest['files']} | {'repro_v0/MANIFEST.json'}
            observed_files = [entry[3] for entry in tree_entries]
            if len(observed_files) != len(set(observed_files)) or set(observed_files) != expected_files:
                raise InvalidInput('public package file set differs from supplied local package')
            if any(mode != '100644' or object_type != 'blob' for mode, object_type, _, _ in tree_entries):
                raise InvalidInput('public package contains a non-regular or non-100644 file')
            receipt['public_package_file_modes_verified'] = True
            execute('public-package-manifest', git + ['-C', 'auditor-source', 'show', args.package_commit + ':repro_v0/MANIFEST.json'])
            if digest((results / 'public-package-manifest.stdout').read_bytes()) != receipt['package_manifest_sha256']:
                raise InvalidInput('public package manifest differs from supplied local package')
            for index, (name, expected_hash) in enumerate(sorted(manifest['files'].items())):
                label = 'public-package-file-' + str(index)
                execute(label, git + ['-C', 'auditor-source', 'show', args.package_commit + ':repro_v0/' + name])
                if digest((results / (label + '.stdout')).read_bytes()) != expected_hash:
                    raise InvalidInput('public package file hash mismatch: ' + name)
            receipt['package_commit_sha'] = args.package_commit
            receipt['package_version_verified'] = True
            receipt['cold_run_mode'] = 'acceptance_candidate'
            receipt['publication_gate_current'] = FORMAL_PUBLICATION_GATE
        execute('checkout', git + ['-C', 'auditor-source', 'checkout', '--detach', pin['auditor_commit_sha']])
        head = execute('fixed-head', git + ['-C', 'auditor-source', 'rev-parse', 'HEAD'])
        if head != pin['auditor_commit_sha']:
            raise RuntimeError('checkout SHA mismatch')
        if digest((work / 'auditor-source' / 'LICENSE').read_bytes()) != pin['source_repo_license_sha256']:
            raise InvalidInput('fixed repository license hash mismatch')
        if execute('tree-before', git + ['-C', 'auditor-source', 'status', '--porcelain']):
            raise RuntimeError('fresh source tree is dirty before audit')
        for name in ('problem', 'clean'):
            expected = pin['fixtures'][name + '.md']['exit_code']
            text = execute(name, ['python3', '-B', 'package/audit.py', '--engine', 'auditor-source/memory_auditor.py',
                                 '--fixture', 'package/fixtures/' + name + '.md', '--output', 'results/' + name + '.json'], (expected,))
            print(text)
            report_path = results / (name + '.json')
            report = json.loads(report_path.read_text(encoding='utf-8'))
            receipt['report_sha256'][name] = digest(report_path.read_bytes())
            receipt['finding_count'][name] = report['finding_count']
            if [[f['line'], f['issue']] for f in report['findings']] != pin['fixtures'][name + '.md']['findings']:
                raise RuntimeError('finding inventory mismatch: ' + name)
        receipt['repo_tree_clean'] = execute('tree-after', git + ['-C', 'auditor-source', 'status', '--porcelain']) == ''
        if not receipt['repo_tree_clean'] or manifest_check() != receipt['package_manifest_sha256']:
            raise RuntimeError('source or package drifted during run')
        if manifest_check(work / 'package') != receipt['package_manifest_sha256']:
            raise RuntimeError('copied package drifted')
        receipt['contract_checks'] = True
        receipt['blocker_codes'] = [
            'HUMAN_RECEIPT_REVIEW_REQUIRED',
            'NETWORK_OPERATOR_ATTESTED_ONLY',
            'PUBLIC_ARCHIVE_URL_HASH_READBACK_REQUIRED',
            'EXACT_PUBLIC_COMMIT_CI_SUCCESS_REQUIRED',
            'FORMAL_OWNER_RECEIPT_ACCEPTANCE_REQUIRED',
            'FORMAL_INDEPENDENT_RECEIPT_ACCEPTANCE_REQUIRED',
        ]
        receipt['blocker'] = [
            'human receipt review required; network is operator-attested, not independently observed',
            'public archive URL and content-hash readback remain open',
            'exact public commit CI success remains open',
            'publication gate remains open: ' + receipt['publication_gate_current'],
            'owner and independent tester receipts have not been accepted by this collector',
        ]
        if args.package_commit is None:
            receipt['blocker_codes'] += [
                'PUBLIC_PACKAGE_COMMIT_NOT_VERIFIED',
                'PUBLIC_ROOT_LICENSE_ALIGNMENT_NOT_VERIFIED',
                'PUBLIC_REPRO_V0_TREE_NOT_VERIFIED',
                'OWNER_REHEARSAL_ONLY',
            ]
            receipt['blocker'].append('local owner rehearsal only; repeat BOTH owner and independent with the same verified public package SHA/manifest')
        result = 2  # problem fixture has candidates; expected, not an execution failure.
    except InvalidInput as error:
        receipt['verdict'] = 'FAILED'
        receipt['blocker'].append('INVALID_INPUT: ' + str(error))
        result = 3
    except (Exception, KeyboardInterrupt) as error:
        receipt['verdict'] = 'FAILED'
        receipt['blocker'].append('EXECUTION_ERROR: ' + type(error).__name__ + ': ' + str(error))
        result = 4
    finally:
        if receipt['contract_checks']:
            try:
                raw_external = input('Seconds on the stopwatch started before the first archive integrity command after artifact acquisition (blank=unknown): ').strip()
                if raw_external:
                    external = float(raw_external)
                    if not math.isfinite(external) or external < 0:
                        raise ValueError('stopwatch time must be finite and nonnegative')
                    receipt['external_stopwatch_seconds'] = external
            except ValueError:
                receipt['verdict'] = 'FAILED'
                receipt['blocker'].append('INVALID_INPUT: stopwatch time must be finite and nonnegative')
                result = 3
            except (EOFError, KeyboardInterrupt):
                pass
        receipt['ended_at'] = utc(time.time())
        program_time = round(time.monotonic() - START_MONOTONIC, 6)
        external_time = receipt['external_stopwatch_seconds']
        receipt['program_elapsed_seconds'] = program_time
        receipt['elapsed_seconds'] = max(program_time, external_time) if external_time is not None else program_time
        receipt['within_600_seconds'] = receipt['elapsed_seconds'] <= 600 if external_time is not None else None
        if external_time is None:
            receipt['blocker'].append('post-acquisition external total duration unknown; internal timing cannot certify ten-minute completion')
        if program_time > 600 or (external_time is not None and external_time > 600):
            receipt['within_600_seconds'] = False
            receipt['verdict'] = 'FAILED'
            receipt['blocker'].append('elapsed time exceeded 600 seconds; keep this failed receipt')
            result = 4
        receipt['actual_exit_codes']['collector'] = result
        try:
            if work is None:
                raise OSError('temporary directory unavailable')
            atomic_json(work / 'receipt.json', receipt)
            print('Receipt (retain failures too): ' + str(work / 'receipt.json'))
        except Exception as error:
            print('EXECUTION_ERROR: receipt write failed: ' + type(error).__name__, file=sys.stderr)
            receipt['verdict'] = 'FAILED'
            receipt['actual_exit_codes']['collector'] = 4
            receipt['blocker'].append('disk receipt unavailable; fallback receipt is on stderr, not saved to disk')
            print(json.dumps(receipt, ensure_ascii=False, allow_nan=False), file=sys.stderr)
            result = 4
    return result


if __name__ == '__main__':
    sys.exit(main())
