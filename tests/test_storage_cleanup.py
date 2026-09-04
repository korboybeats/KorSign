"""Production cleanup policy, scanner and delete guard with temporary filesystem roots."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
source = (root / 'KorSign/Backend/Observable/StorageManager.swift').read_text()
models = source[source.index('enum StorageCategory:'):source.index('// MARK: - Manager')]
scanner = source[source.index('struct AppDescriptor:'):] if 'struct AppDescriptor:' in source else source[source.index('struct AppDescriptor {'):]
start = source.index('\tfunc delete(')
delete = source[start:source.index('\n\tfunc clear(', start)]
start = source.index('\tnonisolated static func purgeStaleTemporary')
startup = source[start:source.index('\n}\n', start)]
program = r'''
import Foundation
var testRoot = URL(fileURLWithPath: "/unused")
protocol SortableItem {}
extension String { static func localized(_ value: String) -> String { value } }
''' + models + scanner + r'''
extension StorageCategory { var title: String { rawValue } }
extension FileManager {
    var signed: URL { testRoot.appendingPathComponent("Documents/Signed") }
    var unsigned: URL { testRoot.appendingPathComponent("Documents/Unsigned") }
    var certificates: URL { testRoot.appendingPathComponent("Documents/Certificates") }
    var archives: URL { testRoot.appendingPathComponent("Documents/Archives") }
    var tweaksLibrary: URL { testRoot.appendingPathComponent("Documents/Tweaks") }
    var logs: URL { testRoot.appendingPathComponent("Documents/Logs") }
    var webManagerInbox: URL { testRoot.appendingPathComponent("Documents/WebManager") }
    var downloadStaging: URL { testRoot.appendingPathComponent("tmp/FeatherDownloads") }
    func allocatedSize(at url: URL) -> Int64 {
        if let children = try? contentsOfDirectory(at: url, includingPropertiesForKeys: nil) {
            return children.reduce(0) { $0 + allocatedSize(at: $1) }
        }
        return Int64((try? Data(contentsOf: url).count) ?? 0)
    }
    func availableImportantCapacity(at url: URL) -> Int64? { 0 }
}
final class FileLogger {
    static func clear() { StorageScanner.purge(contentsOf: FileManager.default.logs) }
}
struct App { var uuid: String? }
final class Storage {
    static let shared = Storage()
    func getAllApps() -> [App] { [] }
    func deleteApps(_ apps: [App]) {}
}
final class StorageManager {
    let snapshot: LibrarySnapshot
    var entries: [StorageLocation: [StorageEntry]] = [:]
    init(_ snapshot: LibrarySnapshot) { self.snapshot = snapshot }
    func _librarySnapshot() -> LibrarySnapshot { snapshot }
    func refresh() {}
    static func purgeCaches() { StorageScanner.purge(contentsOf: testRoot.appendingPathComponent("Library/Caches")) }
''' + delete + startup + r'''
}
@main struct Check {
    static func main() throws {
        testRoot = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
        let fm = FileManager.default
        func write(_ path: String) throws -> URL {
            let url = testRoot.appendingPathComponent(path)
            try fm.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
            try Data("keep".utf8).write(to: url)
            return url
        }
        let active = try write("tmp/FeatherSigning_active/input")
        let upload = try write("Documents/WebManager/pending.ipa")
        let moved = try write("Documents/Unsigned/in-flight/binary")
        let staged = try write("tmp/FeatherDownloads/pending/app.ipa")
        let protected = Set(["tmp", "Documents/Signed", "Documents/Unsigned", "Documents/Certificates", "Documents/WebManager"].map {
            testRoot.appendingPathComponent($0).standardizedFileURL.path
        })
        let snapshot = LibrarySnapshot(apps: [:], certificates: [], protected: protected)
        let cache = try write("Library/Caches/icon")
        let log = try write("Documents/Logs/activity.log")
        let before = StorageScanner.scan(snapshot)
        assert(before.reclaimable == 8)
        assert(StorageCategory.safeToClear == [.caches, .logs])
        for category in StorageCategory.safeToClear + [.temporary, .leftovers] {
            StorageScanner.clear(category)
        }
        assert(!fm.fileExists(atPath: cache.path) && !fm.fileExists(atPath: log.path))
        for url in [active, upload, moved, staged] { assert(try! Data(contentsOf: url) == Data("keep".utf8)) }
        let leftovers = StorageScanner.entries(at: .category(.leftovers), snapshot)
        assert(!leftovers.contains { $0.url.path.contains("WebManager") })
        assert(leftovers.allSatisfy(\.isProtected))
        assert(StorageScanner.entries(at: .category(.other), snapshot).contains { $0.url.standardizedFileURL.path == fm.webManagerInbox.standardizedFileURL.path && $0.isProtected })

        // An old unlocked row cannot bypass current protection, nor can a parent or alias.
        let alias = testRoot.appendingPathComponent("alias")
        try fm.createSymbolicLink(at: alias, withDestinationURL: active.deletingLastPathComponent())
        let sibling = try write("tmp-other/file")
        let manager = StorageManager(snapshot)
        for url in [active, upload, moved, testRoot.appendingPathComponent("tmp"), alias.appendingPathComponent("input"), sibling] {
            let entry = StorageEntry(id: url.path, name: "stale", version: nil, size: 4, date: Date(), url: url,
                                     isDirectory: false, childCount: 0, isProtected: false, appUuid: nil)
            manager.delete([entry])
        }
        assert(!fm.fileExists(atPath: sibling.path))
        for url in [active, upload, moved, staged] { assert(try! Data(contentsOf: url) == Data("keep".utf8)) }

        // Startup can retire old temp work, but pending downloads do not expire by age.
        try fm.setAttributes([.modificationDate: Date(timeIntervalSince1970: 0)], ofItemAtPath: fm.downloadStaging.path)
        StorageManager.purgeStaleTemporary()
        assert(!fm.fileExists(atPath: active.path))
        assert(try! Data(contentsOf: staged) == Data("keep".utf8))
        assert(try! Data(contentsOf: upload) == Data("keep".utf8))
        print("PASS: disposable cleanup, active/pending preservation, stale rows, parent/alias boundaries, reclaimable totals and startup retention")
    }
}
'''
# Redirect only platform root lookups; scanner and policy logic remain production code.
program = program.replace('URL.documentsDirectory', 'testRoot.appendingPathComponent("Documents")')
program = program.replace('fm.temporaryDirectory', 'testRoot.appendingPathComponent("tmp")')
program = program.replace('fm.urls(for: .cachesDirectory, in: .userDomainMask)[0]', 'testRoot.appendingPathComponent("Library/Caches")')
program = program.replace('fm.urls(for: .libraryDirectory, in: .userDomainMask)[0]', 'testRoot.appendingPathComponent("Library")')
with tempfile.TemporaryDirectory(prefix='korsign-cleanup-check-') as directory:
    main = Path(directory) / 'Check.swift'
    main.write_text(program)
    binary = Path(directory) / 'check'
    subprocess.run(['swiftc', '-parse-as-library', str(main), '-o', str(binary)], check=True)
    subprocess.run([str(binary), directory], check=True)
