"""Build the iPhone transport update locally; preserve the pinned idevice C API.

Requires Xcode, rustup stable, and rustup target add aarch64-apple-ios.
Other XCFramework slices remain the upstream v0.1.57 binaries.
"""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
REVISION = '99ea020acabd0579375a09fd690261ea6ca37f68'
BASE_SHA = '40cd5c769b60d1879a96c9caa27666037f9d5321844addec40ae99727b142d10'
CACHE = ROOT / 'IDeviceKitten/.build'

def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path, help='Reuse an existing v0.1.57 source checkout/build cache')
parser.add_argument('--base-xcframework', type=Path, help='Reuse the verified upstream SwiftPM artifact')
args = parser.parse_args()
CACHE.mkdir(parents=True, exist_ok=True)
source = (args.source or CACHE / 'transport-source').resolve()
if not source.exists():
    run('git', 'clone', '--depth', '1', '--branch', 'v0.1.57', 'https://github.com/jkcoxson/idevice.git', str(source))
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip() == REVISION
# Apply each pinned patch once, refusing conflicting local changes.
for name in ('Cargo.lock.patch', 'transport.patch'):
    patch = Path(__file__).with_name(name)
    if subprocess.run(['git', 'apply', '--reverse', '--check', str(patch)], cwd=source, capture_output=True).returncode:
        run('git', 'apply', '--check', str(patch), cwd=source)
        run('git', 'apply', str(patch), cwd=source)
changes = subprocess.check_output(['git', 'diff', '--name-only'], cwd=source, text=True).splitlines()
assert sorted(changes) == ['Cargo.lock', 'ffi/src/tunnel_provider.rs', 'idevice/src/remote_pairing/tls_psk.rs'], changes
env = dict(os.environ)
env['RUSTC'] = subprocess.check_output(['rustup', 'which', '--toolchain', 'stable', 'rustc'], text=True).strip()
run('rustup', 'run', 'stable', 'cargo', 'test', '--locked', '-p', 'idevice', '--lib', '--features', 'full', 'write_tests', cwd=source, env=env)
sdk = subprocess.check_output(['xcrun', '--sdk', 'iphoneos', '--show-sdk-path'], text=True).strip()
env.update(BINDGEN_EXTRA_CLANG_ARGS='--sysroot=' + sdk, IPHONEOS_DEPLOYMENT_TARGET='17.0')
run('rustup', 'run', 'stable', 'cargo', 'build', '--locked', '--release', '--target', 'aarch64-apple-ios', '--features', 'obfuscate', cwd=source / 'ffi', env=env)
with tempfile.TemporaryDirectory(prefix='idevice-', dir=CACHE) as temporary:
    stage = Path(temporary)
    base = args.base_xcframework
    if base is None:
        archive = CACHE / 'idevice-v0.1.57.zip'
        if not archive.exists():
            urllib.request.urlretrieve('https://github.com/jkcoxson/idevice/releases/download/v0.1.57/IDevice.xcframework.zip', archive)
        assert hashlib.sha256(archive.read_bytes()).hexdigest() == BASE_SHA
        run('ditto', '-x', '-k', str(archive), str(stage / 'upstream'))
        base = stage / 'upstream/IDevice.xcframework'
    output = stage / 'IDevice.xcframework'
    shutil.copytree(base, output, symlinks=True)
    library = source / 'target/aarch64-apple-ios/release/libidevice_ffi.a'
    run('lipo', str(library), '-verify_arch', 'arm64')
    shutil.copy2(library, output / 'ios-arm64/libidevice_ffi.a')
    destination = CACHE / 'IDevice.xcframework'
    if destination.exists():
        shutil.rmtree(destination)
    shutil.move(output, destination)
    print('Built local iPhone transport: idevice v0.1.57 + jktcp 0.1.7 + TLS write fix + TCP_NODELAY')
