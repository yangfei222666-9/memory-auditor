"""Builder-only tests; never clone, run owner_run, or create a cold-run receipt."""
import json
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest import mock

import owner_run as collector

ROOT = Path(__file__).resolve().parent
SOURCE_ROOT_VALUE = os.environ.get('REPRO_SOURCE_ROOT')


class DocumentationContractTests(unittest.TestCase):
    def test_v5_license_notice_and_bundled_detector_provenance(self):
        license_text = (ROOT / 'LICENSE').read_text(encoding='utf-8')
        self.assertIn('Copyright (c) 2026 yangfei222666-9', license_text)
        self.assertNotIn('[year]', license_text)
        self.assertNotIn('[fullname]', license_text)

        fixture_license = (ROOT / 'FIXTURE_LICENSE.md').read_text(encoding='utf-8')
        self.assertIn('pinned-engine.py', fixture_license)
        self.assertIn('is bundled', fixture_license)
        self.assertIn('yangfei222666-9', fixture_license)
        self.assertNotIn('is not bundled', fixture_license)

        pin = json.loads((ROOT / 'pinned.json').read_text(encoding='utf-8'))
        self.assertEqual(pin['candidate_revision'], 'v5')
        self.assertEqual(pin['public_ref'], 'refs/heads/main')
        self.assertNotIn('public_head_at_build', pin)
        self.assertEqual(pin['historical_public_head_at_v0_build'], '8c083d501302e0f8389b684584e05040cffc33b2')
        self.assertNotIn('local_repo_head_at_v4_build', pin)
        self.assertNotIn('live_public_head_at_v4_build', pin)
        self.assertEqual(pin['local_repo_head_at_v5_build'], 'cc5762a69dc212a9a67ab57a3615b46a031c72ae')
        self.assertIsNone(pin['live_public_head_at_v5_build'])
        self.assertNotIn('repo_license_sha256', pin)
        self.assertEqual(pin['source_repo_license_sha256'], '45651d6af45c674b39de8fb59513cf032c85ed1512ee57f523cc5b950f805066')
        self.assertEqual(pin['package_license_sha256'], hashlib.sha256((ROOT / 'LICENSE').read_bytes()).hexdigest())
        self.assertNotEqual(pin['source_repo_license_sha256'], pin['package_license_sha256'])
        self.assertEqual(pin['runtime_dependencies'], 'python_stdlib_only')
        self.assertEqual(pin['external_tools'], ['git', 'POSIX shell', 'shasum', 'awk', 'unzip', 'mktemp'])
        self.assertNotIn('package_commit_sha', pin)
        self.assertNotIn('package_state', pin)
        self.assertNotIn('publication_gate', pin)
        self.assertIsNone(pin['embedded_package_commit_sha'])
        self.assertEqual(pin['package_state_at_build'], 'local_candidate_unpublished')
        self.assertEqual(pin['publication_status_authority'], 'external_git_release_ci_and_human_receipts')
        self.assertEqual(pin['publication_preconditions'], [
            'public_package_commit_reachable_from_live_main',
            'public_root_license_matches_package_license',
            'public_repro_v0_exact_file_set_and_hashes_match',
            'public_archive_url_and_content_hash_readback',
            'exact_public_commit_ci_success',
            'owner_and_independent_receipts_accepted',
        ])
        self.assertEqual(pin['third_party_materials'], [])
        self.assertEqual(pin['bundled_source_materials'], [{
            'path': 'pinned-engine.py',
            'source_repo': pin['public_repo'],
            'source_commit_sha': pin['auditor_commit_sha'],
            'source_path': 'memory_auditor.py',
            'license': 'MIT',
            'rights_holder': 'yangfei222666-9',
            'purpose': 'builder_and_layout_self_check_only',
        }])

    def test_readmes_require_hash_preflight_and_show_all_human_run_commands(self):
        required_fragments = (
            'MA_ARCHIVE_SHA256',
            'MA_MANIFEST_SHA256',
            'MA_TIMER_SCOPE=post_acquisition_verification_and_execution',
            'shasum -a 256',
            'unzip -p',
            'unzip -t',
            'python3 -B owner_run.py --tester-role owner',
            'python3 -B owner_run.py --tester-role owner --package-commit FULL40HEX',
            'python3 -B owner_run.py --tester-role independent --package-commit FULL40HEX',
            'publication_status_authority',
            'embedded_package_commit_sha',
        )
        for name in ('README.md', 'README.en.md'):
            text = (ROOT / name).read_text(encoding='utf-8')
            for fragment in required_fragments:
                self.assertIn(fragment, text, name + ' missing ' + fragment)
            self.assertIn('historical_public_head_at_v0_build', text)
            self.assertIn('local_repo_head_at_v5_build', text)
            self.assertNotIn('包尚未发布', text)
            self.assertNotIn('This package has not been published', text)
            self.assertNotIn('当前尚无这样的公开版本', text)
            self.assertNotIn('No such public version is available yet', text)
            self.assertNotIn('因此现在只能做 rehearsal', text)
            self.assertNotIn('only rehearsal is currently possible', text)
            self.assertNotIn('[year] [fullname]', text)
            for tool in ('POSIX shell', 'shasum', 'awk', 'unzip', 'mktemp'):
                self.assertIn(tool, text, name + ' missing declared external tool ' + tool)

    def test_collector_wording_matches_timer_and_two_role_contract(self):
        source = (ROOT / 'owner_run.py').read_text(encoding='utf-8')
        self.assertIn('before the first archive integrity command after artifact acquisition', source)
        self.assertNotIn('BEFORE copying the README command', source)
        self.assertIn('owner and independent tester receipts have not been accepted', source)
        self.assertNotIn('two independent tester receipts have not been accepted', source)
        self.assertIn('post-acquisition external total duration unknown', source)
        self.assertNotIn('pre-paste total duration unknown', source)


