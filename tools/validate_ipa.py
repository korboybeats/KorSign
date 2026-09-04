"""Validate the Main release archive without extracting archive-controlled paths."""
import argparse
import hashlib
import json
import plistlib
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate(ipa, deps, expected_build):
    app = 'Payload/KorSign.app/'
    with zipfile.ZipFile(ipa) as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)), 'Duplicate archive entries')
        require(all(n.startswith('Payload/') and '..' not in PurePosixPath(n).parts
                    for n in names), 'Unexpected archive path')
        require(not any(set(PurePosixPath(n).parts) & {'.codex', 'AGENTS.md', 'PROGRESS.md'}
                        for n in names), 'Local-only files in archive')
        require(archive.testzip() is None, 'Corrupt archive')
        hosts = [n for n in names if n.count('/') == 2 and n.endswith('.app/Info.plist')]
        require(hosts == [app + 'Info.plist'], 'Unexpected app inventory')
        info = plistlib.loads(archive.read(hosts[0]))
        require(info['CFBundleIdentifier'] == 'com.korboy.korsign', 'Not the Main bundle')
        require(info['CFBundleVersion'] == expected_build, 'Build identity mismatch')
        version = info['CFBundleShortVersionString']
        require(isinstance(version, str) and version and all(c in '0123456789.' for c in version),
                'Invalid release version')
        extensions = [n for n in names if n.startswith(app + 'PlugIns/')
                      and n.count('/') == 4 and n.endswith('.appex/Info.plist')]
        require(len(extensions) == 1, 'Unexpected extension inventory')
        widget = plistlib.loads(archive.read(extensions[0]))
        require(widget['CFBundleIdentifier'] == 'com.korboy.korsign.FeatherWidgetExtension',
                'Wrong widget identity')
        for name in ('server.crt', 'server.pem', 'commonName.txt'):
            expected = (deps / name).read_bytes()
            require(expected.strip() and archive.read(app + name) == expected,
                    'Missing or mismatched resource: ' + name)
        # Copy only named executable bytes to a fixed temporary path, never extractall.
        with tempfile.TemporaryDirectory(prefix='korsign-validate-') as directory:
            binary = Path(directory) / 'executable'
            for prefix, metadata in ((app, info), (extensions[0].removesuffix('Info.plist'), widget)):
                executable = metadata['CFBundleExecutable']
                require(isinstance(executable, str) and executable not in ('', '.', '..')
                        and '/' not in executable, 'Invalid executable name')
                with archive.open(prefix + executable) as source, binary.open('wb') as target:
                    shutil.copyfileobj(source, target)
                subprocess.run(['lipo', str(binary), '-verify_arch', 'arm64'], check=True,
                               stdout=subprocess.DEVNULL)
    digest = hashlib.sha256()
    with ipa.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return {'file': ipa.name, 'sha256': digest.hexdigest(), 'bytes': ipa.stat().st_size,
            'bundle_id': info['CFBundleIdentifier'], 'version': version, 'build': expected_build}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ipa', type=Path)
    parser.add_argument('--deps', type=Path, required=True)
    parser.add_argument('--expected-build', required=True)
    args = parser.parse_args()
    print(json.dumps(validate(args.ipa, args.deps, args.expected_build), indent=2))
