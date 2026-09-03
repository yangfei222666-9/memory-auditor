# memory-auditor reproduction package v0 format — local candidate revision v5

`package_state_at_build=local_candidate_unpublished` records only the local state when v5 was built. It does not state the publication status when this file is read and is not a verified ten-minute reproduction or public-release claim. Current status must be determined from the external Git, release, CI, and human-acceptance evidence named by `publication_status_authority=external_git_release_ci_and_human_receipts`; package text alone supplies no download location or status promotion. Cloning the pinned detector commit alone does **not** provide this wrapper.

Two locks are separate: detector commit `e64d2f31d93726e2e8ea1879e61cdfd392d2fb04`, and this package's manifest SHA256. `historical_public_head_at_v0_build=8c083d501302e0f8389b684584e05040cffc33b2` preserves only the initial v0 public snapshot; the local v5 build is bound to `local_repo_head_at_v5_build=cc5762a69dc212a9a67ab57a3615b46a031c72ae`. The build did not query the live remote, so `live_public_head_at_v5_build=null`; a local tracking ref is not presented as current public state. `embedded_package_commit_sha=null` is likewise build-time metadata, not a statement about whether a public package commit exists when this file is read. If external evidence has established a public package SHA, supply it through optional `--package-commit FULL40HEX`; do not write it back into package files or change the manifest. Replace `FULL40HEX` with that confirmed full 40-character hexadecimal commit SHA.

## Pre-execution integrity check (runs no package Python)

Obtain the complete ZIP SHA256 and `MANIFEST.json` SHA256 from a trusted delivery record separate from the ZIP. Do not trust values repeated only inside the ZIP or a chat. After obtaining the ZIP, start an external stopwatch before the first command below. The timed scope is integrity verification, extraction, README review, and collector execution after artifact acquisition; download or transfer time is recorded separately and is not included. Then run:

```bash
MA_TIMER_SCOPE=post_acquisition_verification_and_execution
: "${MA_ARCHIVE:?set MA_ARCHIVE to the downloaded ZIP path}"
: "${MA_ARCHIVE_SHA256:?set MA_ARCHIVE_SHA256 from the trusted delivery record}"
: "${MA_MANIFEST_SHA256:?set MA_MANIFEST_SHA256 from the trusted delivery record}"
ma_actual_archive_sha256="$(shasum -a 256 "$MA_ARCHIVE" | awk '{print $1}')"
test "$ma_actual_archive_sha256" = "$MA_ARCHIVE_SHA256"
ma_actual_manifest_sha256="$(unzip -p "$MA_ARCHIVE" memory-auditor-repro-v0/MANIFEST.json | shasum -a 256 | awk '{print $1}')"
test "$ma_actual_manifest_sha256" = "$MA_MANIFEST_SHA256"
unzip -t "$MA_ARCHIVE"
ma_run_dir="$(mktemp -d "${TMPDIR:-/tmp}/memory-auditor-repro-v5.XXXXXX")"
unzip -q "$MA_ARCHIVE" -d "$ma_run_dir"
cd "$ma_run_dir/memory-auditor-repro-v0"
```

Stop before running any package Python if either `test` or `unzip -t` is nonzero. The current local sidecar validation is only a cross-check; formal reruns must obtain both hashes from a separately authorized public delivery record.

## Environment and three human-run modes

Python 3.9+ and Git are required. The pre-execution integrity check also requires a POSIX shell, `shasum`, `awk`, `unzip`, and `mktemp`. Python dependencies use only the standard library. No pip/npm/Node, DSH, provider, credentials, sudo, global installation, daemon or port. Builder checks used macOS arm64 / Python 3.9.6. Owner cold run, Linux and other Python versions remain unverified.

The external stopwatch should already be running from before the first integrity-check command in the preceding section; do not restart or pause it here. The collector also records `program_elapsed_seconds` using monotonic time from its own entry, which cannot replace the external total. Integrity checks, extraction, README review, clone failures, mistakes, and the offline prompt count. Artifact download or transfer time is recorded separately, so this package cannot claim end-to-end download plus reproduction within 600 seconds.

