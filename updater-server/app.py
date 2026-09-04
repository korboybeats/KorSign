"""KorSign-only signing service. Bind to loopback behind Cloudflare Tunnel."""
import os
from collections import deque
import plistlib
import re
import secrets
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import json
import zipfile
from pathlib import Path
from flask import Flask, request, jsonify, send_file, abort

app = Flask(__name__)
app.config.update(MAX_CONTENT_LENGTH=2 * 1024 * 1024, MAX_FORM_PARTS=5,
                  MAX_FORM_MEMORY_SIZE=512 * 1024)
ROOT = Path(os.environ.get('KORSIGN_OUTPUT', '/var/lib/korsign-updater'))
BASE = os.environ.get('KORSIGN_PUBLIC_URL', '').rstrip('/')
SIGNER = os.environ.get('KORSIGN_ZSIGN', '/usr/local/bin/zsign')
BUNDLES = {'com.korboy.korsign': 'KorSign.ipa',
           'com.korboy.korsign.dev': 'KorSign-Dev.ipa'}
TTL = 1800
# ponytail: one signing job per process; use a bounded job queue if demand grows.
lock = threading.Lock()
attempts = deque()


def cleanup():
    ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    for path in ROOT.iterdir():
        if re.fullmatch(r'[0-9a-f]{48}', path.name) and path.is_dir():
            if time.time() - path.stat().st_mtime > TTL:
                shutil.rmtree(path)


def fetch_release(version, bundle, destination):
    url = 'https://api.github.com/repos/korboybeats/KorSign/releases/tags/v' + version
    req = urllib.request.Request(url, headers={'Accept': 'application/vnd.github+json',
                                               'User-Agent': 'KorSign-Updater'})
    with urllib.request.urlopen(req, timeout=15) as response:
        data = response.read(1024 * 1024 + 1)
    if len(data) > 1024 * 1024:
        raise ValueError('release_too_large')
    release = json.loads(data)
    if release.get('draft') or release.get('tag_name') != 'v' + version:
        raise ValueError('unknown_version')
    asset = next((a for a in release.get('assets', []) if a.get('name') == BUNDLES[bundle]), None)
    if not asset or not 0 < asset.get('size', 0) <= 100 * 1024 * 1024:
        raise ValueError('unknown_version')
    expected = f'https://github.com/korboybeats/KorSign/releases/download/v{version}/{BUNDLES[bundle]}'
    if asset.get('browser_download_url') != expected:
        raise ValueError('unknown_version')
    with urllib.request.urlopen(expected, timeout=30) as response, destination.open('wb') as out:
        count = 0
        deadline = time.monotonic() + 60
        while chunk := response.read(256 * 1024):
            count += len(chunk)
            if count > 100 * 1024 * 1024 or time.monotonic() > deadline:
                raise ValueError('release_too_large')
            out.write(chunk)
    if count != asset['size']:
        raise ValueError('incomplete_download')
    info = ipa_info(destination)
    if info.get('CFBundleIdentifier') != bundle or info.get('CFBundleShortVersionString') != version:
        raise ValueError('release_identity_mismatch')


def ipa_info(path):
    with zipfile.ZipFile(path) as archive:
        names = [n for n in archive.namelist() if re.fullmatch(r'Payload/[^/]+\.app/Info.plist', n)]
        if len(names) != 1 or sum(i.file_size for i in archive.infolist()) > 1024**3:
            raise ValueError('invalid_ipa')
        if archive.getinfo(names[0]).file_size > 1024 * 1024:
            raise ValueError('invalid_ipa')
        return plistlib.loads(archive.read(names[0]))


@app.get('/health')
def health():
    return jsonify(status='ok')


