"""Run production storage methods against real Core Data and isolated SQLite files."""
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parents[1]
model_path = root / 'KorSign/Backend/Storage/Feather.xcdatamodeld'
model = ET.parse(model_path / 'Feather.xcdatamodel/Contents').getroot()
classes = []
types = {'String': 'String?', 'Date': 'Date?', 'URI': 'URL?', 'Boolean': 'Bool', 'Integer 32': 'Int32'}
for entity in model.findall('entity'):
    name = entity.attrib['name']
    properties = [f"@NSManaged var {a.attrib['name']}: {types[a.attrib['attributeType']]}" for a in entity.findall('attribute')]
    for relationship in entity.findall('relationship'):
        typ = 'NSSet?' if relationship.get('toMany') == 'YES' else relationship.get('destinationEntity') + '?'
        properties.append(f"@NSManaged var {relationship.get('name')}: {typ}")
    classes.append(f'''@objc({name}) class {name}: NSManagedObject {{
    {chr(10).join(properties)}
    @nonobjc class func fetchRequest() -> NSFetchRequest<{name}> {{ NSFetchRequest(entityName: "{name}") }}
}}''')

def source(name):
    return (root / 'KorSign/Backend/Storage' / name).read_text().replace('import UIKit.UIImpactFeedbackGenerator', '')

storage = source('Storage.swift').replace('NSPersistentContainer(name: _name)', 'makeContainer()').replace('UserDefaults.standard', 'testDefaults')
# Only substitute the container location/model and isolated defaults. Execute production load/save logic.
program = '''import Foundation
import CoreData
import Combine
import OSLog
extension Logger { static let misc = Logger(subsystem: "StorageCheck", category: "test") }
struct UIImpactFeedbackGenerator {
    enum Style { case light }
    init(style: Style) {}
    func impactOccurred() {}
}
let testRoot = URL(fileURLWithPath: CommandLine.arguments[1])
let defaultsName = "KorSignStorageTest-" + UUID().uuidString
let testDefaults = UserDefaults(suiteName: defaultsName)!
var storeURL: URL { testRoot.appendingPathComponent("library.sqlite") }
let sharedModel = NSManagedObjectModel(contentsOf: testRoot.appendingPathComponent("Feather.momd"))!
func makeContainer() -> NSPersistentContainer {
    let model = sharedModel
    let container = NSPersistentContainer(name: "Feather", managedObjectModel: model)
    container.persistentStoreDescriptions = [NSPersistentStoreDescription(url: storeURL)]
    return container
}
extension FileManager {
    func signed(_ id: String) -> URL { testRoot.appendingPathComponent("Signed/" + id) }
    func unsigned(_ id: String) -> URL { testRoot.appendingPathComponent("Unsigned/" + id) }
    func getPath(in url: URL, for ext: String) -> URL? { url }
}
''' + '\n'.join(classes) + storage + source('Storage+Imported.swift') + source('Storage+Signed.swift') + source('Storage+Shared.swift')
certificate = source('Storage+Certificate.swift').replace('import Zsign', '')
certificate = certificate[:certificate.index('\n\tfunc revokagedCertificate')] + '\n}'
program += (root / 'KorSign/Utilities/CertificateSelection.swift').read_text() + certificate + source('Storage+Sources.swift').replace('import AltSourceKit', '')
checker = (root / 'KorSign/Backend/Observable/AppUpdateChecker.swift').read_text()
for module in ['SwiftUI', 'AltSourceKit', 'NimbleViews', 'UIKit']:
    checker = checker.replace(f'import {module}\n', '')
fr = (root / 'KorSign/Utilities/FR.swift').read_text()
fr = fr[fr.index('\tstatic func handleSource('):fr.index('\n\tstatic func exportCertificateAndOpenUrl')]
program += checker + '\nenum FR {\n' + fr + '\n}\n'