```bash
python3 -B owner_run.py --tester-role owner
```

When invoked without a public package SHA, this command marks the receipt mode as owner rehearsal; that receipt cannot be combined with a later independent receipt for formal two-person acceptance. After the public package is frozen, both owner and independent must rerun with the same real `--package-commit FULL40HEX`. An independent run without this argument returns `3=INVALID_INPUT` immediately.

Formal owner acceptance (only after a public package commit exists and a separate gate authorizes the run):

```bash
python3 -B owner_run.py --tester-role owner --package-commit FULL40HEX
```

Formal independent acceptance (run by a tester uninvolved in building and using only this README):

```bash
python3 -B owner_run.py --tester-role independent --package-commit FULL40HEX
```

These three commands are not interchangeable. The embedded `embedded_package_commit_sha=null` is not a current-state declaration. By contract, a run without `--package-commit` is marked as rehearsal; formal owner and independent acceptance candidates must bind the same full SHA established by external evidence.

Answer honestly about prior exposure, first clone, existing repository/virtual environment/cache, author assistance and README-only use. Unknown means `unknown`. Do not clear machine-wide caches or describe a warm run as cold. Private guidance or a successful demonstration counts as author help.

The acquisition phase runs `git ls-remote` and `git clone --no-checkout`; the only declared remote is `https://github.com/yangfei222666-9/memory-auditor.git`. The collector compares the clone's tracking HEAD with the live remote HEAD read at acquisition start. At the prompt disconnect **all** network interfaces before answering `yes`. When a public package SHA is supplied, the collector requires it to be a commit reachable from that live HEAD, verifies that the commit's root `LICENSE` is a regular `100644` file byte-identical to the package license, and checks that `repro_v0/` consists exactly of `MANIFEST.json` plus the manifest-listed regular `100644` files, comparing the manifest and every file hash. Merely supplying a SHA is not verification. It then checks out the fixed detector SHA offline, verifies the historical source license, audits both fixtures, and records source-tree and package integrity. Global Git config and credential helpers are disabled. No secrets are read; proxy configuration is not inherited. A network failure is retained, not retried.

Audit subprocesses use a Python audit hook to deny socket/process operations. This is not OS isolation or packet capture. `network_observed` distinguishes tester-confirmed disconnection from unobserved traffic. No attempted network call is not proof of no machine-wide traffic; human review is still needed, and unexpected traffic is a blocker.

After both fixture commands, enter the stopwatch total measured from before the first integrity-check command. An unknown external total leaves `within_600_seconds=null`; program timing alone cannot establish acceptance. NaN, infinity and negative values are rejected as timing evidence. Program time or any known total above 600 seconds means `FAILED` and exit 4. The collector prints a new temporary directory's `receipt.json`. Preserve the entire directory, including failures. Even when every formal Git and package check above succeeds, receipts default to `PENDING`; the collector only gathers evidence and cannot certify a cold run. Public archive URL/content-hash readback, exact-SHA CI success, and acceptance of both owner and independent receipts remain external gates. Network, environment, and independence claims still require human review.

## One exit-code table

| code | meaning |
|---|---|
| 0 | CLEAN: valid input, complete report, zero candidates |
| 2 | CANDIDATE_FINDINGS: valid input, complete report, candidates present; not execution failure |
| 3 | INVALID_INPUT: missing/invalid input or fixture/source hash mismatch; no new success report |
| 4 | EXECUTION_ERROR: unexpected error, report/receipt write failure, timeout or contract mismatch |

The inner problem command expects **2**; clean expects **0**. The successful collector returns **2** because the combined result includes problem candidates. It records every command, raw stdout/stderr and expected/actual exit. Signals, timeouts or undeclared codes never pass. CLI `--help` is documentation, not an audit.

There are ten synthetic memories in `problem.md`: line 1 `done_without_evidence`, line 2 `overclaim`, line 4 `duplicate`: three candidates. `clean.md` is the clean counterpart of those ten records, expected zero. Preserve both complete reports. Output says **candidate, not verdict / 候选，不是判决**. No real memory, private ledger or host path was copied.

