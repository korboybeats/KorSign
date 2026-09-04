"""Exercise replacement ordering and failure cleanup using isolated non-app ZIPs."""
import plistlib
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.dont_write_bytecode = True
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'tools'))
import package_ipa

with tempfile.TemporaryDirectory(prefix='korsign-package-test-') as directory:
    work = Path(directory)
    stage = work / 'stage with spaces'
    app = stage / 'Payload/KorSign.app'
    app.mkdir(parents=True)
    (app / 'Info.plist').write_bytes(plistlib.dumps({'CFBundleVersion': 'fixture'}))
    destination = work / 'packages/fixture.zip'
    destination.parent.mkdir()
    destination.write_bytes(b'previous working artifact')

    def preserved():
        assert destination.read_bytes() == b'previous working artifact'
        assert list(destination.parent.iterdir()) == [destination], 'Temporary files stranded'

    def failed_zip(command, **kwargs):
        Path(command[2]).write_bytes(b'partial archive')
        raise subprocess.CalledProcessError(1, command)

    with patch.object(package_ipa.subprocess, 'run', side_effect=failed_zip):
        try:
            package_ipa.package(stage, destination, work)
        except subprocess.CalledProcessError:
            pass
        else:
            raise AssertionError('ZIP failure ignored')
    preserved()

    # Real ZIP creation followed by real validator rejection of incomplete metadata.
    try:
        package_ipa.package(stage, destination, work)
    except KeyError:
        pass
    else:
        raise AssertionError('Validation failure ignored')
    preserved()

    def accepted(candidate, deps, build):
        assert destination.read_bytes() == b'previous working artifact'
        assert candidate.parent.parent == destination.parent
        assert build == 'fixture'
        with zipfile.ZipFile(candidate) as archive:
            assert archive.testzip() is None
            assert 'Payload/KorSign.app/Info.plist' in archive.namelist()
        return {'status': 'fixture accepted'}

    with patch.object(package_ipa, 'validate', side_effect=accepted):
        with patch.object(Path, 'replace', side_effect=OSError('replacement denied')):
            try:
                package_ipa.package(stage, destination, work)
            except OSError:
                pass
            else:
                raise AssertionError('Replacement failure ignored')
        preserved()
        assert package_ipa.package(stage, destination, work) == {'status': 'fixture accepted'}
    assert zipfile.is_zipfile(destination)
    assert list(destination.parent.iterdir()) == [destination]

makefile = (root / 'Makefile').read_text()
assert 'python3 tools/package_ipa.py --stage "$(STAGE)"' in makefile
assert 'rm -f "packages/$(IPA_NAME).ipa"' not in makefile
print('PASS: ZIP, validation and replacement failures preserve previous output; success replaces after validation; temporary files cleaned')
