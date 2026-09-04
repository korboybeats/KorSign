"""Run the release script with fake git/gh; never contact or modify GitHub."""
import json
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='korsign-release-policy-') as directory:
    work = Path(directory)
    for name, source in {
        'git': '''import os, sys
assert sys.argv[1:] == ['ls-remote', '--exit-code', '--refs', 'origin', 'refs/tags/v3.0.2']
sys.exit(int(os.environ['TAG_STATUS']))
''',
        'gh': '''import json, os, sys
from pathlib import Path
Path(os.environ['CALL_LOG']).write_text(json.dumps(sys.argv[1:]))
sys.exit(int(os.environ['CREATE_STATUS']))
''',
    }.items():
        import sys
        path = work / name
        path.write_text('#!' + sys.executable + '\n' + source)
        path.chmod(0o755)
    log = work / 'calls.json'
    env = dict(os.environ, PATH=str(work) + os.pathsep + os.environ['PATH'],
               VERSION='3.0.2', GITHUB_REPOSITORY='fixture/KorSign', GITHUB_SHA='a'*40,
               CALL_LOG=str(log))
    for tag_status, create_status, expected in [(0, 0, 1), (128, 0, 128), (2, 0, 0), (2, 1, 1)]:
        log.unlink(missing_ok=True)
        result = subprocess.run(['sh', str(root / 'tools/create_release.sh')], cwd=work,
            env=env | {'TAG_STATUS': str(tag_status), 'CREATE_STATUS': str(create_status)},
            capture_output=True, text=True)
        assert result.returncode == expected, result.stderr
        if tag_status != 2:
            assert not log.exists(), 'Publish attempted without confirmed unused tag'
        else:
            assert json.loads(log.read_text()) == ['release', 'create', 'v3.0.2',
                'upload/KorSign.ipa', '--repo', 'fixture/KorSign', '--target', 'a'*40,
                '--title', 'KorSign v3.0.2', '--generate-notes']
workflow = (root / '.github/workflows/release.yml').read_text()
assert 'softprops/action-gh-release' not in workflow
assert 'cancel-in-progress: false' in workflow
assert workflow.index('tools/validate_ipa.py') < workflow.index('sh tools/create_release.sh')
print('PASS: existing tag/network error block publication; new tag uses exact Main/build; creation failure propagates without overwrite')
