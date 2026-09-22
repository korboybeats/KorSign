"""Offline archive-boundary checks using pinned, locally cached dependencies.

Run on macOS; optionally pass --checkouts /path/to/SourcePackages/checkouts.
Everything compiled or extracted is kept in one disposable temporary directory.
"""
import argparse
import io
import gzip
import lzma
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import zipfile
import struct
import zlib
import random

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--checkouts', type=Path,
                    default=Path(tempfile.gettempdir()) / 'KorSign/SourcePackages/checkouts')
args = parser.parse_args()
pins = json.loads((root / 'KorSign.xcodeproj/project.xcworkspace/xcshareddata/swiftpm/Package.resolved').read_text())['pins']
for name in ['BitByteData', 'SWCompression']:
    package = args.checkouts / name
    revision = next(p['state']['revision'] for p in pins if p['identity'] == name.lower())
    assert subprocess.check_output(['git', '-C', str(package), 'rev-parse', 'HEAD'], text=True).strip() == revision
    assert not subprocess.check_output(['git', '-C', str(package), 'status', '--porcelain'], text=True).strip()

with tempfile.TemporaryDirectory(prefix='korsign-archive-check-') as temporary:
    work = Path(temporary)
    # Synthetic archives only; no user data or credentials.
    valid = [('Payload/Test.app/', b''), ('Payload/Test.app/file', b'hello')]
    def zip_fixture(name, entries):
        with zipfile.ZipFile(work / name, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for path, data in entries:
                archive.writestr(path, data)
    zip_fixture('valid.ipa', valid)
    large = bytes(range(256)) * 4097
    zip_fixture('large.ipa', [('Payload/Test.app/file', large)])
    with zipfile.ZipFile(work / 'mixed.zip', 'w') as archive:
        for index in range(8):
            archive.writestr(f'stored-{index}', b'x' * (index + 1), compress_type=zipfile.ZIP_STORED)
        archive.writestr('large-deflated', large, compress_type=zipfile.ZIP_DEFLATED)
    def raw_fixture(name, data, payload=None, declared_size=None):
        compressor = zlib.compressobj(wbits=-15)
        compressed = compressor.compress(data) + compressor.flush() if payload is None else payload
        size = len(data) if declared_size is None else declared_size
        crc = zlib.crc32(data)
        filename = b'file'
        header = struct.pack('<IHHHHHIIIHH', 0x04034b50, 20, 0, 8, 0, 0, crc, len(compressed), size, len(filename), 0) + filename
        central = struct.pack('<IHHHHHHIIIHHHHHII', 0x02014b50, 20, 20, 0, 8, 0, 0, crc, len(compressed), size, len(filename), 0, 0, 0, 0, 0, 0) + filename
        end = struct.pack('<IHHHHIIH', 0x06054b50, 0, 0, 1, 1, len(central), len(header)+len(compressed), 0)
        (work/name).write_bytes(header+compressed+central+end)
        return compressed
    fixture_data = random.Random(42).randbytes(1024 * 1024 + 17)
    (work/'fixture-data').write_bytes(fixture_data)
    compressed = raw_fixture('random.zip', fixture_data)
    raw_fixture('empty.zip', b'')
    raw_fixture('truncated.zip', fixture_data, payload=compressed[:-7])
    raw_fixture('trailing.zip', fixture_data, payload=compressed+b'junk')
    raw_fixture('invalid-deflate.zip', fixture_data, payload=b'\x07' * 20)
    raw_fixture('size-small.zip', fixture_data, payload=compressed, declared_size=len(fixture_data)-1)
    raw_fixture('size-large.zip', fixture_data, payload=compressed, declared_size=len(fixture_data)+1)
    class Unseekable(io.BytesIO):
        def seekable(self): return False
        def seek(self, *args): raise OSError('not seekable')
    for use_zip64 in [False, True]:
        for descriptor in [False, True]:
            stream = Unseekable() if descriptor else io.BytesIO()
            with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
                with archive.open('file', 'w', force_zip64=use_zip64) as entry:
                    entry.write(fixture_data)
            (work / f'compat-{int(use_zip64)}-{int(descriptor)}.zip').write_bytes(stream.getvalue())
    def zip64_sizes(name, sizes):
        body = bytearray(); central = bytearray()
        for index, size in enumerate(sizes):
            filename = f'file-{index}'.encode()
            packed = b'\x03\x00'  # Empty raw DEFLATE.
            extra = struct.pack('<HHQQ', 1, 16, size, len(packed))
            offset = len(body)
            body += struct.pack('<IHHHHHIIIHH', 0x04034b50, 45, 0, 8, 0, 0, 0, 0xffffffff, 0xffffffff, len(filename), len(extra)) + filename + extra + packed
            central += struct.pack('<IHHHHHHIIIHHHHHII', 0x02014b50, 45, 45, 0, 8, 0, 0, 0, 0xffffffff, 0xffffffff, len(filename), len(extra), 0, 0, 0, 0, offset) + filename + extra
        end = struct.pack('<IHHHHIIH', 0x06054b50, 0, 0, len(sizes), len(sizes), len(central), len(body), 0)
        end64 = struct.pack('<IQHHIIQQQQ', 0x06064b50, 44, 45, 45, 0, 0, len(sizes), len(sizes), len(central), len(body))
        locator = struct.pack('<IIQI', 0x07064b50, 0, len(body)+len(central), 1)
        (work/name).write_bytes(body+central+end64+locator+end)
    zip64_sizes('zip64-central.zip', [0])
    zip64_sizes('oversized.zip', [2**63])
    zip64_sizes('overflow-total.zip', [2**62, 2**62])
    zip_fixture('valid.tipa', valid)
    zip_fixture('backup.zip', [('Backup/manifest.json', b'{}')])
    zip_fixture('tweak.zip', [('Example.framework/file', b'hello')])
    zip_fixture('bad.zip', valid + [('../sentinel', b'changed')])
    zip_fixture('collision.zip', [('input.zip', b'changed')])
    zip_fixture('duplicate.zip', [('file', b'first'), ('./file', b'second')])
    link = zipfile.ZipInfo('link')
    link.create_system = 3
    link.external_attr = 0o120777 << 16
    zip_fixture('safe-link.zip', [('folder/file', b'hello'), (link, b'folder/file')])
    zip_fixture('bad-link.zip', [(link, b'../sentinel')])
    zip_fixture('existing-link.zip', [('redirect/sentinel', b'changed')])
    zip_fixture('late-existing-link.zip', [('safe/file', b'hello'), ('redirect/sentinel', b'changed')])
    # Stored bytes are changed after ZIP creation to verify CRC rejection.
    with zipfile.ZipFile(work / 'crc.zip', 'w') as archive:
        archive.writestr('file', b'hello' + large)
    corrupt = (work / 'crc.zip').read_bytes().replace(b'hello', b'jello', 1)
    (work / 'crc.zip').write_bytes(corrupt)
    for name, paths in [('valid.tar', ['./', './Library/', './Library/file']),
                        ('bad.tar', ['./Library/file', '../sentinel'])]:
        with tarfile.open(work / name, 'w', format=tarfile.USTAR_FORMAT) as archive:
            for path in paths:
                entry = tarfile.TarInfo(path)
                if path.endswith('/'):
                    entry.type = tarfile.DIRTYPE
                    archive.addfile(entry)
                else:
                    entry.size = 5
                    archive.addfile(entry, io.BytesIO(b'hello'))
    (work / 'compressed.tar.gz').write_bytes(gzip.compress((work / 'valid.tar').read_bytes()))
    (work / 'compressed.tar.xz').write_bytes(lzma.compress((work / 'valid.tar').read_bytes()))
    def ar_fixture(name, member):
        header = f'{member:<16}{0:<12}{0:<6}{0:<6}{644:<8}{5:<10}`\n'.encode('ascii')
        (work / name).write_bytes(b'!<arch>\n' + header + b'hello\n')
    ar_fixture('valid.deb', 'data.tar')
    ar_fixture('bad.deb', '../sentinel')

    # Compile source modules directly: no SwiftPM resolution, scripts, or network.
    for name in ['ZIPFoundation', 'BitByteData', 'SWCompression']:
        source_dir = (root / name if name == 'ZIPFoundation' else args.checkouts / name) / 'Sources'
        if name == 'ZIPFoundation':
            source_dir /= name
        sources = sorted(p for p in source_dir.rglob('*.swift') if 'swcomp' not in p.parts)
        subprocess.run(['swiftc', '-swift-version', '5', '-emit-library', '-emit-module',
                        '-module-name', name, '-I', str(work), '-L', str(work),
                        *(['-lBitByteData'] if name == 'SWCompression' else []),
                        *map(str, sources), '-o', str(work / f'lib{name}.dylib'),
                        '-emit-module-path', str(work / f'{name}.swiftmodule')], check=True)
    main = work / 'Check.swift'
    main.write_text(r'''
import Foundation
import ZIPFoundation

enum TweakHandlerError: Error { case unsupportedFileExtension(String) }
@main struct Check {
    static func main() async throws {
        let fm = FileManager.default
        let root = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
        let sentinel = root.appendingPathComponent("sentinel")
        try Data("untouched".utf8).write(to: sentinel)
        for path in ["", "/absolute", "../sentinel", "a/../../sentinel", "a\\b", "C:/file", "a\0b"] {
            do { try ArchiveExtraction.validatePath(path); assertionFailure("Accepted invalid name") }
            catch {}
        }
        // Extraction through a symlinked working-directory alias stays supported.
        let actualRoot = root.appendingPathComponent("actual-root")
        let aliasRoot = root.appendingPathComponent("alias-root")
        try fm.createDirectory(at: actualRoot, withIntermediateDirectories: true)
        try fm.createSymbolicLink(at: aliasRoot, withDestinationURL: actualRoot)
        try ArchiveExtraction.unzip(root.appendingPathComponent("valid.ipa"), to: aliasRoot)
        assert(try Data(contentsOf: actualRoot.appendingPathComponent("Payload/Test.app/file")) == Data("hello".utf8))
        // A link introduced after preflight must still be rejected before writing.
        let changingRoot = root.appendingPathComponent("changing-root")
        try fm.createDirectory(at: changingRoot, withIntermediateDirectories: true)
        var rejectedNewLink = false
        do {
            try ArchiveExtraction.unzip(root.appendingPathComponent("existing-link.zip"), to: changingRoot, progress: { fraction in
                if fraction == 0 {
                    try! fm.createSymbolicLink(at: changingRoot.appendingPathComponent("redirect"), withDestinationURL: root)
                }
            })
        } catch { rejectedNewLink = true }
        assert(rejectedNewLink)
        assert(try Data(contentsOf: sentinel) == Data("untouched".utf8))
        for bufferSize in [16 * 1024, 256 * 1024, 512 * 1024, 1024 * 1024] {
        for useZlib in [false, true] {
        for name in ["zip64-central.zip", "compat-0-0.zip", "compat-0-1.zip", "compat-1-0.zip", "compat-1-1.zip", "empty.zip", "random.zip", "mixed.zip", "large.ipa", "valid.ipa", "valid.tipa", "backup.zip", "tweak.zip", "safe-link.zip"] {
            let output = root.appendingPathComponent(UUID().uuidString)
            try fm.createDirectory(at: output, withIntermediateDirectories: true)
            var progress: [Double] = []
            var profile = ""
            try ArchiveExtraction.unzip(root.appendingPathComponent(name), to: output, bufferSize: bufferSize, useZlib: useZlib, profile: { profile = $0 }) { progress.append($0) }
            assert(profile.contains("decoder=\(useZlib ? "zlib" : "apple")"))
            assert(profile.contains("completed=true") && profile.contains("total="))
            assert(progress.first == 0 && progress.last == 1)
            assert(progress.count <= 102 && progress == progress.sorted())
            if name.hasPrefix("valid") {
                assert(try Data(contentsOf: output.appendingPathComponent("Payload/Test.app/file")) == Data("hello".utf8))
            }
            if name == "large.ipa" {
                let expected = Data((0..<(256 * 4097)).map { UInt8($0 % 256) })
                assert(try Data(contentsOf: output.appendingPathComponent("Payload/Test.app/file")) == expected)
            }
            if name == "safe-link.zip" {
                assert(try fm.destinationOfSymbolicLink(atPath: output.appendingPathComponent("link").path) == "folder/file")
            }
        }
        }
        for name in ["bad.zip", "collision.zip", "duplicate.zip", "bad-link.zip", "existing-link.zip", "late-existing-link.zip", "crc.zip", "truncated.zip", "trailing.zip", "invalid-deflate.zip", "size-small.zip", "size-large.zip", "oversized.zip", "overflow-total.zip"] {
            let output = root.appendingPathComponent(UUID().uuidString)
            try fm.createDirectory(at: output, withIntermediateDirectories: true)
            try Data("original".utf8).write(to: output.appendingPathComponent("input.zip"))
            if name == "existing-link.zip" || name == "late-existing-link.zip" {
                try fm.createSymbolicLink(at: output.appendingPathComponent("redirect"), withDestinationURL: root)
            }
            var rejected = false
            do { try ArchiveExtraction.unzip(root.appendingPathComponent(name), to: output, bufferSize: bufferSize, useZlib: true) }
            catch { rejected = true }
            assert(rejected, "Accepted \(name)")
            assert(try Data(contentsOf: sentinel) == Data("untouched".utf8))
            assert(try Data(contentsOf: output.appendingPathComponent("input.zip")) == Data("original".utf8))
            if name == "bad.zip" { assert(!fm.fileExists(atPath: output.appendingPathComponent("Payload").path)) }
        }
        }
        // Separate archive handles may decode concurrently without sharing stream state.
        try await withThrowingTaskGroup(of: Void.self) { group in
            for _ in 0..<4 {
                group.addTask {
                    let output = root.appendingPathComponent(UUID().uuidString)
                    try fm.createDirectory(at: output, withIntermediateDirectories: true)
                    try ArchiveExtraction.unzip(root.appendingPathComponent("random.zip"), to: output, bufferSize: 256 * 1024, useZlib: true)
                }
            }
            try await group.waitForAll()
        }
        let archive = try Archive(url: root.appendingPathComponent("random.zip"), accessMode: .read)
        let entry = Array(archive)[0]
        var retainedChunks: [Data] = []
        let retainedCRC = try archive.extract(entry, bufferSize: 16 * 1024, useZlib: true, consumer: { retainedChunks.append($0) })
        assert(retainedCRC == entry.checksum)
        assert(retainedChunks.reduce(into: Data()) { $0.append($1) } == (try! Data(contentsOf: root.appendingPathComponent("fixture-data"))))
        let cancelled = Progress(totalUnitCount: 1)
        cancelled.cancel()
        var rejectedCancel = false
        do { _ = try archive.extract(entry, useZlib: true, progress: cancelled, consumer: { _ in fatalError("Consumed after cancellation") }) }
        catch Archive.ArchiveError.cancelledOperation { rejectedCancel = true }
        assert(rejectedCancel)
        enum SinkFailure: Error { case failed }
        var rejectedSink = false
        do { _ = try archive.extract(entry, useZlib: true, consumer: { _ in throw SinkFailure.failed }) }
        catch SinkFailure.failed { rejectedSink = true }
        assert(rejectedSink)
        assert(try archive.extract(entry, useZlib: true, consumer: { _ in }) == entry.checksum)
        for name in ["valid.tar", "bad.tar"] {
            var source = root.appendingPathComponent(name)
            let original = source
            let before = try fm.contentsOfDirectory(atPath: root.path).sorted()
            var rejected = false
            do { try extractFile(at: &source) } catch { rejected = true }
            assert(rejected == (name == "bad.tar"))
            if rejected {
                assert(source == original)
                assert(try fm.contentsOfDirectory(atPath: root.path).sorted() == before)
            } else {
                assert(try Data(contentsOf: source.appendingPathComponent("Library/file")) == Data("hello".utf8))
            }
        }
        for name in ["compressed.tar.gz", "compressed.tar.xz"] {
            var source = root.appendingPathComponent(name)
            try extractFile(at: &source)
            try extractFile(at: &source)
            assert(try Data(contentsOf: source.appendingPathComponent("Library/file")) == Data("hello".utf8))
        }
        for name in ["valid.deb", "bad.deb"] {
            var rejected = false
            do { _ = try await AR(with: root.appendingPathComponent(name)).extract() }
            catch { rejected = true }
            assert(rejected == (name == "bad.deb"))
        }
        print("PASS: ZIP/TAR/DEB paths, relative symlink, external links, collisions, CRC, progress, and input preservation")
    }
}
'''.replace('assert(try ', 'assert(try! '))
    production = ['Handlers/ArchiveExtraction.swift', 'ARDecompression/Decompression.swift',
                  'ARDecompression/AR.swift', 'ARDecompression/Models/ARFileModel.swift']
    binary = work / 'check'
    subprocess.run(['swiftc', '-swift-version', '5', '-parse-as-library', '-I', str(work), '-L', str(work),
                    '-lZIPFoundation', '-lSWCompression', '-lBitByteData',
                    '-Xlinker', '-rpath', '-Xlinker', str(work),
                    *(str(root / 'KorSign/Utilities' / p) for p in production), str(main), '-o', str(binary)], check=True)
    subprocess.run([str(binary), str(work)], check=True, timeout=60)
