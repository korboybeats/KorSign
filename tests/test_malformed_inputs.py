"""Production AR parsing and signing metadata guards, using temporary inputs only."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
utilities = root / 'KorSign/Utilities'
archive = (utilities / 'Handlers/ArchiveExtraction.swift').read_text()
validation = archive[archive.index('\tstatic func validatePath'):archive.index('\n\tstatic func destination')]
signing = (utilities / 'Handlers/SigningHandler.swift').read_text()
start = signing.index('\t\tguard\n\t\t\tlet infoDictionary')
metadata = signing[start:signing.index('\n\t\tSigningLog.shared.info', start)]
program = '''import Foundation
enum ArchiveExtraction {
''' + validation + '''
}
enum SigningFileHandlerError: Error { case infoPlistNotFound }
func readMetadata(_ movedAppPath: URL) throws -> NSMutableDictionary {
''' + metadata + '''
    return infoDictionary
}
''' + r'''
@main struct Check {
    static func main() async throws {
        let root = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
        let file = root.appendingPathComponent("input.deb")
        func field(_ value: String, _ count: Int) -> String {
            value + String(repeating: " ", count: count - value.utf8.count)
        }
        func member(_ name: String, _ body: String) -> Data {
            let header = field(name, 16) + field("0", 12) + field("0", 6) + field("0", 6)
                + field("100644", 8) + field(String(body.utf8.count), 10) + "`\n"
            return Data((header + body + (body.utf8.count % 2 == 1 ? "\n" : "")).utf8)
        }
        let magic = Data("!<arch>\n".utf8)
        let valid = magic + member("data.tar", "hello")
        for data in [magic, valid, magic + member("empty", "") + member("data.tar", "even")] {
            try data.write(to: file)
            let files = try await AR(with: file).extract()
            assert(try Data(contentsOf: file) == data)
            if data == valid { assert(files.count == 1 && files[0].content == Data("hello".utf8)) }
            if data != magic && data != valid { assert(files.count == 2 && files[0].content.isEmpty) }
        }
        var bad = (0..<8).map { Data(valid.prefix($0)) }
        bad += [Data(valid.prefix(9)), Data(valid.prefix(30)), Data(valid.prefix(67)),
                Data(valid.prefix(70)), Data(valid.dropLast()), valid + Data("short".utf8)]
        for (offset, width, text) in [(48,10,"-1"), (48,10,"9999999999"), (48,10,"bad"),
                                     (16,12,"nan"), (16,12,"inf"), (16,12,"bad"),
                                     (28,6,"bad"), (34,6,"bad"), (40,8,"bad"), (0,16,"")] {
            var data = valid
            data.replaceSubrange(8 + offset..<8 + offset + width, with: Data(field(text, width).utf8))
            bad.append(data)
        }
        var badMarker = valid
        badMarker[66] = 0
        bad.append(badMarker)
        var nonASCII = valid
        nonASCII[8] = 0xff
        bad.append(nonASCII)
        for data in bad {
            try data.write(to: file)
            var rejected = false
            do { _ = try await AR(with: file).extract() } catch { rejected = true }
            assert(rejected)
            assert(try Data(contentsOf: file) == data)
        }

        let plist = root.appendingPathComponent("Info.plist")
        var rejected = false
        do { _ = try readMetadata(root) } catch SigningFileHandlerError.infoPlistNotFound { rejected = true }
        assert(rejected)
        for data in [Data(), Data("broken".utf8),
                     try PropertyListSerialization.data(fromPropertyList: ["array"], format: .xml, options: 0)] {
            try data.write(to: plist)
            rejected = false
            do { _ = try readMetadata(root) } catch SigningFileHandlerError.infoPlistNotFound { rejected = true }
            assert(rejected)
            assert(try Data(contentsOf: plist) == data)
        }
        for format in [PropertyListSerialization.PropertyListFormat.xml, .binary] {
            let data = try PropertyListSerialization.data(fromPropertyList: ["CFBundleIdentifier": "test.app"], format: format, options: 0)
            try data.write(to: plist)
            let dictionary = try readMetadata(root)
            assert(dictionary["CFBundleIdentifier"] as? String == "test.app")
            dictionary["CFBundleName"] = "Mutable"
            assert(dictionary["CFBundleName"] as? String == "Mutable")
            assert(try Data(contentsOf: plist) == data)
        }
        print("PASS: malformed DEB/header/number/padding and plist errors; valid members and XML/binary plists; input preservation")
    }
}
'''.replace('assert(try ', 'assert(try! ')
with tempfile.TemporaryDirectory(prefix='korsign-malformed-check-') as directory:
    work = Path(directory)
    source = work / 'Check.swift'
    source.write_text(program)
    binary = work / 'check'
    subprocess.run(['swiftc', '-parse-as-library', str(utilities / 'ARDecompression/AR.swift'),
                    str(utilities / 'ARDecompression/Models/ARFileModel.swift'),
                    str(source), '-o', str(binary)], check=True)
    subprocess.run([str(binary), directory], check=True)