## Extract-and-run layout smoke (two commands)

This checks only the ZIP layout, pinned engine, both fixtures and the exit-code contract. It performs no clone and is not an owner cold run. Run these lines unchanged from the extracted package directory; each creates a fresh temporary report directory:

```bash
ma_problem_dir="$(mktemp -d "${TMPDIR:-/tmp}/memory-auditor-problem.XXXXXX")"; python3 -B audit.py --engine pinned-engine.py --fixture fixtures/problem.md --output "$ma_problem_dir/problem.json"; ma_problem_code=$?; test "$ma_problem_code" -eq 2
ma_clean_dir="$(mktemp -d "${TMPDIR:-/tmp}/memory-auditor-clean.XXXXXX")"; python3 -B audit.py --engine pinned-engine.py --fixture fixtures/clean.md --output "$ma_clean_dir/clean.json"; ma_clean_code=$?; test "$ma_clean_code" -eq 0
```

Both shell commands must finish with exit 0. The inner problem audit still returns the declared code 2, while clean returns 0. Retain the printed candidates and report hashes; this builder smoke is not an owner or independent receipt.

## Receipts, limits and public gates

Receipts record fixed SHA/public HEAD; package, both READMEs, fixtures, license, reports and stdout/stderr hashes; OS/architecture, Python/Git, exact commands, exit codes, finding counts, time, tree status, network and independence declarations. Unknown fields are not invented. Existing reports cannot be overwritten. The manifest covers every package file except itself; its own SHA256 is recorded separately, avoiding a circular self-hash.

Lexical matching is not semantic judgment. False positives/negatives, skipped short lines, approximate negation windows and misleading evidence keywords remain possible. Evidence authenticity is not checked. This is not a production safety tool or proof about the whole assistant/all platforms. The wrapper accepts only two frozen Markdown fixtures, does not alter the detector, and never runs a deep/provider mode.

This package uses MIT. [LICENSE](LICENSE) identifies `Copyright (c) 2026 yangfei222666-9`. `pinned-engine.py` is a byte-identical copy of `memory_auditor.py` at the fixed commit and is used only for builder/layout self-checks; [FIXTURE_LICENSE.md](FIXTURE_LICENSE.md) and `pinned.json` record its provenance, purpose, and distribution authorization. The fixed historical source commit still carries its original placeholder notice, so `source_repo_license_sha256` and the current `package_license_sha256` are recorded separately and are not interchangeable. The package LICENSE and repository working-tree root LICENSE are byte-aligned in the local v5 scope; the root LICENSE, package files, and publication status of any public commit can be established only by the formal run and evidence governed by `publication_status_authority`.

The owner must perform the owner cold run; builder tests do not count. After separately authorized publication pins the public package commit and README, the owner and a person uninvolved in building and without a success recording must each rerun the same command, using roles `owner` and `independent` respectively and the same public package SHA. Earlier rehearsals without that SHA do not count toward these two receipts. Both runs must share detector SHA, manifest and fixtures, finish within 600 total seconds, and the independent tester must receive no extra guidance. Screenshots/comments are receipt indexes, not substitutes. `verified_public` also needs public URL/content-hash readback.

Retain the first failed run ID. After a change, use a new directory and label an assisted rerun; never overwrite failures. Rollback needs no system uninstall: after exit, retain receipts and move only this run's printed `memory-auditor-repro-v0-*` temporary directory to Trash, not any other directory.

## Extracted-layout self-check (not a cold run)

Run the second README command from the extracted package directory:

```bash
REPRO_TEST_ENGINE=./pinned-engine.py python3 -B -m unittest discover -s . -p test_contract.py -v
```

`pinned-engine.py` is only for the builder self-check. Its content comes from the fixed detector commit, and its SHA256 must match `pinned.json`; the owner flow still reads the detector from the Git objects cloned during that run. Collector unit tests fully mock Git/processes/input; temporary synthetic receipts are cleaned up and cannot count as human acceptance. No real clone or owner cold run occurs. The old Node requirement at the end of the spec conflicts with its Python-only body; this package follows the narrower Python-only scope.
