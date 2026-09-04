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

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--checkouts', type=Path,
                    default=Path(tempfile.gettempdir()) / 'KorSign/SourcePackages/checkouts')
args = parser.parse_args()
pins = json.loads((root / 'KorSign.xcodeproj/project.xcworkspace/xcshareddata/swiftpm/Package.resolved').read_text())['pins']
for name in ['ZIPFoundation', 'BitByteData', 'SWCompression']:
    package = args.checkouts / name
    revision = next(p['state']['revision'] for p in pins if p['identity'] == name.lower())
    assert subprocess.check_output(['git', '-C', str(package), 'rev-parse', 'HEAD'], text=True).strip() == revision
    assert not subprocess.check_output(['git', '-C', str(package), 'status', '--porcelain'], text=True).strip()

with tempfile.TemporaryDirectory(prefix='korsign-archive-check-') as temporary:
    work = Path(temporary)
    # Tiny synthetic archives only; no user data or credentials.
    valid = [('Payload/Test.app/', b''), ('Payload/Test.app/file', b'hello')]
    def zip_fixture(name, entries):
        with zipfile.ZipFile(work / name, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for path, data in entries:
                archive.writestr(path, data)
    zip_fixture('valid.ipa', valid)
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
    # Stored bytes are changed after ZIP creation to verify CRC rejection.
    with zipfile.ZipFile(work / 'crc.zip', 'w') as archive:
        archive.writestr('file', b'hello')
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
        source_dir = args.checkouts / name / 'Sources'
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
        for name in ["valid.ipa", "valid.tipa", "backup.zip", "tweak.zip", "safe-link.zip"] {
            let output = root.appendingPathComponent(UUID().uuidString)
            try fm.createDirectory(at: output, withIntermediateDirectories: true)
            var progress: [Double] = []
            try ArchiveExtraction.unzip(root.appendingPathComponent(name), to: output) { progress.append($0) }
            assert(progress.first == 0 && progress.last == 1)
            assert(progress.count <= 102 && progress == progress.sorted())
            if name.hasPrefix("valid") {
                assert(try Data(contentsOf: output.appendingPathComponent("Payload/Test.app/file")) == Data("hello".utf8))
            }
            if name == "safe-link.zip" {
                assert(try fm.destinationOfSymbolicLink(atPath: output.appendingPathComponent("link").path) == "folder/file")
            }
        }
        for name in ["bad.zip", "collision.zip", "duplicate.zip", "bad-link.zip", "existing-link.zip", "crc.zip"] {
            let output = root.appendingPathComponent(UUID().uuidString)
            try fm.createDirectory(at: output, withIntermediateDirectories: true)
            try Data("original".utf8).write(to: output.appendingPathComponent("input.zip"))
            if name == "existing-link.zip" {
                try fm.createSymbolicLink(at: output.appendingPathComponent("redirect"), withDestinationURL: root)
            }
            var rejected = false
            do { try ArchiveExtraction.unzip(root.appendingPathComponent(name), to: output) }
            catch { rejected = true }
            assert(rejected, "Accepted \(name)")
            assert(try Data(contentsOf: sentinel) == Data("untouched".utf8))
            assert(try Data(contentsOf: output.appendingPathComponent("input.zip")) == Data("original".utf8))
            if name == "bad.zip" { assert(!fm.fileExists(atPath: output.appendingPathComponent("Payload").path)) }
        }
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
    subprocess.run([str(binary), str(work)], check=True)
