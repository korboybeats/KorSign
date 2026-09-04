"""Local synthetic ZIP checks; no app build, network, signing or delivery."""
import importlib.util
import plistlib
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.dont_write_bytecode = True
root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('validate_ipa', root / 'tools/validate_ipa.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
app = 'Payload/KorSign.app/'
widget = app + 'PlugIns/Widget.appex/'
with tempfile.TemporaryDirectory(prefix='korsign-release-test-') as directory:
    work = Path(directory)
    binary = work / 'fixture.o'
    subprocess.run(['xcrun', '--sdk', 'iphoneos', 'clang', '-target', 'arm64-apple-ios16.0', '-x', 'c', '-c',
                    '-o', str(binary), '-'], input=b'int fixture;', check=True)
    entries = {
        app + 'Info.plist': plistlib.dumps({'CFBundleIdentifier': 'com.korboy.korsign',
            'CFBundleVersion': 'test-build', 'CFBundleShortVersionString': '3.0.1',
            'CFBundleExecutable': 'KorSign'}),
        widget + 'Info.plist': plistlib.dumps({
            'CFBundleIdentifier': 'com.korboy.korsign.FeatherWidgetExtension',
            'CFBundleExecutable': 'Widget'}),
        app + 'KorSign': binary.read_bytes(), widget + 'Widget': binary.read_bytes(),
    }
    for name in ('server.crt', 'server.pem', 'commonName.txt'):
        (work / name).write_bytes(b'fixture-only')
        entries[app + name] = b'fixture-only'
    archive = work / 'fixture.zip'

    def check(values, *, rejected=False, build='test-build'):
        with zipfile.ZipFile(archive, 'w') as output:
            for name, data in values.items():
                output.writestr(name, data)
        try:
            result = module.validate(archive, work, build)
        except (ValueError, KeyError, subprocess.CalledProcessError):
            assert rejected, 'Valid fixture rejected'
        else:
            assert not rejected, 'Invalid fixture accepted'
            assert result['version'] == '3.0.1' and len(result['sha256']) == 64

    check(entries)
    check(entries, rejected=True, build='different-build')
    wrong = plistlib.loads(entries[app + 'Info.plist'])
    wrong['CFBundleIdentifier'] = 'com.korboy.korsign.dev'
    check(entries | {app + 'Info.plist': plistlib.dumps(wrong)}, rejected=True)
    check({k: v for k, v in entries.items() if k != app + 'server.pem'}, rejected=True)
    check(entries | {app + 'server.pem': b'wrong'}, rejected=True)
    check(entries | {app + 'PROGRESS.md': b'local'}, rejected=True)
    check(entries | {widget + 'Widget': b'not a binary'}, rejected=True)
    archive.write_bytes(b'not a ZIP')
    try:
        module.validate(archive, work, 'test-build')
    except zipfile.BadZipFile:
        pass
    else:
        raise AssertionError('Corrupt archive accepted')

workflow = (root / '.github/workflows/release.yml').read_text()
assert 'upload/*' not in workflow and 'packages/*' not in workflow
assert 'upload/KorSign.ipa' in workflow
assert workflow.index('tools/validate_ipa.py') < workflow.index('sh tools/create_release.sh')
print('PASS: valid Main, wrong bundle/build, missing/mismatched resources, local files, invalid binary/ZIP, exact release selection')
