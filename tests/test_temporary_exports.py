"""Production export ownership and share/HTTP retention with isolated fake consumers."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
files = ['KorSign/Utilities/TemporaryExport.swift', 'KorSign/Utilities/Handlers/CertificateExporter.swift',
         'KorSign/Utilities/FileExporter.swift',
         'NimbleKit/Sources/NimbleExtensions/UIActivityViewController/UlActivityViewController+Present.swift']
source = '\n'.join((root / f).read_text() for f in files)
source = source.replace('import Zip', '').replace('import UIKit.UIActivityViewController', '').replace('public ', '')
http = (root / 'KorSign/Backend/Server/WebManagerServer+HTTP.swift').read_text()
a = http.index('private static func download(')
b = http.index('\n\tprivate static func dateString', a)
http = http[a:b].replace('private static func', 'func')
picker = (root / 'KorSign/Views/Common/DocumentExporterView.swift').read_text()
picker = picker[picker.index('\tfinal class Coordinator:'):picker.rindex('\n}')]
backup = (root / 'KorSign/Backend/Observable/BackupManager.swift').read_text()
a = backup.index('\t\tlet export = try TemporaryExport(fileName: "KorSign-Backup-')
b = backup.index('\n\t}', a)
backup = 'enum BackupOutput { static func _stamp() -> String { "fixture" }\nstatic func write(_ packed: Data) throws -> TemporaryExport {\n' + backup[a:b] + '\n}}'
source += '\n' + picker + '\n' + backup + '\n'
stubs = r'''
import Foundation
import CoreGraphics
let fm = FileManager.default
let root = URL(fileURLWithPath: CommandLine.arguments[1])
extension FileManager {
    func uniqueTemporaryDirectory(_ label: String) -> URL { root.appendingPathComponent(label + UUID().uuidString) }
}
struct CertificatePair { var nickname: String? = "Fixture"; var password: String? = "secret" }
final class Storage {
    static let shared = Storage()
    enum Kind { case certificate, provision }
    var missing = false
    func getFile(_ kind: Kind, from: CertificatePair) -> URL? {
        root.appendingPathComponent((missing && kind == .provision) ? "missing" : (kind == .certificate ? "original.p12" : "original.mobileprovision"))
    }
    func getProvisionFileDecoded(for: CertificatePair) -> Provision? { nil }
    struct Provision { let Name: String }
}
enum Zip {
    static var fail = false
    static func zipFiles(paths: [URL], zipFilePath: URL, password: String?, progress: ((Double) -> Void)?) throws {
        try Data("partial archive".utf8).write(to: zipFilePath)
        if fail { throw CocoaError(.fileWriteUnknown) }
        for path in paths { assert(fm.fileExists(atPath: path.path)) }
    }
}
class UIView { let bounds = CGRect(x: 0, y: 0, width: 20, height: 20) }
class UIViewController {
    let view = UIView()
    var presented: UIActivityViewController?
    func present(_ controller: UIActivityViewController, animated: Bool) { presented = controller }
}
class UIActivity {}
class UIDocumentPickerViewController {}
protocol UIDocumentPickerDelegate {}
class Popover {
    var sourceView: UIView?
    var sourceRect = CGRect.zero
    var permittedArrowDirections: [Int] = []
}
final class UIActivityViewController: UIViewController {
    var completionWithItemsHandler: ((String?, Bool, [Any]?, Error?) -> Void)?
    var popoverPresentationController: Popover? = Popover()
    init(activityItems: [Any], applicationActivities: [UIActivity]?) {}
}
enum UIApplication {
    static var presenter: UIViewController?
    static func topViewController() -> UIViewController? { presenter }
}
struct Headers {
    enum Name { case contentDisposition }
    func replaceOrAdd(name: Name, value: String) {}
}
final class Response {
    let headers = Headers()
    var callback: ((Result<Void, Error>) -> Void)?
}
struct Request {
    let fileio: FileIO
}
struct FileIO {
    var empty = false
    func streamFile(at: String, onCompleted: @escaping @Sendable (Result<Void, Error>) -> Void) -> Response {
        assert(fm.fileExists(atPath: at))
        let response = Response()
        if !empty { response.callback = onCompleted }
        return response
    }
}
func waitUntilRemoved(_ directory: URL) {
    for _ in 0..<2000 {
        if !fm.fileExists(atPath: directory.path) { return }
        Thread.sleep(forTimeInterval: 0.001)
    }
    fatalError("Export was not cleaned")
}
func exports() -> [URL] {
    (try! fm.contentsOfDirectory(at: root, includingPropertiesForKeys: nil)).filter { $0.lastPathComponent.hasPrefix("FeatherExport") }
}
'''
checks = r'''
@main struct Check {
    static func main() throws {
        for name in ["original.p12", "original.mobileprovision"] {
            try Data("original".utf8).write(to: root.appendingPathComponent(name))
        }
        let presenter = UIViewController()
        for completed in [true, false] {
            let directory: URL
            do {
                let export = CertificateExporter.makeZip(for: CertificatePair())!
                directory = export.directory
                assert(fm.fileExists(atPath: directory.appendingPathComponent("password.txt").path))
                UIActivityViewController.show(presenter, activityItems: [export.url], retaining: export)
            }
            // The sheet alone must retain the export after the producer returns.
            assert(fm.fileExists(atPath: directory.path))
            presenter.presented?.completionWithItemsHandler?(nil, completed, nil, nil)
            presenter.presented = nil
            waitUntilRemoved(directory)
        }
        var missingPresenterDirectory: URL!
        do {
            let export = try TemporaryExport(fileName: "no-presenter")
            missingPresenterDirectory = export.directory
            UIActivityViewController.show(nil, activityItems: [export.url], retaining: export)
        }
        waitUntilRemoved(missingPresenterDirectory)
        for empty in [false, true] {
            var response: Response?
            var directory: URL!
            do {
                let export = CertificateExporter.makeZip(for: CertificatePair())!
                directory = export.directory
                response = download(Request(fileio: FileIO(empty: empty)), file: export.url, as: "fixture.zip", retaining: export)
            }
            if !empty {
                assert(fm.fileExists(atPath: directory.path))
                response?.callback?(.failure(CocoaError(.fileReadUnknown)))
            }
            response = nil // Also covers a discarded, never-consumed response.
            waitUntilRemoved(directory)
        }
        // Save-to-Files coordinator retains a batch after the SwiftUI producer releases it.
        for cancel in [false, true] {
            var coordinator: Coordinator?
            var directories: [URL] = []
            var completed = 0
            do {
                let items = [try TemporaryExport(fileName: "one"), try TemporaryExport(fileName: "two")]
                directories = items.map(\.directory)
                for item in items { try Data("export".utf8).write(to: item.url) }
                if !cancel { try fm.copyItem(at: items[0].url, to: root.appendingPathComponent("saved-copy")) }
                coordinator = Coordinator(onComplete: { completed += 1 }, retaining: items as NSArray)
            }
            for directory in directories { assert(fm.fileExists(atPath: directory.path)) }
            if cancel { coordinator?.documentPickerWasCancelled(UIDocumentPickerViewController()) }
            else { coordinator?.documentPicker(UIDocumentPickerViewController(), didPickDocumentsAt: []) }
            assert(completed == 1)
            coordinator = nil
            for directory in directories { waitUntilRemoved(directory) }
            if !cancel { assert(try! Data(contentsOf: root.appendingPathComponent("saved-copy")) == Data("export".utf8)) }
        }
        var backupDirectory: URL!
        do {
            let bytes = Data("sealed backup fixture".utf8)
            let backup = try BackupOutput.write(bytes)
            backupDirectory = backup.directory
            assert(try! Data(contentsOf: backup.url) == bytes)
        }
        waitUntilRemoved(backupDirectory)
        let bundle = root.appendingPathComponent("Sample.framework")
        try fm.createDirectory(at: bundle, withIntermediateDirectories: true)
        var directory: URL!
        do {
            let item = FileExporter.shareableURL(for: bundle)!
            directory = item.owner!.directory
            assert(fm.fileExists(atPath: item.url.path))
        }
        waitUntilRemoved(directory)
        let original = root.appendingPathComponent("original.p12")
        let plain = FileExporter.shareableURL(for: original)!
        assert(plain.url == original && plain.owner == nil)
        // Every failed preparation must clean its partial certificate/password/archive copies.
        for failZip in [true, false] {
            Zip.fail = failZip
            Storage.shared.missing = !failZip
            assert(CertificateExporter.makeZip(for: CertificatePair()) == nil)
            for directory in exports() { waitUntilRemoved(directory) }
        }
        Zip.fail = true
        assert(FileExporter.shareableURL(for: bundle) == nil)
        for directory in exports() { waitUntilRemoved(directory) }
        assert(try! Data(contentsOf: original) == Data("original".utf8))
        assert(fm.fileExists(atPath: bundle.path))
        print("PASS: export failure cleanup; borrowed/saved-copy safety; sheet and picker ownership; backup output; response lifetime")
    }
}
'''
with tempfile.TemporaryDirectory(prefix='korsign-export-check-') as directory:
    work = Path(directory)
    swift = work / 'Check.swift'
    swift.write_text(stubs + source + http + checks)
    binary = work / 'check'
    subprocess.run(['xcrun', 'swiftc', '-swift-version', '5', '-parse-as-library', str(swift), '-o', str(binary)], check=True)
    subprocess.run([str(binary), directory], check=True, timeout=20)
