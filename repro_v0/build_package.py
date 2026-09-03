#!/usr/bin/env python3
"""Build a deterministic, manifest-locked reproduction ZIP."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import sys
import zipfile


ROOT = Path(__file__).resolve().parent
PREFIX = 'memory-auditor-repro-v0/'
ZIP_TIMESTAMP = (2026, 8, 27, 0, 0, 0)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def package_files():
    manifest_path = ROOT / 'MANIFEST.json'
    manifest_raw = manifest_path.read_bytes()
    manifest = json.loads(manifest_raw)
    expected = manifest.get('files')
    if manifest.get('format') != 'sha256-path-manifest-v1' or not isinstance(expected, dict):
        raise ValueError('unsupported manifest format')

    paths = list(ROOT.rglob('*'))
    if any(path.is_symlink() for path in paths):
        raise ValueError('package symlinks are forbidden')
    actual = sorted(
        path.relative_to(ROOT).as_posix()
        for path in paths
        if path.is_file() and path != manifest_path
    )
    if actual != sorted(expected):
        raise ValueError('package file set differs from manifest')

    files = {'MANIFEST.json': manifest_raw}
    for name, expected_hash in expected.items():
        relative = PurePosixPath(name)
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('unsafe manifest path: ' + name)
        raw = (ROOT / name).read_bytes()
        if digest(raw) != expected_hash:
            raise ValueError('package file hash mismatch: ' + name)
        files[name] = raw
    return files, digest(manifest_raw)


def build(output):
    output = output.expanduser().resolve()
    if output.parent == ROOT or ROOT in output.parents:
        raise ValueError('output must be outside the package directory')
    if not output.parent.is_dir():
        raise ValueError('output parent does not exist')

    files, manifest_hash = package_files()
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(files):
            info = zipfile.ZipInfo(PREFIX + name, date_time=ZIP_TIMESTAMP)
            info.create_system = 3
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(info, files[name])

    with zipfile.ZipFile(output) as archive:
        expected_names = {PREFIX + name for name in files}
        if archive.testzip() is not None or set(archive.namelist()) != expected_names:
            raise RuntimeError('ZIP integrity or member-set check failed')
        for name, raw in files.items():
            if archive.read(PREFIX + name) != raw:
                raise RuntimeError('ZIP member mismatch: ' + name)

    return {
        'archive': str(output),
        'archive_bytes': output.stat().st_size,
        'archive_sha256': digest(output.read_bytes()),
        'manifest_sha256': manifest_hash,
        'file_count': len(files),
        'zip_integrity': 'PASS',
        'all_member_bytes_match': 'PASS',
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = build(args.output)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        print('BUILD_ERROR: ' + type(error).__name__ + ': ' + str(error), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
