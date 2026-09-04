"""Run with the service venv: python test_server.py. No real credentials/network."""
import io
import plistlib
import tempfile
import time
import urllib.parse
import zipfile
from pathlib import Path
from unittest.mock import patch
import app as service

with tempfile.TemporaryDirectory() as root:
    service.ROOT = Path(root) / 'outputs'
    service.BASE = 'https://updater.example.test'
    client = service.app.test_client()
    work_paths = []

    def release(version, bundle, destination):
        work_paths.append(destination.parent)
        with zipfile.ZipFile(destination, 'w') as archive:
            archive.writestr('Payload/KorSign.app/Info.plist', plistlib.dumps({
                'CFBundleIdentifier': bundle, 'CFBundleShortVersionString': version,
                'CFBundleVersion': '42', 'CFBundleDisplayName': 'KorSign'}))
            archive.writestr('Payload/KorSign.app/test', bytes(range(256)) * 512)

    def signer(args, **kwargs):
        Path(args[args.index('-o') + 1]).write_bytes(Path(args[-1]).read_bytes())
        return type('Result', (), {'returncode': 0})()

    def post(bundle='com.korboy.korsign', **extra):
        return client.post('/ryuksign/sign', data={
            'version': '3.0.1', 'bundleId': bundle, 'p12password': 'test-only',
            'p12': (io.BytesIO(b'fake'), 'cert.p12'),
            'provision': (io.BytesIO(b'fake'), 'profile.mobileprovision'), **extra})

    assert client.get('/health').json == {'status': 'ok'}
    assert client.post('/ryuksign/sign', data=b'x' * (2097152 + 1)).status_code == 413
    assert post('com.unrelated.app').status_code == 400
    assert post('com.korboy.ryuksign').status_code == 400
    assert post(extra='unexpected').status_code in (400, 413)
    assert post(version='../3.0.1').status_code == 400
    with patch.object(service, 'fetch_release', release), patch.object(service.subprocess, 'run', signer):
        for bundle in service.BUNDLES:
            response = post(bundle)
            assert response.status_code == 200, response.data
            install = urllib.parse.urlsplit(response.json['install'])
            manifest_url = urllib.parse.parse_qs(install.query)['url'][0]
            manifest = plistlib.loads(client.get(urllib.parse.urlsplit(manifest_url).path).data)
            assert manifest['items'][0]['metadata']['bundle-identifier'] == bundle
            path = urllib.parse.urlsplit(manifest['items'][0]['assets'][0]['url']).path
            get = client.get(path, headers={'Accept-Encoding': 'gzip, deflate'})
            head = client.head(path, headers={'Accept-Encoding': 'gzip, deflate'})
            assert get.status_code == head.status_code == 200
            assert int(head.headers['Content-Length']) == len(get.data) > 131072
            assert not head.data and 'Content-Encoding' not in head.headers
            assert get.headers['Cache-Control'] == 'no-store'
            ranged = client.get(path, headers={'Range': 'bytes=10-29'})
            assert ranged.status_code == 206 and ranged.data == get.data[10:30]
            assert client.get(path.replace('app.ipa', 'certificate.p12')).status_code == 404
        assert all(not p.exists() for p in work_paths)
        with patch.object(service.subprocess, 'run', side_effect=service.subprocess.TimeoutExpired('zsign', 120)):
            assert post().status_code == 422
        assert all(not p.exists() for p in work_paths)
        service.lock.acquire()
        try:
            assert post().status_code == 429
        finally:
            service.lock.release()
        service.attempts.extend([time.monotonic()] * 10)
        assert post().status_code == 429
        with patch.object(service.time, 'time', return_value=time.time() + service.TTL + 1):
            assert client.get(path).status_code == 404
            service.cleanup()
            assert not list(service.ROOT.iterdir())
print('PASS: request limits, main/Dev signing contract, credential cleanup, expiry, HEAD/GET/ranges')
