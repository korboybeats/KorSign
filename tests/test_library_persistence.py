"""Production JSON libraries with real temporary files; no app, network or signing."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
sources = []
for name in ['LibraryPersistence.swift', 'TweakModels.swift', 'TweakManager.swift', 'EntitlementsManager.swift']:
    text = (root / 'KorSign/Backend/Observable' / name).read_text()
    for module in ['NimbleExtensions', 'Zip', 'OSLog']:
        text = text.replace(f'import {module}\n', '')
    # Isolated instances instead of touching the app singletons.
    text = text.replace('private init()', 'init()')
    sources.append(text)
sources.append((root / 'KorSign/Utilities/TemporaryExport.swift').read_text())
router_source = (root / 'KorSign/Backend/Server/WebManagerServer.swift').read_text()
router = router_source[router_source.index('enum WebManagerRouter {'):router_source.index('// MARK: - Server')]
stubs = r''' 
import Foundation
import Combine
protocol SortableItem {}
var testRoot: URL!
extension String { static func localized(_ text: String, arguments: CVarArg...) -> String { text } }
enum Toast {
    enum Duration { case sticky }
    static var errors: [String] = []
    static func error(_ text: String, duration: Duration) { errors.append(text) }
}
enum Logger {
    struct Log { func error(_ text: String) {}; func info(_ text: String) {} }
    static let misc = Log()
}
enum FR {
    static var completion: ((Result<Int, Error>) -> Void)?
    static func handlePackageFile(_ url: URL, completion: @escaping (Result<Int, Error>) -> Void) { Self.completion = completion }
}
struct Options {
    enum InjectPath: String, Codable { case executable_path }
    enum InjectFolder: String, Codable { case frameworks }
}
enum Zip {
    static var fail = false
    static func zipFiles(paths: [URL], zipFilePath: URL, password: String?, progress: ((Double) -> Void)?) throws {
        try Data("zip fixture".utf8).write(to: zipFilePath)
        if fail { throw CocoaError(.fileWriteUnknown) }
    }
}
enum TweakExtractor {
    struct Candidate { let url: URL }
    static var candidates: [Candidate] = []
    static var workDirectory: URL!
    static func extract(fromZip url: URL) async throws -> (workDir: URL, candidates: [Candidate]) {
        (workDirectory, candidates)
    }
    static func directorySize(at url: URL) -> Int64 { 0 }
}
struct CertificateReader {
    struct Value { var value: Any }
    struct Profile { var Entitlements: [String: Value]? }
    var decoded: Profile? { nil }
    init(_ url: URL) {}
}
extension FileManager {
    var tweaksLibrary: URL { testRoot.appendingPathComponent("Tweaks") }
    func tweaksLibrary(_ id: String) -> URL { tweaksLibrary.appendingPathComponent(id) }
    var entitlementsLibrary: URL { testRoot.appendingPathComponent("Entitlements") }
    func entitlementsLibrary(_ id: String) -> URL { entitlementsLibrary.appendingPathComponent(id) }
    func createDirectoryIfNeeded(at url: URL) throws { try createDirectory(at: url, withIntermediateDirectories: true) }
    func removeFileIfNeeded(at url: URL) throws { if fileExists(atPath: url.path) { try removeItem(at: url) } }
    func uniqueTemporaryDirectory(_ label: String) -> URL { testRoot.appendingPathComponent(label + UUID().uuidString) }
}
'''
checks = r'''
@main struct Check {
    @MainActor static func main() async throws {
        testRoot = URL(fileURLWithPath: CommandLine.arguments[1])
        let fm = FileManager.default
        let source = testRoot.appendingPathComponent("input.dylib")
        try Data("original".utf8).write(to: source)
        let tweaks = TweakManager()
        let entitlements = EntitlementsManager()
        let tweakManifest = fm.tweaksLibrary.appendingPathComponent("library.json")
        let folderManifest = fm.tweaksLibrary.appendingPathComponent("folders.json")
        let entitlementManifest = fm.entitlementsLibrary.appendingPathComponent("library.json")
        // A directory in place of a file forces a real atomic-write failure, even as root.
        func failWrites(at url: URL, _ body: () throws -> Void) throws {
            let original = url.appendingPathExtension("fixture-backup")
            let existed = fm.fileExists(atPath: url.path)
            if existed { try fm.moveItem(at: url, to: original) }
            try fm.createDirectory(at: url, withIntermediateDirectories: true)
            let marker = url.appendingPathComponent("keep")
            try Data("keep".utf8).write(to: marker)
            defer {
                assert(try! Data(contentsOf: marker) == Data("keep".utf8))
                try! fm.removeItem(at: url)
                if existed { try! fm.moveItem(at: original, to: url) }
            }
            try body()
        }
        let tweak = tweaks.addTweak(name: "Test", from: source)!
        let version = tweak.versions[0]
        let component = version.components[0]
        let installedFile = tweaks.fileURL(forTweak: tweak, version: version, component: component)
        let folder = tweaks.addFolder(name: "Folder")!
        assert(tweaks.moveTweaks([tweak.id], toFolder: folder.id))
        let savedTweaks = tweaks.tweaks
        let savedFolders = tweaks.folders
        let savedBytes = try Data(contentsOf: tweakManifest)
        let beforeDirectories = Set(try fm.contentsOfDirectory(atPath: fm.tweaksLibrary.path))
        try failWrites(at: tweakManifest) {
            tweaks.mutate(tweak.id) { $0.name = "lost" }
            tweaks.mutateComponent(component.id, versionId: version.id, in: tweak.id) { $0.isEnabled = false }
            assert(!tweaks.deleteTweak(tweak.id))
            tweaks.deleteVersion(version.id, from: tweak.id)
            tweaks.deleteComponent(component.id, versionId: version.id, from: tweak.id)
            assert(!tweaks.deleteFolder(folder.id))
            assert(!tweaks.moveTweaks([tweak.id], toFolder: nil))
            assert(tweaks.addTweak(name: "Failed", from: source) == nil)
            assert(tweaks.addVersion(to: tweak.id, from: source, label: "2") == nil)
            assert(tweaks.addComponents(to: tweak.id, versionId: version.id, fromFiles: [source]).isEmpty)
            tweaks.resetLibrary()
            assert(tweaks.tweaks == savedTweaks && tweaks.folders == savedFolders)
            assert(try! Data(contentsOf: installedFile) == Data("original".utf8))
        }
        assert(try Data(contentsOf: tweakManifest) == savedBytes)
        assert(Set(try! fm.contentsOfDirectory(atPath: fm.tweaksLibrary.path)) == beforeDirectories)
        assert(TweakManager().tweaks == savedTweaks)
        try failWrites(at: folderManifest) {
            assert(tweaks.addFolder(name: "Failed") == nil)
            tweaks.renameFolder(folder.id, to: "Failed")
            assert(tweaks.folders == savedFolders)
        }
        // Copy failure midway through a multi-file add must not accept only the first file.
        assert(tweaks.addTweak(name: "Partial", fromFiles: [source, testRoot.appendingPathComponent("missing")]) == nil)
        assert(tweaks.tweaks == savedTweaks)
        // Retry succeeds and persists after reopening; deletion follows the successful save.
        tweaks.mutate(tweak.id) { $0.name = "Saved" }
        assert(TweakManager().tweak(tweak.id)?.name == "Saved")
        assert(tweaks.deleteTweak(tweak.id))
        assert(!fm.fileExists(atPath: installedFile.path) && TweakManager().tweaks.isEmpty)

        let entry = entitlements.add(name: "Original", dict: ["flag": true])!
        let plist = entitlements.fileURL(for: entry)
        let oldPlist = try Data(contentsOf: plist)
        try failWrites(at: entitlementManifest) {
            assert(entitlements.addBlank(name: "Failed") == nil)
            entitlements.rename(entry.id, to: "Failed")
            assert(!entitlements.delete(entry.id))
            assert(entitlements.files == [entry])
            assert(try! Data(contentsOf: plist) == oldPlist)
        }
        try failWrites(at: plist) {
            assert(!entitlements.save(entry, dict: ["flag": false]))
            assert(entitlements.load(entry, reportFailure: false) == nil)
        }
        assert(!entitlements.save(entry, dict: ["bad": URL(string: "https://fixture")!]))
        assert(try Data(contentsOf: plist) == oldPlist)
        assert(entitlements.save(entry, dict: ["flag": false]))
        assert(EntitlementsManager().load(entry)?["flag"] as? Bool == false)
        assert(entitlements.delete(entry.id))
        assert(!fm.fileExists(atPath: plist.path) && EntitlementsManager().files.isEmpty)

        // Corrupt or partly undecodable manifests cannot be silently rewritten as empty.
        let corrupt = Data("[{\"name\":\"recoverable\"},42]".utf8)
        try corrupt.write(to: tweakManifest)
        let damaged = TweakManager()
        assert(damaged.addTweak(name: "Blocked", from: source) == nil)
        damaged.resetLibrary()
        assert(try Data(contentsOf: tweakManifest) == corrupt)
        try Data("not json".utf8).write(to: entitlementManifest)
        let damagedEntitlements = EntitlementsManager()
        assert(damagedEntitlements.addBlank(name: "Blocked") == nil)
        assert(try Data(contentsOf: entitlementManifest) == Data("not json".utf8))
        try Data("[]".utf8).write(to: tweakManifest)
        try Data("[]".utf8).write(to: entitlementManifest)

        // Model-level compatibility remains: pre-folder, single-file versions still decode.
        let legacy = Data("[{\"name\":\"Legacy\",\"versions\":[{\"fileName\":\"old.dylib\",\"fileType\":\"dylib\"}]}]".utf8)
        try legacy.write(to: tweakManifest)
        assert(TweakManager().tweaks.first?.versions.first?.components.first?.fileName == "old.dylib")

        // A version with no registered components can still contain recovery files.
        let emptyVersion = TweakVersion(label: "empty", components: [])
        let emptyTweak = ManagedTweak(name: "Empty", versions: [emptyVersion])
        try LibraryPersistence.save([emptyTweak], to: tweakManifest)
        let emptyManager = TweakManager()
        let orphanDir = emptyManager.versionDirectory(forTweak: emptyTweak.id, version: emptyVersion)
        try fm.createDirectory(at: orphanDir, withIntermediateDirectories: true)
        let orphan = orphanDir.appendingPathComponent("recovery")
        try Data("keep".utf8).write(to: orphan)
        assert(emptyManager.addComponents(to: emptyTweak.id, versionId: emptyVersion.id,
            fromFiles: [source, testRoot.appendingPathComponent("missing")]).isEmpty)
        assert(try! Data(contentsOf: orphan) == Data("keep".utf8))

        // Restore fails truthfully, cleans its new copies, and never adopts unknown old files.
        try Data("[]".utf8).write(to: tweakManifest)
        let restoring = TweakManager()
        let backup = testRoot.appendingPathComponent("backup")
        let incoming = ManagedTweak(name: "Restored")
        try fm.createDirectory(at: backup.appendingPathComponent(incoming.id.uuidString), withIntermediateDirectories: true)
        try Data("backup".utf8).write(to: backup.appendingPathComponent(incoming.id.uuidString).appendingPathComponent("payload"))
        try LibraryPersistence.save([incoming], to: backup.appendingPathComponent("library.json"))
        try failWrites(at: tweakManifest) {
            do { _ = try restoring.mergeFromBackup(tweaksDir: backup); fatalError("Expected restore failure") } catch {}
            assert(restoring.tweaks.isEmpty)
            assert(!fm.fileExists(atPath: fm.tweaksLibrary(incoming.id.uuidString).path))
        }
        assert(try restoring.mergeFromBackup(tweaksDir: backup) == 1)
        assert(try restoring.mergeFromBackup(tweaksDir: backup) == 0)
        assert(TweakManager().tweaks == [incoming])
        assert(try Data(contentsOf: source) == Data("original".utf8))
        testRoot = testRoot.appendingPathComponent("router")
        try fm.createDirectory(at: testRoot, withIntermediateDirectories: true)
        let routerManager = TweakManager.shared // initialize before injecting the write failure
        let routerManifest = fm.tweaksLibrary.appendingPathComponent("library.json")
        try fm.createDirectory(at: routerManifest, withIntermediateDirectories: true)
        var importedCount = 0
        let upload = testRoot.appendingPathComponent("upload.dylib")
        try Data("upload".utf8).write(to: upload)
        WebManagerRouter.route(upload) { importedCount += 1 }
        try await Task.sleep(nanoseconds: 50_000_000)
        assert(fm.fileExists(atPath: upload.path) && routerManager.tweaks.isEmpty && importedCount == 0)
        try fm.removeItem(at: routerManifest)
        WebManagerRouter.route(upload) { importedCount += 1 }
        for _ in 0..<100 where fm.fileExists(atPath: upload.path) {
            try await Task.sleep(nanoseconds: 10_000_000)
        }
        assert(!fm.fileExists(atPath: upload.path) && routerManager.tweaks.count == 1 && importedCount == 1)
        assert(TweakManager().tweaks == routerManager.tweaks)
        let zip = testRoot.appendingPathComponent("partial.zip")
        try Data("zip fixture".utf8).write(to: zip)
        let work = testRoot.appendingPathComponent("extracted")
        try fm.createDirectory(at: work, withIntermediateDirectories: true)
        let first = work.appendingPathComponent("first.dylib")
        try Data("first".utf8).write(to: first)
        TweakExtractor.workDirectory = work
        TweakExtractor.candidates = [.init(url: first), .init(url: work.appendingPathComponent("missing.dylib"))]
        WebManagerRouter.route(zip) { importedCount += 1 }
        for _ in 0..<100 where fm.fileExists(atPath: work.path) {
            try await Task.sleep(nanoseconds: 10_000_000)
        }
        assert(fm.fileExists(atPath: zip.path), "Partly failed ZIP import deleted its source")
        assert(routerManager.tweaks.count == 2)
        assert(importedCount == 1) // Partial ZIP import must retain its recovery copy.
        let ipa = testRoot.appendingPathComponent("fixture.ipa")
        try Data("ipa fixture".utf8).write(to: ipa)
        WebManagerRouter.route(ipa) { importedCount += 1 }
        try await Task.sleep(nanoseconds: 50_000_000)
        assert(fm.fileExists(atPath: ipa.path))
        FR.completion?(.failure(CocoaError(.fileReadCorruptFile)))
        assert(importedCount == 1 && fm.fileExists(atPath: ipa.path))
        WebManagerRouter.route(ipa) { importedCount += 1 }
        try await Task.sleep(nanoseconds: 50_000_000)
        FR.completion?(.success(1))
        assert(importedCount == 2 && !fm.fileExists(atPath: ipa.path))
        FR.completion = nil
        try fm.createDirectory(at: work, withIntermediateDirectories: true)
        try Data("retry".utf8).write(to: first)
        TweakExtractor.candidates = [.init(url: first)]
        WebManagerRouter.route(zip) { importedCount += 1 }
        for _ in 0..<100 where fm.fileExists(atPath: zip.path) {
            try await Task.sleep(nanoseconds: 10_000_000)
        }
        assert(importedCount == 3 && !fm.fileExists(atPath: zip.path))


        // Export owners release only their staging, never the stored library files.
        let exportManager = routerManager
        let exportFolder = exportManager.addFolder(name: "Export")!
        let ids = Set(exportManager.tweaks.map(\.id))
        assert(exportManager.moveTweaks(ids, toFolder: exportFolder.id))
        let stored = exportManager.tweaks.flatMap { tweak in
            exportManager.fileURLs(forTweak: tweak.id, version: tweak.activeVersion!)
        }
        let storedBytes = try stored.map { try Data(contentsOf: $0) }
        var directories: [URL] = []
        do {
            let exports = exportManager.exportableURLs(forTweakIds: ids)
            assert(exports.count == ids.count)
            directories += exports.map(\.directory)
            for export in exports { assert(fm.fileExists(atPath: export.url.path)) }
            let folderExport = exportManager.exportFolder(exportFolder.id)!
            directories.append(folderExport.directory)
            assert(fm.fileExists(atPath: folderExport.url.path))
            let bundle = testRoot.appendingPathComponent("Bundle.framework")
            try fm.createDirectory(at: bundle, withIntermediateDirectories: true)
            let bundled = exportManager.addTweak(name: "Bundle", from: bundle)!
            let zipped = exportManager.exportableURL(for: bundled, version: bundled.activeVersion!)!
            directories.append(zipped.directory)
            assert(zipped.url.pathExtension == "zip")
            let multi = exportManager.addTweak(name: "Multiple", fromFiles: stored)!
            let combined = exportManager.exportableURL(for: multi, version: multi.activeVersion!)!
            directories.append(combined.directory)
            assert(combined.url.pathExtension == "zip")
            Zip.fail = true
            assert(exportManager.exportFolder(exportFolder.id) == nil)
            assert(exportManager.exportableURL(for: bundled, version: bundled.activeVersion!) == nil)
        }
        directories += try fm.contentsOfDirectory(at: testRoot, includingPropertiesForKeys: nil)
            .filter { $0.lastPathComponent.hasPrefix("FeatherExport") }
        for directory in directories {
            for _ in 0..<200 where fm.fileExists(atPath: directory.path) {
                try await Task.sleep(nanoseconds: 10_000_000)
            }
            assert(!fm.fileExists(atPath: directory.path))
        }
        assert(try stored.map { try Data(contentsOf: $0) } == storedBytes)
        print("PASS: single, selection, folder, bundle and multi-file export ownership; ZIP failures; stored sources preserved")

        assert(!Toast.errors.isEmpty)
        print("PASS: failed add/edit/delete/restore preservation, retry/reopen durability, corrupt-load blocking, legacy decoding and source retention")
    }
}
'''
checks = checks.replace('assert(try ', 'assert(try! ')
with tempfile.TemporaryDirectory(prefix='korsign-library-save-check-') as directory:
    source = Path(directory) / 'Check.swift'
    source.write_text(stubs + '\n'.join(sources) + router + checks)
    binary = Path(directory) / 'check'
    subprocess.run(['swiftc', '-parse-as-library', str(source), '-o', str(binary)], check=True)
    subprocess.run([str(binary), directory], check=True, timeout=30)
