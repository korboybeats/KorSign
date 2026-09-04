"""python test_signer.py /path/to/zsign /path/to/KorSign.ipa

Uses disposable, untrusted certificates. Never installs or trusts them.
"""
import datetime
import plistlib
import struct
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

signer, ipa = (str(Path(p).resolve()) for p in sys.argv[1:])
with tempfile.TemporaryDirectory(prefix='korsign-signer-check-') as tmp:
    work = Path(tmp)

    def run(*args):
        return subprocess.run(args, cwd=work, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, check=True, timeout=120)

    # The issuer name exercises Zsign's Apple-chain selection. The key is fake;
    # neither this CA nor its leaf is trusted by Apple or installed in a keychain.
    issuer = '/CN=Apple Worldwide Developer Relations Certification Authority/OU=G3/O=Apple Inc./C=US'
    run('openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', 'ca.key',
        '-out', 'ca.pem', '-days', '1', '-subj', issuer)
    run('openssl', 'req', '-new', '-newkey', 'rsa:2048', '-nodes', '-keyout', 'key.pem',
        '-out', 'test.csr', '-subj', '/CN=KorSign Disposable Test/OU=TESTONLY00')
    for supported in (False, True):
        if supported:
            run('openssl', 'x509', '-req', '-in', 'test.csr', '-CA', 'ca.pem',
                '-CAkey', 'ca.key', '-CAcreateserial', '-out', 'cert.pem', '-days', '1')
        else:
            run('openssl', 'x509', '-req', '-in', 'test.csr', '-signkey', 'key.pem',
                '-out', 'cert.pem', '-days', '1')
        run('openssl', 'pkcs12', '-export', '-inkey', 'key.pem', '-in', 'cert.pem',
            '-out', 'test.p12', '-passout', 'pass:test-only')
        run('openssl', 'x509', '-in', 'cert.pem', '-outform', 'DER', '-out', 'cert.der')
        profile = {'Name': 'Disposable test - NOT installable',
                   'TeamIdentifier': ['TESTONLY00'], 'ApplicationIdentifierPrefix': ['TESTONLY00'],
                   'ExpirationDate': datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) + datetime.timedelta(days=1),
                   'DeveloperCertificates': [(work/'cert.der').read_bytes()],
                   'Entitlements': {'application-identifier': 'TESTONLY00.*',
                                    'com.apple.developer.team-identifier': 'TESTONLY00',
                                    'keychain-access-groups': ['TESTONLY00.*']}}
        (work/'profile.plist').write_bytes(plistlib.dumps(profile))
        run('openssl', 'cms', '-sign', '-nodetach', '-binary', '-in', 'profile.plist',
            '-signer', 'cert.pem', '-inkey', 'key.pem', '-outform', 'DER', '-out', 'test.mobileprovision')
        output = work/'signed.ipa'
        output.unlink(missing_ok=True)
        result = subprocess.run([signer, '-q', '-f', '-t', tmp, '-k', str(work/'test.p12'),
                                 '-p', 'test-only', '-m', str(work/'test.mobileprovision'),
                                 '-o', str(output), ipa], stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, timeout=120)
        if not supported:
            assert result.returncode != 0 and not output.exists(), 'CMS failure was reported as success'
            continue
        assert result.returncode == 0
        with zipfile.ZipFile(output) as archive:
            assert archive.testzip() is None
            for name in archive.namelist():
                if not name.endswith(('.app/Info.plist', '.appex/Info.plist', '.framework/Info.plist')):
                    continue
                info = plistlib.loads(archive.read(name))
                data = archive.read(name.rsplit('/', 1)[0] + '/' + info['CFBundleExecutable'])
                assert data[:4] == b'\xcf\xfa\xed\xfe', 'Expected shipped arm64 Mach-O'
                offset, signature = 32, None
                for _ in range(struct.unpack_from('<I', data, 16)[0]):
                    command, size = struct.unpack_from('<II', data, offset)
                    if command == 0x1d:
                        start, length = struct.unpack_from('<II', data, offset + 8)
                        signature = data[start:start+length]
                    offset += size
                assert signature is not None
                blobs = {}
                for i in range(struct.unpack_from('>I', signature, 8)[0]):
                    slot, offset = struct.unpack_from('>II', signature, 12 + i*8)
                    length = struct.unpack_from('>I', signature, offset+4)[0]
                    blobs[slot] = signature[offset:offset+length]
                assert len(blobs.get(65536, b'')) > 8, 'Missing CMS signature'
                (work/'cms.der').write_bytes(blobs[65536][8:])
                (work/'directory.bin').write_bytes(blobs[0])
                run('openssl', 'cms', '-verify', '-binary', '-noverify', '-inform', 'DER',
                    '-in', 'cms.der', '-content', 'directory.bin', '-out', 'verified.bin')
print('PASS: unsupported issuer fails; host/nested CMS signatures verify with disposable keys')
