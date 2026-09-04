"""Offline dependency refresh checks using generated, disposable TLS material."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.dont_write_bytecode = True
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'tools'))
import refresh_server_deps as tool

with tempfile.TemporaryDirectory(prefix='korsign-deps-test-') as directory:
    work = Path(directory)
    subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                    '-keyout', str(work / 'key.pem'), '-out', str(work / 'cert.pem'),
                    '-days', '1', '-subj', '/CN=fixture.invalid'], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(['openssl', 'genrsa', '-out', str(work / 'other.pem'), '2048'],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    other = (work / 'other.pem').read_text()
    key = (work / 'key.pem').read_text()
    cert = (work / 'cert.pem').read_text()
    valid = {'cert': cert, 'ca': cert, 'key1': key[:len(key)//2], 'key2': key[len(key)//2:],
             'info': {'domains': {'commonName': 'fixture.invalid'}}}
    destination = work / 'deps'
    destination.mkdir()
    (destination / 'sentinel').write_bytes(b'working set')

    def download(value):
        def run(command, **kwargs):
            assert '--max-time' in command and '=https' in command
            Path(command[command.index('--output') + 1]).write_text(value)
        return run

    def preserved():
        assert list(destination.iterdir()) == [destination / 'sentinel']
        assert (destination / 'sentinel').read_bytes() == b'working set'
        assert not list(work.glob('.korsign-deps-*'))

    for side_effect in (
        subprocess.CalledProcessError(22, 'curl'), download('not JSON'),
        download(json.dumps(valid | {'key1': None})),
        download(json.dumps(valid | {'cert': 'invalid certificate'})),
        download(json.dumps(valid | {'key2': 'invalid key'})),
        download(json.dumps(valid | {'key1': other[:len(other)//2], 'key2': other[len(other)//2:]})),
    ):
        with patch.object(tool.subprocess, 'run', side_effect=side_effect):
            try:
                tool.refresh('https://fixture.invalid/pack.json', destination)
            except (ValueError, TypeError, OSError, subprocess.CalledProcessError):
                pass
            else:
                raise AssertionError('Invalid refresh accepted')
        preserved()
    with patch.object(tool.subprocess, 'run', side_effect=download(json.dumps(valid))):
        with patch.object(tool, 'replace_directory', side_effect=OSError('swap failed')):
            try:
                tool.refresh('https://fixture.invalid/pack.json', destination)
            except OSError:
                pass
            else:
                raise AssertionError('Replacement failure ignored')
        preserved()
        tool.refresh('https://fixture.invalid/pack.json', destination)
        assert {p.name for p in destination.iterdir()} == {'server.crt', 'server.pem', 'commonName.txt'}
        assert (destination / 'server.pem').read_text() == key
        fresh = work / 'fresh'
        tool.refresh('https://fixture.invalid/pack.json', fresh)
        assert (fresh / 'server.crt').read_bytes() == (destination / 'server.crt').read_bytes()
    assert not list(work.glob('.korsign-deps-*'))
print('PASS: failed refresh preserves files; real TLS parsing and atomic directory replacement; first creation; staging cleanup')
