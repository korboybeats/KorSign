"""Bounded native patcher checks with disposable synthetic binaries and sanitizers."""
from pathlib import Path
import os
import struct
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
def thin(commands=None, subtype=2, count=1, size=None):
    if commands is None:
        commands = struct.pack('<6I', 0x32, 24, 2, 0x100000, 0x110000, 0)
    return struct.pack('<8I', 0xfeedfacf, 0x100000c, subtype, 6, count,
                       len(commands) if size is None else size, 0, 0) + commands

def fat(slices, endian='>'):
    offset = 8 + 20 * len(slices)
    table = struct.pack(endian + '2I', 0xcafebabe, len(slices))
    payload = b''
    for data in slices:
        table += struct.pack(endian + '5I', 0x100000c, 2, offset, len(data), 0)
        payload += data
        offset += len(data)
    return table + payload

with tempfile.TemporaryDirectory(prefix='korsign-macho-check-') as temporary:
    work = Path(temporary)
    driver = work / 'Check.m'
    driver.write_text('''#import "MachOUtils.h"
int main(int argc, const char **argv) {
    @autoreleasepool {
        NSString *error = argv[1][0] == 's' ? LCPatchMachOForSDK26(argv[2]) : LCPatchMachOFixupARM64eSlice(argv[2]);
        if (error) { fprintf(stderr, "%s\\n", error.UTF8String); return 1; }
        return 0;
    }
}
''')
    binary = work / 'check'
    source_dir = root / 'KorSign/Utilities/MachO'
    subprocess.run(['xcrun', 'clang', '-fmodules', '-fobjc-arc', '-g',
                    '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                    '-fmodules-cache-path=' + str(work / 'modules'),
                    '-framework', 'Foundation', '-I', str(source_dir),
                    str(source_dir / 'MachOUtils.m'), str(driver), '-o', str(binary)], check=True)
    env = dict(os.environ, ASAN_OPTIONS='detect_leaks=0')
    def run(data, mode, expected=None):
        target = work / 'fixture'
        target.write_bytes(data)
        target.chmod(0o755)
        result = subprocess.run([str(binary), mode, str(target)], env=env, capture_output=True)
        assert result.returncode == (1 if expected is None else 0), result.stderr.decode()
        assert b'Sanitizer' not in result.stderr and b'runtime error:' not in result.stderr, result.stderr
        assert target.read_bytes() == (data if expected is None else expected)
        assert target.stat().st_mode & 0o777 == 0o755

    valid = thin()
    patched = bytearray(valid)
    struct.pack_into('<I', patched, 32 + 16, 0x1a0000)
    run(valid, 'sdk', bytes(patched))
    run(valid, 'arm', valid)  # Thin binaries are not ARM64e slice-fix targets.
    no_build = thin(b'', count=0)
    run(no_build, 'sdk', no_build)
    run(no_build, 'arm', no_build)
    for endian in ['>', '<']:
        universal = fat([valid, valid], endian)
        sdk = bytearray(universal)
        arm = bytearray(universal)
        for index in range(2):
            offset = 48 + index * len(valid)
            struct.pack_into('<I', sdk, offset + 32 + 16, 0x1a0000)
            struct.pack_into('<I', arm, offset + 8, 0x80000002)
            struct.pack_into(endian + 'I', arm, 8 + index * 20 + 4, 0x80000002)
        run(universal, 'sdk', bytes(sdk))
        run(universal, 'arm', bytes(arm))
        run(bytes(arm), 'arm', bytes(arm))  # Idempotent.

    invalid = [b'', b'\xcf', b'not a binary', valid[:20],
               thin(size=500), thin(count=100),
               thin(struct.pack('<2I', 0x32, 0)),
               thin(struct.pack('<2I', 0x32, 8)),
               thin(struct.pack('<2I', 0x32, 0xffffffff)),
               thin(struct.pack('<6I', 0x32, 24, 2, 0, 0, 1)),
               struct.pack('>2I', 0xcafebabe, 100),
               struct.pack('>2I', 0xcafebabe, 1) + b'\0' * 20,
               fat([valid, valid[:20]])]
    past_end = bytearray(fat([valid]))
    struct.pack_into('>I', past_end, 16, 0xfffffff0)
    invalid.append(bytes(past_end))
    overlapping = bytearray(fat([valid, valid]))
    struct.pack_into('>I', overlapping, 36, 48)
    invalid.append(bytes(overlapping))
    # Commands may not consume bytes belonging to a later slice.
    cross_slice = bytearray(fat([valid, valid]))
    struct.pack_into('>I', cross_slice, 20, 32)
    invalid.append(bytes(cross_slice))
    # A valid patch command followed by a malformed one must leave the file intact.
    invalid.append(thin(valid[32:] + struct.pack('<2I', 1, 0), count=2))
    for data in invalid:
        run(data, 'sdk')
        run(data, 'arm')
    missing = subprocess.run([str(binary), 'sdk', str(work / 'missing')], env=env, capture_output=True)
    assert missing.returncode == 1
    print('PASS: native bounds, no partial validation writes, valid SDK/ARM64e patches, endian variants, idempotence and permissions (ASan/UBSan)')

# Exercise the production Swift callers with deterministic native results.
source = (root / 'KorSign/Utilities/Handlers/SigningHandler.swift').read_text()
def method(name, next_name):
    start = source.index('\tprivate func ' + name)
    end = source.index('\n\tprivate func ' + next_name, start)
    return source[start:end].replace('private func', 'func')
callers = method('_locateMachosAndChangeToSDK26', '_locateCodeSignatureDirectories')
callers += method('_locateMachosAndFixupArm64eSlice', '_enumerateFiles')
program = r'''
import Foundation
struct Bundle {
    let url: URL
    init?(url: URL) { self.url = url }
    var executableURL: URL? { url.appendingPathComponent("binary") }
}
var paths: [String] = []
var failure: String? = nil
func LCPatchMachOForSDK26(_ path: String) -> String? { paths.append(path); return failure }
func LCPatchMachOFixupARM64eSlice(_ path: String) -> String? { paths.append(path); return failure }
final class Handler {
    var files: [URL] = []
    func _enumerateFiles(at url: URL, where predicate: (String) -> Bool) -> [URL] { files }
''' + callers + r'''
}
@main struct Check {
    static func main() async throws {
        let app = URL(fileURLWithPath: "/temporary/Test.app")
        let handler = Handler()
        try await handler._locateMachosAndChangeToSDK26(for: app)
        assert(paths == [app.appendingPathComponent("binary").path])
        for framework in [false, true] {
            paths = []
            failure = "Invalid native input"
            let first = app.appendingPathComponent(framework ? "Test.framework" : "first.dylib")
            handler.files = [first, app.appendingPathComponent("second.dylib")]
            var rejected = false
            do { try await handler._locateMachosAndFixupArm64eSlice(for: app) }
            catch { rejected = true; assert(error.localizedDescription == failure) }
            assert(rejected && paths.count == 1)
            assert(paths[0] == (framework ? first.appendingPathComponent("binary") : first).path)
        }
        var rejected = false
        do { try await handler._locateMachosAndChangeToSDK26(for: app) }
        catch { rejected = true }
        assert(rejected)
        print("PASS: production Swift callers propagate native failures and use the executable path directly")
    }
}
'''
with tempfile.TemporaryDirectory(prefix='korsign-macho-callers-') as temporary:
    work = Path(temporary)
    main = work / 'Check.swift'
    main.write_text(program)
    binary = work / 'check'
    subprocess.run(['swiftc', '-parse-as-library', str(main), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
