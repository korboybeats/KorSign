"""Production batch runner and cleanup with controlled terminal evidence; no signing/network."""
from pathlib import Path
import subprocess
import tempfile
root = Path(__file__).resolve().parents[1]
source = (root / 'KorSign/Backend/Observable/BatchJobRunner.swift').read_text().replace('import SwiftUI', 'import Combine')
source += (root / 'KorSign/Backend/Observable/InstallCleanup.swift').read_text().replace('UserDefaults.standard', 'defaults')
stubs = r'''
import Foundation
let suite = "KorSignBatchTest-" + UUID().uuidString
let defaults = UserDefaults(suiteName: suite)!
extension String {
    static func localized(_ value: String) -> String { value }
}
protocol AppInfoPresentable { var uuid: String? { get }; var isSigned: Bool { get } }
class Signed: AppInfoPresentable {
    var uuid: String?
    var isSigned: Bool { true }
    init(_ id: String) { uuid = id }
}
struct UIImage {}
struct CertificatePair {}
struct Options {
    var post_deleteAppAfterSigned = false
    func resolved(for app: AppInfoPresentable) -> Options { self }
}
enum FR {
    static func signPackageFile(_ app: AppInfoPresentable, using: Options, icon: UIImage?,
        certificate: CertificatePair?, completion: (Result<Signed, Error>) -> Void) {
        completion(.success(Signed(app.uuid! + "-signed")))
    }
}
enum FileLogger { static func log(_ text: String, category: String) {} }
@MainActor final class Storage {
    static let shared = Storage()
    var deleted: [String] = []
    func deleteApps(_ apps: [AppInfoPresentable]) { deleted += apps.compactMap(\.uuid) }
    func deleteApp(for app: AppInfoPresentable) { deleteApps([app]) }
}
@MainActor enum StorageManager {
    static var purges = 0
    static func purgeCaches() { purges += 1 }
}
struct BackgroundTaskManager {
    init(taskName: String, expirationTitle: String, expirationBody: String) {}
    func start() {}
    func stop() {}
}
@MainActor final class AppInstaller {
    enum Outcome { case installed, cancelled, finishedUnverified, exported(URL?) }
    static var instances: [AppInstaller] = []
    let app: AppInfoPresentable
    var callback: ((Result<Outcome, Error>) -> Void)?
    var stopped = false
    init(app: AppInfoPresentable) { self.app = app; Self.instances.append(self) }
    func start(_ callback: @escaping (Result<Outcome, Error>) -> Void) { self.callback = callback }
    func stop() { stopped = true } // Retain callback to exercise defensive stale-callback rejection.
    func finish(_ outcome: Result<Outcome, Error>) { callback?(outcome) }
}
@MainActor func until(_ check: () -> Bool) async {
    let deadline = Date().addingTimeInterval(3)
    while !check() { precondition(Date() < deadline); await Task.yield() }
}
'''
checks = r'''
@main struct Check {
    @MainActor static func main() async {
        defer { defaults.removePersistentDomain(forName: suite) }
        defaults.set(true, forKey: InstallCleanup.deleteKey)
        defaults.set(true, forKey: InstallCleanup.clearCacheKey)
        let runner = BatchJobRunner(apps: [Signed("ok"), Signed("failed"), Signed("unknown"), Signed("skip")],
                                    mode: .install, options: Options(), certificate: nil)
        let task = Task { await runner.run() }
        await until { AppInstaller.instances.count == 1 }
        AppInstaller.instances[0].finish(.success(.installed))
        await until { AppInstaller.instances.count == 2 }
        AppInstaller.instances[1].finish(.failure(NSError(domain: "fixture", code: 1)))
        await until { AppInstaller.instances.count == 3 }
        AppInstaller.instances[2].finish(.success(.finishedUnverified))
        await until { AppInstaller.instances.count == 4 }
        runner.skipCurrentInstall()
        AppInstaller.instances[3].finish(.success(.installed)) // Too late: user already skipped.
        await task.value
        assert(runner.succeeded == 1 && runner.failed == 2)
        assert(Storage.shared.deleted.isEmpty && StorageManager.purges == 0)
        assert(AppInstaller.instances.allSatisfy(\.stopped))
        runner.retire()
        runner.retire()
        await runner.run()
        assert(Storage.shared.deleted == ["ok"] && StorageManager.purges == 1)

        // Cancel/dismiss immediately after confirmation, before the resumed runner executes.
        let cancelled = BatchJobRunner(apps: [Signed("confirmed"), Signed("pending")],
                                       mode: .install, options: Options(), certificate: nil)
        let cancellation = Task { await cancelled.run() }
        await until { AppInstaller.instances.count == 5 }
        AppInstaller.instances[4].finish(.success(.installed))
        cancelled.retire()
        assert(Storage.shared.deleted == ["ok"]) // Work has not retired yet.
        await cancellation.value
        assert(Storage.shared.deleted == ["ok", "confirmed"])
        assert(AppInstaller.instances.count == 5 && StorageManager.purges == 2 && cancelled.succeeded == 1)

        // Sign-and-install cleans the new signed copy, never the input identity.
        let combined = BatchJobRunner(apps: [Signed("input")], mode: .signAndInstall,
                                      options: Options(), certificate: nil)
        let combinedTask = Task { await combined.run() }
        await until { AppInstaller.instances.count == 6 }
        AppInstaller.instances[5].finish(.success(.installed))
        await combinedTask.value
        combined.retire()
        assert(Storage.shared.deleted == ["ok", "confirmed", "input-signed"])

        defaults.set(false, forKey: InstallCleanup.deleteKey)
        defaults.set(false, forKey: InstallCleanup.clearCacheKey)
        let kept = BatchJobRunner(apps: [Signed("keep")], mode: .install, options: Options(), certificate: nil)
        let keepTask = Task { await kept.run() }
        await until { AppInstaller.instances.count == 7 }
        AppInstaller.instances[6].finish(.success(.installed))
        await keepTask.value
        kept.retire()
        assert(Storage.shared.deleted.count == 3 && StorageManager.purges == 3)
        let signOnly = BatchJobRunner(apps: [Signed("sign")], mode: .sign, options: Options(), certificate: nil)
        await signOnly.run()
        signOnly.retire()
        assert(Storage.shared.deleted.count == 3 && AppInstaller.instances.count == 7)
        defaults.set(true, forKey: InstallCleanup.deleteKey)
        let partial = BatchJobRunner(apps: [Signed("earlier"), Signed("cancelled")],
                                     mode: .install, options: Options(), certificate: nil)
        let partialTask = Task { await partial.run() }
        await until { AppInstaller.instances.count == 8 }
        AppInstaller.instances[7].finish(.success(.installed))
        await until { AppInstaller.instances.count == 9 }
        partial.retire()
        AppInstaller.instances[8].finish(.success(.installed))
        await partialTask.value
        assert(Storage.shared.deleted.last == "earlier" && Storage.shared.deleted.count == 4)
        assert(StorageManager.purges == 3) // Delete-only setting remains independent.
        assert(partial.succeeded == 1)
        print("PASS: confirmed-only batch cleanup, dismissal boundary, failures/unverified/skip preservation, cancellation race, exactly-once cleanup, settings and signed-output identity")
    }
}
'''
with tempfile.TemporaryDirectory(prefix='korsign-batch-cleanup-') as directory:
    path = Path(directory)
    (path / 'Check.swift').write_text(stubs + source + checks)
    subprocess.run(['swiftc', '-parse-as-library', '-O', '-assert-config', 'Debug',
                    str(path / 'Check.swift'), '-o', str(path / 'check')], check=True)
    subprocess.run([str(path / 'check')], check=True, timeout=15)