@unittest.skipUnless(SOURCE_ROOT_VALUE, 'source-repository publication contract requires REPRO_SOURCE_ROOT')
class PublicationTreeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source_root = Path(SOURCE_ROOT_VALUE).resolve()

    def test_root_license_matches_package_license(self):
        self.assertEqual((self.source_root / 'LICENSE').read_bytes(), (ROOT / 'LICENSE').read_bytes())

    def test_root_readmes_link_current_package_without_unbound_ci_claim(self):
        for name in ('README.md', 'README.en.md'):
            text = (self.source_root / name).read_text(encoding='utf-8')
            self.assertIn('repro_v0/README.md', text)
            self.assertIn('Copyright (c) 2026 yangfei222666-9', text)
        chinese = (self.source_root / 'README.md').read_text(encoding='utf-8')
        self.assertNotIn('14 个测试全绿,CI 绿', chinese)

    def test_legacy_repro_is_explicitly_historical(self):
        text = (self.source_root / 'REPRO.md').read_text(encoding='utf-8')
        self.assertIn('HISTORICAL_NODE_REPRODUCTION_RECORD', text[:800])
        self.assertIn('repro_v0/README.md', text[:800])

    def test_ci_runs_source_tree_package_contract(self):
        text = (self.source_root / '.github/workflows/ci.yml').read_text(encoding='utf-8')
        self.assertIn('python -m unittest discover -s tests -v', text)
        self.assertIn('working-directory: repro_v0', text)
        self.assertIn('REPRO_SOURCE_ROOT: ..', text)
        self.assertIn('REPRO_TEST_ENGINE: ./pinned-engine.py', text)
        self.assertIn('python -B -m unittest discover -s . -p test_contract.py -v', text)


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sandbox = tempfile.TemporaryDirectory(prefix='memory-repro-builder-')
        cls.base = Path(cls.sandbox.name)
        cls.engine = cls.base / 'memory_auditor.py'
        supplied = os.environ.get('REPRO_TEST_ENGINE')
        if supplied:
            raw = Path(supplied).read_bytes()
        else:
            pin = json.loads((ROOT / 'pinned.json').read_text())
            command = ['git', '-C', str(ROOT.parent), 'show', pin['auditor_commit_sha'] + ':memory_auditor.py']
            raw = subprocess.run(command, capture_output=True, check=True).stdout
        cls.engine.write_bytes(raw)

    @classmethod
    def tearDownClass(cls):
        cls.sandbox.cleanup()

    def setUp(self):
        self.folder = Path(tempfile.mkdtemp(dir=str(self.base)))
        self.report = self.folder / 'report.json'

    def invoke(self, name='problem.md', fixture=None, engine=None, output=None, script=None):
        command = [sys.executable, '-B', str(script or ROOT / 'audit.py'), '--engine', str(engine or self.engine),
                   '--fixture', str(fixture or ROOT / 'fixtures' / name), '--output', str(output or self.report)]
        environment = os.environ.copy()
        environment['TMPDIR'] = str(self.folder)
        return subprocess.run(command, capture_output=True, text=True, env=environment)

    def test_problem_has_three_named_candidates_and_exit_two(self):
        result = self.invoke()
        self.assertEqual(result.returncode, 2, result.stderr)
        report = json.loads(self.report.read_text())
        self.assertTrue(report['candidate_not_verdict'])
        self.assertEqual(report['finding_count'], 3)
        self.assertEqual([(f['line'], f['issue']) for f in report['findings']],
                         [(1, 'done_without_evidence'), (2, 'overclaim'), (4, 'duplicate')])
        self.assertIn('candidate, not verdict', result.stdout)
        self.assertNotIn(str(ROOT.parent), self.report.read_text())

    def test_clean_has_zero_candidates_and_exit_zero(self):
        result = self.invoke('clean.md')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(self.report.read_text())['findings'], [])

    def test_missing_input_is_three_without_report(self):
        result = self.invoke(fixture=self.folder / 'problem.md')
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertFalse(self.report.exists())

    def test_hash_tamper_is_three_without_report(self):
        bad = self.folder / 'problem.md'
        bad.write_text('a valid-looking but unapproved fixture\n')
        self.assertEqual(self.invoke(fixture=bad).returncode, 3)
        self.assertFalse(self.report.exists())

    def test_non_utf8_is_three_without_report(self):
        bad = self.folder / 'problem.md'
        bad.write_bytes(b'\xff\xfe')
        self.assertEqual(self.invoke(fixture=bad).returncode, 3)
        self.assertFalse(self.report.exists())

    def test_bad_engine_is_three_without_report(self):
        engine = self.folder / 'engine.py'
        engine.write_text('raise Exception("not the pinned detector")\n')
        self.assertEqual(self.invoke(engine=engine).returncode, 3)
        self.assertFalse(self.report.exists())

    def test_existing_report_is_four_and_unchanged(self):
        self.report.write_bytes(b'old report must remain\n')
        self.assertEqual(self.invoke().returncode, 4)
        self.assertEqual(self.report.read_bytes(), b'old report must remain\n')

    def test_missing_output_directory_is_three(self):
        result = self.invoke(output=self.folder / 'absent' / 'report.json')
        self.assertEqual(result.returncode, 3)

    def test_output_outside_temporary_directory_is_three(self):
        result = self.invoke(output=ROOT / 'must-not-write.json')
        self.assertEqual(result.returncode, 3)
        self.assertFalse((ROOT / 'must-not-write.json').exists())

    def test_fixture_symlink_is_three(self):
        link = self.folder / 'problem.md'
        link.symlink_to(ROOT / 'fixtures' / 'problem.md')
        self.assertEqual(self.invoke(fixture=link).returncode, 3)
        self.assertFalse(self.report.exists())

    def test_bad_cli_arguments_are_three_not_argparse_two(self):
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'audit.py'), '--unknown'], capture_output=True)
        self.assertEqual(result.returncode, 3)

    def test_package_tamper_is_three(self):
        packet = self.folder / 'packet'
        shutil.copytree(ROOT, packet)
        (packet / 'README.md').write_text('changed README\n')
        self.assertEqual(self.invoke(script=packet / 'audit.py').returncode, 3)
        self.assertFalse(self.report.exists())

    def test_unmanifested_nested_manifest_is_rejected(self):
        packet = self.folder / 'packet'
        shutil.copytree(ROOT, packet)
        (packet / 'extra').mkdir()
        (packet / 'extra' / 'MANIFEST.json').write_text('{}')
        self.assertEqual(self.invoke(script=packet / 'audit.py').returncode, 3)

    def test_network_guard_blocks_socket_creation_without_connecting(self):
        code = 'import sys;sys.path.insert(0,sys.argv[1]);import audit,socket;audit.network_guard();socket.socket()'
        result = subprocess.run([sys.executable, '-B', '-c', code, str(ROOT)], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('network/process attempt forbidden', result.stderr)


class CollectorUnitTests(unittest.TestCase):
    """Synthetic subprocess/input fixtures only: no real Git, network or cold run."""
    def setUp(self):
        folder = tempfile.TemporaryDirectory(prefix='repro-collector-unit-')
        self.addCleanup(folder.cleanup)
        self.work = Path(folder.name) / 'run'
        self.work.mkdir()
        self.pin = json.loads((ROOT / 'pinned.json').read_text())
        self.public_head = 'a' * 40
        self.assertNotEqual(self.public_head, self.pin.get('local_repo_head_at_v5_build'))

    def locked_package_bytes(self, relative):
        if relative == 'MANIFEST.json':
            return (ROOT / relative).read_bytes()
        manifest = json.loads((ROOT / 'MANIFEST.json').read_text())
        expected = manifest['files'][relative]
        candidates = [ROOT / relative] + sorted(ROOT.glob(relative + '.bak-*'))
        for candidate in candidates:
            raw = candidate.read_bytes()
            if hashlib.sha256(raw).hexdigest() == expected:
                return raw
        raise AssertionError('no local fixture matches manifest hash: ' + relative)

    def fake_process(self, command, **kwargs):
        stdout, code = b'', 0
        if command == ['git', '--version']:
            stdout = b'git version synthetic-unit-fixture\n'
        elif 'ls-remote' in command:
            stdout = (self.public_head + '\trefs/heads/main\n').encode()
        elif 'clone' in command:
            source = self.work / 'auditor-source'
            source.mkdir()
            source_license = (ROOT / 'LICENSE').read_bytes().replace(
                b'Copyright (c) 2026 yangfei222666-9',
                b'Copyright (c) [year] [fullname]',
            ) + b'\n'
            self.assertEqual(hashlib.sha256(source_license).hexdigest(), self.pin['source_repo_license_sha256'])
            (source / 'LICENSE').write_bytes(source_license)
        elif 'cat-file' in command:
            stdout = b'commit\n'
        elif 'merge-base' in command:
            code = 0
        elif 'rev-parse' in command:
            if command[-1] == 'refs/remotes/origin/main':
                stdout = self.public_head.encode()
            else:
                stdout = self.pin['auditor_commit_sha'].encode()
        elif 'show' in command:
            revision_path = command[-1]
            if revision_path.endswith(':LICENSE'):
                stdout = (ROOT / 'LICENSE').read_bytes()
            else:
                relative = revision_path.split(':repro_v0/', 1)[1]
                stdout = self.locked_package_bytes(relative)
        elif 'ls-tree' in command:
            if command[-1] == 'LICENSE':
                stdout = ('100644 blob ' + '1' * 40 + '\tLICENSE\0').encode()
            else:
                manifest = json.loads((ROOT / 'MANIFEST.json').read_text())
                paths = ['repro_v0/MANIFEST.json'] + ['repro_v0/' + name for name in manifest['files']]
                stdout = b''.join(
                    ('100644 blob ' + str(index + 1).zfill(40) + '\t' + path + '\0').encode()
                    for index, path in enumerate(paths)
                )
        elif command[0] == 'python3':
            name = Path(command[command.index('--fixture') + 1]).name
            expected = self.pin['fixtures'][name]
            report = {'finding_count': len(expected['findings']),
                      'findings': [{'line': line, 'issue': issue} for line, issue in expected['findings']]}
            (self.work / command[-1]).write_text(json.dumps(report))
            code = expected['exit_code']
            stdout = b'synthetic collector test, not actual audit execution\n'
        return SimpleNamespace(returncode=code, stdout=stdout, stderr=b'')

    def simulate(self, external='1', process=None, role='owner', package_commit=None, answers=None):
        answers = answers or ['no', 'yes', 'no', 'no', 'yes', 'yes', external]
        manifest_hash = hashlib.sha256((ROOT / 'MANIFEST.json').read_bytes()).hexdigest()
        arguments = ['--tester-role', role]
        if package_commit is not None:
            arguments += ['--package-commit', package_commit]
        with mock.patch.object(collector.tempfile, 'mkdtemp', return_value=str(self.work)), \
             mock.patch.object(collector, 'manifest_check', return_value=manifest_hash), \
             mock.patch.object(collector.shutil, 'copytree'), \
             mock.patch.object(collector.subprocess, 'run', side_effect=process or self.fake_process), \
             mock.patch('builtins.input', side_effect=answers), \
             mock.patch.object(collector, 'START_MONOTONIC', time.monotonic()), \
             mock.patch.object(collector, 'START_WALL', time.time()):
            code = collector.main(arguments)
        receipt = json.loads((self.work / 'receipt.json').read_text())
        return code, receipt

    def test_external_over_600_fails_even_when_program_is_fast(self):
        code, receipt = self.simulate('601')
        self.assertEqual(code, 4)
        self.assertEqual(receipt['verdict'], 'FAILED')
        self.assertFalse(receipt['within_600_seconds'])

    def test_nonfinite_external_time_is_rejected(self):
        code, receipt = self.simulate('inf')
        self.assertEqual(code, 3)
        self.assertIsNone(receipt['external_stopwatch_seconds'])

    def test_unknown_external_time_does_not_claim_within_600(self):
        code, receipt = self.simulate('')
        self.assertEqual(code, 2)
        self.assertIsNone(receipt['within_600_seconds'])
        self.assertEqual(receipt['verdict'], 'PENDING')

    def test_receipt_exposes_v5_dependency_and_publication_contract(self):
        code, receipt = self.simulate()
        self.assertEqual(code, 2, receipt['blocker'])
        self.assertEqual(receipt['candidate_revision'], 'v5')
        self.assertEqual(receipt['runtime_dependencies'], 'python_stdlib_only')
        self.assertEqual(receipt['external_tools'], ['git', 'POSIX shell', 'shasum', 'awk', 'unzip', 'mktemp'])
        self.assertEqual(receipt['third_party_materials'], [])
        self.assertEqual(receipt['bundled_source_materials'][0]['path'], 'pinned-engine.py')
        self.assertEqual(receipt['source_repo_license_sha256'], self.pin['source_repo_license_sha256'])
        self.assertEqual(receipt['package_license_sha256'], self.pin['package_license_sha256'])
        self.assertEqual(receipt['publication_state_at_build'], self.pin['package_state_at_build'])
        self.assertEqual(receipt['publication_status_authority'], self.pin['publication_status_authority'])
        self.assertEqual(receipt['publication_preconditions'], self.pin['publication_preconditions'])
        self.assertEqual(receipt['public_ref'], self.pin['public_ref'])
        self.assertIsNone(receipt['package_commit_input_sha'])
        self.assertIsNone(receipt['public_source_repo_license_aligned'])
        self.assertEqual(
            receipt['publication_gate_current'],
            'BLOCKED_PUBLIC_PACKAGE_COMMIT_ROOT_LICENSE_ARCHIVE_URL_CI_AND_DUAL_HUMAN_ACCEPTANCE',
        )
        self.assertTrue(any(receipt['publication_gate_current'] in item for item in receipt['blocker']))
        self.assertFalse(any('public source-repository LICENSE notice alignment remains open' in item for item in receipt['blocker']))
        labels = [entry['label'] for entry in receipt['commands']]
        self.assertNotIn('public-root-license', labels)
        self.assertNotIn('public-package-manifest', labels)

    def test_temp_creation_failure_returns_declared_four(self):
        with mock.patch.object(collector.tempfile, 'mkdtemp', side_effect=OSError('synthetic no space')):
            self.assertEqual(collector.main(['--tester-role', 'owner']), 4)

    def test_package_license_hash_mismatch_stops_before_git(self):
        folder = tempfile.TemporaryDirectory(prefix='repro-license-mismatch-')
        self.addCleanup(folder.cleanup)
        tampered_root = Path(folder.name) / 'package'
        shutil.copytree(ROOT, tampered_root)
        (tampered_root / 'LICENSE').write_text('tampered package license\n', encoding='utf-8')
        with mock.patch.object(collector, 'ROOT', tampered_root):
            code, receipt = self.simulate()
        self.assertEqual(code, 3)
        self.assertEqual(receipt['commands'], [])
        self.assertFalse(receipt['package_version_verified'])
        self.assertIsNone(receipt['public_source_repo_license_aligned'])
        self.assertTrue(any('package LICENSE hash mismatch' in item for item in receipt['blocker']))

    def test_missing_executable_is_recorded_with_failed_command(self):
        code, receipt = self.simulate(process=FileNotFoundError('synthetic missing Git'))
        self.assertEqual(code, 4)
        self.assertEqual(len(receipt['commands']), 1)
        self.assertEqual(receipt['commands'][0]['label'], 'git-version')
        self.assertEqual(receipt['commands'][0]['command'], ['git', '--version'])
        self.assertIsNone(receipt['commands'][0]['actual'])
        self.assertIn('FileNotFoundError', receipt['commands'][0]['error'])

    def test_independent_without_external_pin_stops_before_git(self):
        code, receipt = self.simulate(role='independent')
        self.assertEqual(code, 3)
        self.assertEqual(receipt['commands'], [])

    def test_nonindependent_tester_cannot_become_acceptance_candidate(self):
        answers = ['no', 'yes', 'no', 'yes', 'yes', 'yes', '1']
        code, receipt = self.simulate(
            role='independent', package_commit='f' * 40, answers=answers,
        )
        self.assertEqual(code, 3)
        self.assertFalse(receipt['independent_eligibility'])
        self.assertEqual(receipt['cold_run_mode'], 'rehearsal')
        self.assertEqual(receipt['commands'], [])
        self.assertTrue(any('independent eligibility failed' in item for item in receipt['blocker']))

    def test_external_package_pin_checks_manifest_and_every_public_file(self):
        # Entire Git/process layer is mocked; this is NOT a public-SHA receipt.
        package_commit = 'f' * 40
        code, receipt = self.simulate(role='independent', package_commit=package_commit)
        self.assertEqual(code, 2, receipt['blocker'])
        self.assertTrue(receipt['independent_eligibility'])
        self.assertTrue(receipt['package_version_verified'])
        self.assertTrue(receipt['public_source_repo_license_aligned'])
        self.assertTrue(receipt['public_package_file_modes_verified'])
        self.assertEqual(receipt['package_commit_sha'], package_commit)
        self.assertEqual(receipt['package_commit_input_sha'], package_commit)
        self.assertEqual(receipt['clone_tracking_head'], self.public_head)
        self.assertEqual(receipt['cold_run_mode'], 'acceptance_candidate')
        self.assertEqual(
            receipt['publication_gate_current'],
            'BLOCKED_PUBLIC_ARCHIVE_URL_CONTENT_HASH_CI_AND_DUAL_HUMAN_ACCEPTANCE',
        )
        labels = [entry['label'] for entry in receipt['commands']]
        self.assertLess(labels.index('public-package-object-type'), labels.index('public-package-commit-reachable'))
        self.assertLess(labels.index('public-package-commit-reachable'), labels.index('public-root-license'))
        self.assertLess(labels.index('public-root-license'), labels.index('public-package-manifest'))
        by_label = {entry['label']: entry for entry in receipt['commands']}
        self.assertEqual(by_label['public-root-license']['command'][-1], package_commit + ':LICENSE')
        self.assertEqual(
            by_label['public-package-manifest']['command'][-1],
            package_commit + ':repro_v0/MANIFEST.json',
        )
        self.assertEqual(by_label['public-package-object-type']['command'][-3:],
                         ['cat-file', '-t', package_commit])
        self.assertEqual(by_label['public-package-commit-reachable']['command'][-4:],
                         ['merge-base', '--is-ancestor', package_commit, self.public_head])
        manifest = json.loads((ROOT / 'MANIFEST.json').read_text())
        checked = [entry for entry in receipt['commands'] if entry['label'].startswith('public-package-file-') and entry['label'] != 'public-package-file-set']
        self.assertEqual(len(checked), len(manifest['files']))
        self.assertEqual(
            {entry['command'][-1].split(':repro_v0/', 1)[1] for entry in checked},
            set(manifest['files']),
        )
        self.assertTrue(any(receipt['publication_gate_current'] in item for item in receipt['blocker']))
        self.assertFalse(any('public source-repository LICENSE notice alignment remains open' in item for item in receipt['blocker']))
        self.assertEqual(receipt['verdict'], 'PENDING')

    def test_public_root_license_mismatch_cannot_be_promoted(self):
        def wrong_root_license(command, **kwargs):
            if 'show' in command and command[-1].endswith(':LICENSE'):
                return SimpleNamespace(returncode=0, stdout=b'wrong public license\n', stderr=b'')
            return self.fake_process(command, **kwargs)
        code, receipt = self.simulate(
            process=wrong_root_license, role='independent', package_commit='f' * 40,
        )
        self.assertEqual(code, 3)
        self.assertFalse(receipt['public_source_repo_license_aligned'])
        self.assertFalse(receipt['package_version_verified'])
        self.assertIsNone(receipt['package_commit_sha'])
        self.assertEqual(receipt['cold_run_mode'], 'rehearsal')
        self.assertEqual(
            receipt['publication_gate_current'],
            'BLOCKED_PUBLIC_PACKAGE_COMMIT_ROOT_LICENSE_ARCHIVE_URL_CI_AND_DUAL_HUMAN_ACCEPTANCE',
        )
        self.assertNotIn('public-package-manifest', [entry['label'] for entry in receipt['commands']])

    def test_clone_tracking_head_drift_stops_before_public_package_checks(self):
        def drifted_tracking(command, **kwargs):
            if 'rev-parse' in command and command[-1] == 'refs/remotes/origin/main':
                return SimpleNamespace(returncode=0, stdout=b'b' * 40 + b'\n', stderr=b'')
            return self.fake_process(command, **kwargs)
        code, receipt = self.simulate(
            process=drifted_tracking, role='independent', package_commit='f' * 40,
        )
        self.assertEqual(code, 3)
        self.assertEqual(receipt['clone_tracking_head'], 'b' * 40)
        self.assertFalse(receipt['package_version_verified'])
        self.assertIsNone(receipt['package_commit_sha'])
        labels = [entry['label'] for entry in receipt['commands']]
        self.assertNotIn('public-package-object-type', labels)

    def test_public_package_symlink_mode_cannot_be_promoted(self):
        def symlink_mode(command, **kwargs):
            result = self.fake_process(command, **kwargs)
            if 'ls-tree' in command and command[-1] == 'repro_v0':
                result.stdout = result.stdout.replace(b'100644 blob ', b'120000 blob ', 1)
            return result
        code, receipt = self.simulate(
            process=symlink_mode, role='independent', package_commit='f' * 40,
        )
        self.assertEqual(code, 3)
        self.assertFalse(receipt['public_package_file_modes_verified'])
        self.assertFalse(receipt['package_version_verified'])
        self.assertIsNone(receipt['package_commit_sha'])
        self.assertNotIn('public-package-manifest', [entry['label'] for entry in receipt['commands']])

    def test_tree_object_sha_cannot_be_promoted(self):
        def tree_object(command, **kwargs):
            if 'cat-file' in command:
                return SimpleNamespace(returncode=0, stdout=b'tree\n', stderr=b'')
            return self.fake_process(command, **kwargs)
        code, receipt = self.simulate(process=tree_object, role='independent', package_commit='f' * 40)
        self.assertEqual(code, 3)
        self.assertFalse(receipt['package_version_verified'])
        self.assertIsNone(receipt['package_commit_sha'])
        self.assertEqual(receipt['cold_run_mode'], 'rehearsal')
        self.assertNotIn('public-package-commit-reachable', [entry['label'] for entry in receipt['commands']])

    def test_tag_object_sha_cannot_be_promoted(self):
        def tag_object(command, **kwargs):
            if 'cat-file' in command:
                return SimpleNamespace(returncode=0, stdout=b'tag\n', stderr=b'')
            return self.fake_process(command, **kwargs)
        code, receipt = self.simulate(process=tag_object, role='independent', package_commit='f' * 40)
        self.assertEqual(code, 3)
        self.assertFalse(receipt['package_version_verified'])
        self.assertIsNone(receipt['package_commit_sha'])

    def test_unreachable_commit_cannot_be_promoted(self):
        def unreachable(command, **kwargs):
            if 'merge-base' in command:
                return SimpleNamespace(returncode=1, stdout=b'', stderr=b'')
            return self.fake_process(command, **kwargs)
        code, receipt = self.simulate(process=unreachable, role='independent', package_commit='f' * 40)
        self.assertEqual(code, 3)
        self.assertEqual(receipt['actual_exit_codes']['public-package-commit-reachable'], 1)
        self.assertFalse(receipt['package_version_verified'])
        self.assertIsNone(receipt['package_commit_sha'])
        self.assertNotIn('public-package-manifest', [entry['label'] for entry in receipt['commands']])

    def test_reachability_git_error_is_execution_failure(self):
        def git_error(command, **kwargs):
            if 'merge-base' in command:
                return SimpleNamespace(returncode=128, stdout=b'', stderr=b'synthetic Git error\n')
            return self.fake_process(command, **kwargs)
        code, receipt = self.simulate(process=git_error, role='independent', package_commit='f' * 40)
        self.assertEqual(code, 4)
        self.assertFalse(receipt['package_version_verified'])
        self.assertIsNone(receipt['package_commit_sha'])
        self.assertEqual(receipt['cold_run_mode'], 'rehearsal')
        self.assertNotIn('public-package-manifest', [entry['label'] for entry in receipt['commands']])
        self.assertTrue(any('EXECUTION_ERROR' in blocker for blocker in receipt['blocker']))

    def test_object_type_git_error_is_execution_failure(self):
        def git_error(command, **kwargs):
            if 'cat-file' in command:
                return SimpleNamespace(returncode=128, stdout=b'', stderr=b'synthetic Git error\n')
            return self.fake_process(command, **kwargs)
        code, receipt = self.simulate(process=git_error, role='independent', package_commit='f' * 40)
        self.assertEqual(code, 4)
        self.assertFalse(receipt['package_version_verified'])
        self.assertIsNone(receipt['package_commit_sha'])
        self.assertNotIn('public-package-commit-reachable', [entry['label'] for entry in receipt['commands']])
        self.assertNotIn('public-package-manifest', [entry['label'] for entry in receipt['commands']])

    def test_public_manifest_mismatch_cannot_be_promoted(self):
        def wrong_manifest(command, **kwargs):
            if 'show' in command and command[-1].endswith(':repro_v0/MANIFEST.json'):
                return SimpleNamespace(returncode=0, stdout=b'{}\n', stderr=b'')
            return self.fake_process(command, **kwargs)
        code, receipt = self.simulate(process=wrong_manifest, package_commit='f' * 40)
        self.assertEqual(code, 3)
        self.assertFalse(receipt['package_version_verified'])
        self.assertIsNone(receipt['package_commit_sha'])
        self.assertEqual(receipt['cold_run_mode'], 'rehearsal')
        self.assertEqual(
            receipt['publication_gate_current'],
            'BLOCKED_PUBLIC_PACKAGE_COMMIT_ROOT_LICENSE_ARCHIVE_URL_CI_AND_DUAL_HUMAN_ACCEPTANCE',
        )

    def test_public_file_hash_mismatch_cannot_be_promoted(self):
        def wrong_file(command, **kwargs):
            result = self.fake_process(command, **kwargs)
            if 'show' in command and command[-1].endswith(':repro_v0/audit.py'):
                result.stdout = b'wrong public file\n'
            return result
        code, receipt = self.simulate(process=wrong_file, package_commit='f' * 40)
        self.assertEqual(code, 3)
        self.assertFalse(receipt['package_version_verified'])
        self.assertIsNone(receipt['package_commit_sha'])
        self.assertEqual(receipt['cold_run_mode'], 'rehearsal')

    def test_extra_public_file_fails_exact_package_scope(self):
        def extra_file(command, **kwargs):
            result = self.fake_process(command, **kwargs)
            if 'ls-tree' in command and command[-1] == 'repro_v0':
                result.stdout += b'100644 blob 9999999999999999999999999999999999999999\trepro_v0/unmanifested.txt\0'
            return result
        code, receipt = self.simulate(process=extra_file, package_commit='f' * 40)
        self.assertEqual(code, 3)
        self.assertFalse(receipt['package_version_verified'])
        self.assertIsNone(receipt['package_commit_sha'])
        self.assertEqual(receipt['cold_run_mode'], 'rehearsal')


if __name__ == '__main__':
    unittest.main()
