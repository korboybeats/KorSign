"""Production shared-file/certificate staging branches with delayed fake consumers."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
app = (root / 'KorSign/KorSignApp.swift').read_text()
a = app.index('let tempDir = FileManager.default.uniqueTemporaryDirectory("FeatherShared")')
b = app.index('// Tweak files shared into the app', a)
ipa = app[a:b]
ipa = ipa[:ipa.rfind('\n\t\t\t}')]
a = app.index('let generator = UINotificationFeedbackGenerator()', app.index('if url.host == "import-certificate"'))
b = app.index('/// feather://export-certificate', a)
cert = app[a:b]
cert = cert[:cert.rfind('\n\t\t\t}')]
a = app.index('\tprivate func _importSharedTweak')
b = app.index('\n\t\tif ext == "zip"', a)
tweak = app[a:b].replace('private func', 'func') + '\n\t\ttry? FileManager.default.removeItem(at: tempDir)\n}\n'
tweak = tweak.replace('FileManager.default.temporaryDirectory', 'testRoot')
shortcuts = (root / 'NimbleKit/Sources/NimbleExtensions/FileManager/FileManager+shortcuts.swift').read_text()
a = shortcuts.index('\tpublic func decodeAndWrite')
b = shortcuts.index('\n\t// FeatherTweak', a)
decode = shortcuts[a:b].replace('public ', '').replace('self.temporaryDirectory', 'testRoot')
program = r'''
import Foundation
let fm = FileManager.default
var testRoot: URL!
extension FileManager {
    func uniqueTemporaryDirectory(_ label: String) -> URL { testRoot.appendingPathComponent(label + UUID().uuidString) }
''' + decode + r'''
}
// Coordination modes exercise partial copy failure, coordination failure and no accessor.
class NSFileCoordinator {
    enum ReadingOptions { case withoutChanges }
    static var mode = 0
    func coordinate(readingItemAt url: URL, options: ReadingOptions, error: UnsafeMutablePointer<NSError?>?, byAccessor: (URL) -> Void) {
        if Self.mode == 1 { byAccessor(url.appendingPathComponent("missing")); return }
        if Self.mode == 3 { return }
        byAccessor(url)
        if Self.mode == 2 { error?.pointee = CocoaError(.fileReadNoPermission) as NSError }
    }
}
extension String { static func localized(_ value: String, arguments: CVarArg...) -> String { value } }
enum UIAlertController {
    static func showErrorWithCopy(title: String, message: String) {}
    static func showAlertWithOk(title: String, message: String) {}
}
enum Toast {
    enum Duration { case long }
    static func error(_ value: String, duration: Duration) {}
    static func success(_ value: String, systemImage: String) {}
}
final class UINotificationFeedbackGenerator {
    enum Kind { case error, success }
    func prepare() {}
    func notificationOccurred(_ kind: Kind) {}
}
final class DownloadManager {
    static let shared = DownloadManager()
    var input: URL?
    var completion: ((Error?) -> Void)?
    func startArchive(from url: URL, id: String, completion: @escaping (Error?) -> Void) -> Int {
        input = url; self.completion = completion; return 1
    }
}
enum FR {
    static var valid = true
    static var inputs: [URL] = []
    static var completion: ((Error?) -> Void)?
    static func checkPasswordForCertificate(for key: URL, with password: String, using provision: URL) -> Bool { valid }
    static func handleCertificateFiles(p12URL: URL, provisionURL: URL, p12Password: String, completion: @escaping (Error?) -> Void) {
        inputs = [p12URL, provisionURL]; Self.completion = completion
    }
}
func importIPA(_ url: URL) {
''' + ipa + '\n}\nfunc importCert(_ p12Base64: String, _ provisionBase64: String, _ password: String) {\n' + cert + '\n}\n' + tweak + r'''
func waitRemoved(_ url: URL) {
    for _ in 0..<2000 {
        if !fm.fileExists(atPath: url.path) { return }
        Thread.sleep(forTimeInterval: 0.001)
    }
    fatalError("Staging remained")
}
@main struct Check {
    static func main() throws {
        testRoot = URL(fileURLWithPath: CommandLine.arguments[1])
        let original = testRoot.appendingPathComponent("original.ipa")
        try Data("original".utf8).write(to: original)
        for mode in 1...3 {
            NSFileCoordinator.mode = mode
            importIPA(original)
            _importSharedTweak(original)
            assert(DownloadManager.shared.completion == nil)
            assert(try! fm.contentsOfDirectory(atPath: testRoot.path).allSatisfy { !$0.hasPrefix("FeatherShared") })
        }
        NSFileCoordinator.mode = 0
        for error: Error? in [nil, CocoaError(.fileReadCorruptFile)] {
            importIPA(original)
            let input = DownloadManager.shared.input!
            assert(try! Data(contentsOf: input) == Data("original".utf8))
            DownloadManager.shared.completion?(error)
            DownloadManager.shared.completion = nil
            waitRemoved(input.deletingLastPathComponent())
            assert(try! Data(contentsOf: original) == Data("original".utf8))
        }
        let data = Data("certificate fixture".utf8).base64EncodedString()
        for invalidProvision in [true, false] {
            FR.valid = false
            importCert(data, invalidProvision ? "bad!" : data, "pw")
            assert(FR.completion == nil)
            assert(try! fm.contentsOfDirectory(atPath: testRoot.path).allSatisfy { !$0.hasSuffix(".p12") && !$0.hasSuffix(".mobileprovision") })
        }
        FR.valid = true
        for error: Error? in [nil, CocoaError(.fileWriteUnknown)] {
            importCert(data, data, "pw")
            assert(FR.inputs.count == 2 && FR.inputs.allSatisfy { fm.fileExists(atPath: $0.path) })
            FR.completion?(error)
            FR.completion = nil
            for input in FR.inputs { waitRemoved(input) }
        }
        // Real write failure returns nil instead of a URL that was never written.
        let base = testRoot!
        testRoot = original // An ordinary file cannot be a staging parent.
        assert(fm.decodeAndWrite(base64: data, pathComponent: ".p12") == nil)
        testRoot = base
        assert(try! Data(contentsOf: original) == Data("original".utf8))
        print("PASS: shared preparation failures; delayed IPA/certificate success and failure; original preservation; failed decoder writes")
    }
}
'''
with tempfile.TemporaryDirectory(prefix='korsign-shared-import-check-') as directory:
    work = Path(directory)
    swift = work / 'Check.swift'
    swift.write_text(program)
    binary = work / 'check'
    subprocess.run(['xcrun', 'swiftc', '-swift-version', '5', '-parse-as-library', str(swift), '-o', str(binary)], check=True)
    subprocess.run([str(binary), directory], check=True, timeout=20)