# Execute the real consumer resolution and backup-key policy against this isolated store.
updater = (root / 'KorSign/Backend/Observable/SelfUpdateManager.swift').read_text()
updater = updater[updater.index('\tfunc resolvedCertificate()'):updater.index('\n\tvar method:')]
auto = (root / 'KorSign/Backend/Observable/AutoSignManager.swift').read_text()
auto = auto[auto.index('\tnonisolated private static func _certificate()'):auto.index('\n}\n\nenum AutoSignError')]
consumer = (updater.replace('func resolvedCertificate()', 'static func resolvedCertificate()') +
            auto.replace('nonisolated private static', 'static')).replace('Storage.shared', 'storage').replace('UserDefaults.standard', 'testDefaults')
program += '\nenum CertificateConsumers { static var storage: Storage!\n' + consumer + '\n}\n'
backup = (root / 'KorSign/Backend/Observable/BackupManager.swift').read_text()
start = backup.index('\tprivate static let _settingPrefixes')
end = backup.index('\n\t}', backup.index('static func isBackupableSettingKey', start)) + len('\n\t}')
program += '\nenum BackupPolicy {\n' + backup[start:end] + '\n}\n'

program += r'''
// Dynamic results preserve the view-context boundary without hosting a SwiftUI view.
struct FetchedResults<T: NSManagedObject>: Sequence {
    let read: () -> [T]
    func makeIterator() -> IndexingIterator<[T]> {
        MainActor.preconditionIsolated()
        return read().makeIterator()
    }
}
final class ComparisonGate: @unchecked Sendable {
    let entered = DispatchSemaphore(value: 0), release = DispatchSemaphore(value: 0)
    private let lock = NSLock()
    private var used = false
    func waitUntilEntered() { precondition(entered.wait(timeout: .now() + 10) == .success) }
    func pauseOnce() {
        lock.lock()
        let pause = !used
        used = true
        lock.unlock()
        if pause { entered.signal(); precondition(release.wait(timeout: .now() + 10) == .success) }
    }
}
struct ASRepository {
    var name: String?; var id: String?; var currentIconURL: URL?
    var apps: [App] = []
    struct App {
        var id: String?
        var currentName: String
        var version: String?
        var currentUniqueId: String
        var gate: ComparisonGate? = nil
        var currentVersion: String? { gate?.pauseOnce(); return version }
    }
}
final class SkippedUpdatesManager {
    static let shared = SkippedUpdatesManager()
    static var persisted: Set<String> = []
    var bundleIDs: Set<String> { Self.persisted }
}
extension String { static func localized(_ value: String) -> String { value } }
enum Toast { enum Duration { case sticky }; static func error(_ value: String, duration: Duration) {} }
final class NBFetchService {
    static var outcome: Result<ASRepository, Error> = .failure(CocoaError(.fileReadUnknown))
    func fetch<T>(from url: URL, completion: @escaping (Result<T, Error>) -> Void) {
        let result = Self.outcome.map { $0 as! T }
        DispatchQueue.global().async { completion(result) }
    }
}
@MainActor func readChecks(_ storage: Storage) async throws {
    let checker = AppUpdateChecker.shared
    let signed = FetchedResults { try! storage.context.fetch(Signed.fetchRequest()) }
    let imported = FetchedResults { try! storage.context.fetch(Imported.fetchRequest()) }
    let rows = Array(signed)
    rows.forEach { $0.identifier = "renamed.app"; $0.originalIdentifier = "original.app"; $0.version = "1" }
    try storage.saveContext().get()
    let app = ASRepository.App(id: "original.app", currentName: "Different", version: "2", currentUniqueId: "source.app")
    let repo = ASRepository(name: "Source", id: "source", apps: [app])
    await checker.precomputeAllUpdates(sources: [repo], signedApps: signed, importedApps: imported)
    assert(checker.updateCount == 1 && checker.appsWithUpdates == ["source.app"])
    assert(checker.checkForUpdates(app: app, signedApps: signed, importedApps: imported))
    SkippedUpdatesManager.persisted = ["original.app"]
    await checker.precomputeAllUpdates(sources: [repo], signedApps: signed, importedApps: imported)
    assert(checker.updateCount == 0)
    SkippedUpdatesManager.persisted = []
    var importError: Error?
    storage.addImported(uuid: "higher-import", appName: "Different", appIdentifier: "other.id", appVersion: "4") { importError = $0 }
    assert(importError == nil)
    await checker.precomputeAllUpdates(sources: [repo], signedApps: signed, importedApps: imported)
    assert(checker.updateCount == 0, "Lost name fallback or highest imported version")
    Array(imported).forEach { storage.context.delete($0) }
    try storage.saveContext().get()

    // A real managed version changes while the plain-value comparison is paused.
    let gate = ComparisonGate()
    var delayed = repo
    delayed.apps[0].gate = gate
    let pending = Task { await checker.precomputeAllUpdates(sources: [delayed], signedApps: signed, importedApps: imported) }
    await Task.detached { gate.waitUntilEntered() }.value
    rows[0].version = "3"
    try storage.saveContext().get()
    gate.release.signal()
    await pending.value
    assert(checker.updateCount == 0, "Published an obsolete library snapshot")

    rows.forEach { $0.version = "1" }
    try storage.saveContext().get()
    let olderGate = ComparisonGate()
    delayed.apps[0].gate = olderGate
    let olderRepo = delayed
    let older = Task { await checker.precomputeAllUpdates(sources: [olderRepo], signedApps: signed, importedApps: imported) }
    await Task.detached { olderGate.waitUntilEntered() }.value
    await checker.precomputeAllUpdates(sources: [], signedApps: signed, importedApps: imported)
    olderGate.release.signal()
    await older.value
    assert(checker.updateCount == 0 && checker.appsWithUpdates.isEmpty, "Older request replaced newer results")

    let cancelGate = ComparisonGate()
    delayed.apps[0].gate = cancelGate
    let cancelledRepo = delayed
    let cancelled = Task { await checker.precomputeAllUpdates(sources: [cancelledRepo], signedApps: signed, importedApps: imported) }
    await Task.detached { cancelGate.waitUntilEntered() }.value
    cancelled.cancel()
    cancelGate.release.signal()
    await cancelled.value
    assert(checker.updateCount == 0 && checker.appsWithUpdates.isEmpty)
}
@MainActor func sourceChecks() async throws {
    let storage = Storage.shared
    let repo = ASRepository(name: "Added", id: "added")
    NBFetchService.outcome = .success(repo)
    func handle() async -> Result<String, Error> {
        await withCheckedContinuation { continuation in
            FR.handleSource("https://example.test/source", showAlerts: false) { result in
                MainActor.preconditionIsolated()
                continuation.resume(returning: result)
            }
        }
    }
    _ = Imported(context: storage.context) // Force the real save to fail validation.
    if case .success = await handle() { fatalError("Source callback hid the failed save") }
    let absent = await Task.detached { storage.sourceExists("added") }.value
    assert(!absent && !storage.context.hasChanges)
    let added = try await handle().get()
    assert(added == "Added")
    let present = await Task.detached { storage.sourceExists("added") }.value
    assert(present)
    if case .success = await handle() { fatalError("Duplicate was reported as a new source") }
    NBFetchService.outcome = .failure(CocoaError(.fileReadUnknown))
    if case .success = await handle() { fatalError("Network failure reported success") }
    try close(storage)
}
extension Storage {
    func revokagedCertificate(for cert: CertificatePair) {}
    func getUuidDirectory(for cert: CertificatePair) -> URL? {
        cert.uuid.map { testRoot.appendingPathComponent("Certificates/" + $0) }
    }

}
func insert(_ storage: Storage, id: String, valid: Bool = true) -> Result<Signed, Error> {
    var outcome: Result<Signed, Error>?
    storage.addSigned(uuid: id, appName: valid ? "App" : nil, appIdentifier: "test.app", appVersion: "1") { outcome = $0 }
    return outcome!
}
func close(_ storage: Storage) throws {
    for store in storage.container.persistentStoreCoordinator.persistentStores {
        try storage.container.persistentStoreCoordinator.remove(store)
    }
}
@main struct Check {
    @MainActor static func main() async throws {
        let fm = FileManager.default
        defer { testDefaults.removePersistentDomain(forName: defaultsName) }
        let sentinel = testRoot.appendingPathComponent("Certificates/keep.p12")
        try fm.createDirectory(at: sentinel.deletingLastPathComponent(), withIntermediateDirectories: true)
        try Data("credentials".utf8).write(to: sentinel)
        let corrupt = Data("not a SQLite database".utf8)
        try corrupt.write(to: storeURL)
        let failed = Storage()
        assert(!failed.isReady && failed.loadError != nil)
        assert(testDefaults.object(forKey: CertificateSelection.selectedKey) == nil)
        assert(testDefaults.object(forKey: CertificateSelection.updaterKey) == nil)
        assert(!testDefaults.bool(forKey: "feather.sortIndexMigrated"))
        assert(try Data(contentsOf: storeURL) == corrupt)
        assert(fm.fileExists(atPath: sentinel.path))
        if case .success = failed.saveContext() { fatalError("Saved without a store") }
        failed.retryLoad()
        assert(!failed.isReady)
        assert(try Data(contentsOf: storeURL) == corrupt)
        // Test owns this corrupt fixture. Production never removes it.
        try fm.removeItem(at: storeURL)
        failed.retryLoad()
        assert(failed.isReady && failed.loadError == nil)
        let app = try insert(failed, id: "durable").get()
        assert(!failed.context.hasChanges && !app.objectID.isTemporaryID)
        if case .success = insert(failed, id: "invalid", valid: false) { fatalError("False signing success") }
        assert(!failed.context.hasChanges)
        assert(try failed.context.count(for: Signed.fetchRequest()) == 1)
        var importError: Error?
        failed.addImported(uuid: "invalid-import") { importError = $0 }
        assert(importError != nil && !failed.context.hasChanges)
        assert(try failed.context.count(for: Imported.fetchRequest()) == 0)
        var certificateError: Error?
        _ = Imported(context: failed.context)
        failed.addCertificate(uuid: "invalid-cert", expiration: Date()) { certificateError = $0 }
        assert(certificateError != nil && !failed.context.hasChanges)
        assert(try failed.context.count(for: CertificatePair.fetchRequest()) == 0)
        var sourceError: Error?
        _ = Imported(context: failed.context)
        failed.addSources(repos: [URL(string: "https://example.test")!: ASRepository(name: "Source", id: "source", currentIconURL: nil)]) { sourceError = $0 }
        assert(sourceError != nil && !failed.context.hasChanges)
        assert(try failed.context.count(for: AltSource.fetchRequest()) == 0)
        // A failed deletion save must not erase the app directory.
        let directory = fm.signed("durable")
        try fm.createDirectory(at: directory, withIntermediateDirectories: true)
        _ = Imported(context: failed.context) // mandatory fields missing: force a real validation failure
        failed.deleteApps([app])
        assert(fm.fileExists(atPath: directory.path))
        assert(try failed.context.count(for: Signed.fetchRequest()) == 1)
        // Legacy migration uses the last visible date-desc list once, before any new import.
        failed.addCertificate(uuid: "older", expiration: Date()) { assert($0 == nil) }
        failed.addCertificate(uuid: "newer", expiration: Date()) { assert($0 == nil) }
        failed.getCertificate(uuid: "older")!.date = Date(timeIntervalSince1970: 1)
        failed.getCertificate(uuid: "newer")!.date = Date(timeIntervalSince1970: 2)
        _ = try failed.saveContext().get()
        testDefaults.removeObject(forKey: CertificateSelection.selectedKey)
        testDefaults.removeObject(forKey: CertificateSelection.updaterKey)
        testDefaults.set(1, forKey: "feather.selectedCert")
        testDefaults.set(0, forKey: "Feather.selfUpdateCertIndex")
        try close(failed)
        let reopened = Storage()
        assert(reopened.isReady)
        assert(testDefaults.string(forKey: CertificateSelection.selectedKey) == "older")
        assert(testDefaults.string(forKey: CertificateSelection.updaterKey) == "newer")
        CertificateConsumers.storage = reopened
        assert(CertificateConsumers._certificate()?.uuid == "older")
        assert(CertificateConsumers.resolvedCertificate()?.uuid == "newer")
        testDefaults.set("", forKey: CertificateSelection.updaterKey)
        assert(CertificateConsumers.resolvedCertificate()?.uuid == "older")
        testDefaults.set("newer", forKey: CertificateSelection.updaterKey)
        assert(!BackupPolicy.isBackupableSettingKey("feather.selectedCert"))
        assert(!BackupPolicy.isBackupableSettingKey("Feather.selfUpdateCertIndex"))
        assert(!BackupPolicy.isBackupableSettingKey(CertificateSelection.selectedKey))
        assert(BackupPolicy.isBackupableSettingKey(CertificateSelection.updaterKey))

        reopened.addCertificate(uuid: "latest", expiration: Date()) { assert($0 == nil) }
        let chosen = testDefaults.string(forKey: CertificateSelection.selectedKey)!
        assert(reopened.getCertificate(uuid: chosen)?.uuid == "older")
        reopened.deleteCertificate(for: reopened.getCertificate(uuid: "newer")!)
        assert(reopened.getCertificate(uuid: chosen)?.uuid == "older")
        assert(reopened.getCertificate(uuid: testDefaults.string(forKey: CertificateSelection.updaterKey)!) == nil)
        reopened.deleteCertificate(for: reopened.getCertificate(uuid: chosen)!)
        assert(reopened.getCertificate(uuid: chosen) == nil)
        assert(CertificateConsumers._certificate() == nil)
        assert(CertificateConsumers.resolvedCertificate() == nil)
        CertificateSelection.migrate(ids: ["latest"], defaults: testDefaults)
        assert(testDefaults.string(forKey: CertificateSelection.selectedKey) == "older")
        // Invalid old choices remain missing; the updater's follow-selected default stays distinct.
        testDefaults.removeObject(forKey: CertificateSelection.selectedKey)
        testDefaults.removeObject(forKey: CertificateSelection.updaterKey)
        testDefaults.set(99, forKey: "feather.selectedCert")
        testDefaults.set(99, forKey: "Feather.selfUpdateCertIndex")
        CertificateSelection.migrate(ids: ["latest"], defaults: testDefaults)
        assert(testDefaults.string(forKey: CertificateSelection.selectedKey) == "")
        assert(testDefaults.string(forKey: CertificateSelection.updaterKey) == "missing")
        testDefaults.removeObject(forKey: CertificateSelection.updaterKey)
        testDefaults.removeObject(forKey: "Feather.selfUpdateCertIndex")
        CertificateSelection.migrate(ids: [], defaults: testDefaults)
        assert(testDefaults.string(forKey: CertificateSelection.updaterKey) == "")
        print("PASS: certificate migration, reorder/import stability, missing/deleted selection, updater override and follow-selected defaults")

        assert(try reopened.context.count(for: Signed.fetchRequest()) == 1)
        let background = await Task.detached { insert(reopened, id: "background").map { _ in () } }.value
        _ = try background.get()
        assert(try reopened.context.count(for: Signed.fetchRequest()) == 2)
        try await readChecks(reopened)
        try close(reopened)
        try await sourceChecks()
        assert(fm.fileExists(atPath: sentinel.path))
        print("PASS: load/retry preserve data; failed saves and deletion roll back; committed rows survive reopen; background insertion/reads are queue-confined; update snapshots reject stale/cancelled results; source errors reach main")
    }
}
'''
# Swift assert's autoclosure is nonthrowing.
program = program.replace('assert(try ', 'assert(try! ')
with tempfile.TemporaryDirectory(prefix='korsign-storage-test-') as directory:
    tmp = Path(directory)
    subprocess.run(['xcrun', 'momc', '--sdkroot', subprocess.check_output(['xcrun', '--sdk', 'macosx', '--show-sdk-path'], text=True).strip(), str(model_path), str(tmp / 'Feather.momd')], check=True)
    swift = tmp / 'check.swift'
    swift.write_text(program)
    subprocess.run(['xcrun', 'swiftc', '-swift-version', '5', '-parse-as-library', str(swift), '-o', str(tmp / 'check')], check=True)
    subprocess.run([str(tmp / 'check'), directory, '-com.apple.CoreData.ConcurrencyDebug', '1'], check=True)