@app.post('/ryuksign/sign')
def sign():
    if set(request.form) != {'version', 'bundleId', 'p12password'} or set(request.files) != {'p12', 'provision'}:
        return jsonify(error='bad_request'), 400
    if any(len(request.form.getlist(k)) != 1 for k in request.form) or any(len(request.files.getlist(k)) != 1 for k in request.files):
        return jsonify(error='bad_request'), 400
    version, bundle, password = (request.form[k] for k in ('version', 'bundleId', 'p12password'))
    if not re.fullmatch(r'\d{1,5}(?:\.\d{1,5}){1,3}', version):
        return jsonify(error='bad_version'), 400
    if bundle not in BUNDLES:
        return jsonify(error='bundle_not_allowed'), 400
    if len(password) > 1024 or '\0' in password:
        return jsonify(error='bad_cert'), 400
    if not BASE.startswith('https://'):
        return jsonify(error='not_configured'), 503
    if not lock.acquire(blocking=False):
        return jsonify(error='rate_limited'), 429
    output = None
    try:
        now = time.monotonic()
        while attempts and now - attempts[0] >= 300:
            attempts.popleft()
        if len(attempts) >= 10:
            return jsonify(error='rate_limited'), 429
        attempts.append(now)
        cleanup()
        if sum(1 for p in ROOT.iterdir() if p.is_dir()) >= 10:
            return jsonify(error='rate_limited'), 429
        with tempfile.TemporaryDirectory(prefix='korsign-sign-') as work:
            work = Path(work)
            for field, filename in [('p12', 'certificate.p12'), ('provision', 'profile.mobileprovision')]:
                request.files[field].save(work / filename)
                if not (work / filename).stat().st_size:
                    return jsonify(error='missing_' + field), 400
            fetch_release(version, bundle, work / 'input.ipa')
            result = subprocess.run([SIGNER, '-f', '-q', '-t', str(work), '-k', str(work/'certificate.p12'),
                                     '-p', password, '-m', str(work/'profile.mobileprovision'),
                                     '-o', str(work/'signed.ipa'), str(work/'input.ipa')],
                                    cwd=work, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                    timeout=120)
            if result.returncode or not (work/'signed.ipa').is_file():
                return jsonify(error='sign_failed'), 422
            info = ipa_info(work/'signed.ipa')
            if info.get('CFBundleIdentifier') != bundle or info.get('CFBundleShortVersionString') != version:
                raise ValueError('signed_identity_mismatch')
            token = secrets.token_hex(24)
            output = ROOT / token
            output.mkdir(mode=0o700)
            shutil.move(work/'signed.ipa', output/'app.ipa')
            manifest = {'items': [{'assets': [{'kind': 'software-package', 'url': f'{BASE}/files/{token}/app.ipa'}],
                'metadata': {'bundle-identifier': bundle, 'bundle-version': str(info['CFBundleVersion']),
                             'kind': 'software', 'title': info.get('CFBundleDisplayName', 'KorSign')}}]}
            (output/'manifest.plist').write_bytes(plistlib.dumps(manifest))
        install = 'itms-services://?action=download-manifest&url=' + urllib.parse.quote(f'{BASE}/files/{token}/manifest.plist', safe='')
        return jsonify(install=install)
    except urllib.error.HTTPError as error:
        return jsonify(error='unknown_version' if error.code == 404 else 'download_failed'), 404 if error.code == 404 else 502
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, subprocess.TimeoutExpired):
        if output:
            shutil.rmtree(output, ignore_errors=True)
        return jsonify(error='sign_failed'), 422
    finally:
        lock.release()


@app.get('/files/<token>/<filename>')
def files(token, filename):
    if not re.fullmatch(r'[0-9a-f]{48}', token) or filename not in ('app.ipa', 'manifest.plist'):
        abort(404)
    path = ROOT / token / filename
    if not path.is_file() or time.time() - path.parent.stat().st_mtime > TTL:
        abort(404)
    response = send_file(path, mimetype='application/octet-stream' if filename == 'app.ipa' else 'application/xml', conditional=True)
    response.headers['Cache-Control'] = 'no-store'
    return response


if __name__ == '__main__':
    cleanup()
