"""Offline prompt lifecycle check: production installer decisions, fake iOS/HTTP/probe."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
source = (root / 'KorSign/Backend/Observable/AppInstaller.swift').read_text()
# Package preparation is covered by test_installation_archive.py; omit real signing/network.
a = source.index('\t// MARK: Pipeline')
b = source.index('\t// MARK: Status')
source = source[:a] + '\tprivate func _run() async {}\n\n' + source[b:]
source = source.replace('import SwiftUI', '').replace('import IDeviceSwift', '')
source = source.replace('private ', '')  # expose lifecycle entry points only in the disposable fixture
source = source.replace('UserDefaults.standard', 'testDefaults')
source = source.replace('Bundle.main.bundleIdentifier?.hasSuffix(".dev") == true', 'isDevDiagnostic')
source = source.replace('Bundle.main.bundleIdentifier!', '"fixture.host"').replace('Bundle.main.name', '"Fixture"')
state = (root / 'KorSign/Backend/Observable/OTAInstallState.swift').read_text()
stubs = r'''
import Foundation
import Combine
var isDevDiagnostic = false
let defaultsName = "KorSignPromptTest-" + UUID().uuidString
let testDefaults = UserDefaults(suiteName: defaultsName)!
protocol AppInfoPresentable { var identifier: String? { get } }
struct TestApp: AppInfoPresentable { let identifier: String? = "fixture.app" }
extension String { static func localized(_ value: String, arguments: String = "") -> String { value } }
enum FileLogger {
    static func log(_ value: String, category: String) {}
    static func error(_ value: String, category: String) {}
}
@MainActor final class UIApplication {
    enum State: Int { case active, inactive, background }
    static let shared = UIApplication()
    static let didBecomeActiveNotification = Notification.Name("fixture.active")
    var applicationState = State.active
    var opens = 0
    var acceptsURL = true
    func open(_ url: URL, completion: (Bool) -> Void) { opens += 1; completion(acceptsURL) }
}
final class InstallerStatusViewModel: ObservableObject {
    enum InstallerStatus {
        case none, ready, sendingManifest, sendingPayload, installing
        case completed(Result<Void, Error>), broken(Error)
    }
    @Published var status = InstallerStatus.none
    var installProgress = 0.0
    init(isIdevice: Bool) {}
}
final class InstallWorkspaceDiagnostic {
    static var active = 0
    init?(identifier: String, log: @escaping (String) -> Void) { Self.active += 1 }
    func stop() { Self.active -= 1 }
}
final class InstalledAppProbe {
    func resetProgress() {}
    func read(_ identifier: String) -> (record: InstalledAppRecord?, progress: InstallProgressReading?) { (nil, nil) }
}
final class ServerInstaller {
    let pageEndpoint = URL(string: "https://example.test/install")!
    let iTunesLink = "itms-services://?url=https://example.test/manifest.plist"
    let iTunesLinkExternal: String? = "itms-services://?url=https://example.test/external.plist"
    var stops = 0
    init(app: AppInfoPresentable, viewModel: InstallerStatusViewModel) throws {}
    func stop() { stops += 1 }
}
'''
checks = r'''
@main struct Check {
    @MainActor static func drain() async throws { try await Task.sleep(nanoseconds: 20_000_000) }
    @MainActor static func main() async throws {
        defer { testDefaults.removePersistentDomain(forName: defaultsName) }
        for dev in [false, true] {
            isDevDiagnostic = dev
            for mode in [0, 1] {
                testDefaults.set(mode, forKey: "Feather.serverMethod")
                UIApplication.shared.acceptsURL = true
                UIApplication.shared.applicationState = .background
                let installer = AppInstaller(app: TestApp())
                var results: [Result<AppInstaller.Outcome, Error>] = []
                installer.start { results.append($0) }
                installer._handle(.ready)
                assert(!(installer._ota.phase == .waiting)) // Packaging/foreground wait isn't a prompt.
                assert(results.isEmpty)
                UIApplication.shared.applicationState = .active
                let opensBefore = UIApplication.shared.opens
                installer.presentInstallIfReady()
                try await drain()
                assert(UIApplication.shared.opens == opensBefore + 1)
                assert((installer._ota.phase == .waiting))
                let opens = UIApplication.shared.opens
                let deadline = installer._ota.deadline
                installer._handle(.sendingManifest)
                installer.presentInstallIfReady() // Foregrounding doesn't reopen or cancel the alert.
                try await drain()
                assert((installer._ota.phase == .waiting) && results.isEmpty)
                assert(UIApplication.shared.opens == opens && installer._ota.deadline == deadline)
                assert(!installer._ota.timedOut(at: deadline! - 1))
                assert(installer._ota.timedOut(at: deadline!))

                let server = installer._server!
                installer.stop() // Existing panel close action abandons without claiming installation.
                installer._handle(.sendingPayload)
                installer._handle(.completed(.success(())))
                assert(results.isEmpty)
                assert(!(installer._ota.phase == .waiting) && installer._progressTask == nil && server.stops == 1)
                assert(installer._ota.phase == .finished)
                assert(InstallWorkspaceDiagnostic.active == 0)

                // A new attempt can accept the prompt and complete normally.
                let retry = AppInstaller(app: TestApp())
                var retryResults: [Result<AppInstaller.Outcome, Error>] = []
                retry.start { retryResults.append($0) }
                retry._handle(.ready)
                try await drain()
                assert((retry._ota.phase == .waiting))
                retry._handle(.sendingPayload)
                assert(!(retry._ota.phase == .waiting))
                assert(retryResults.isEmpty)
                retry._handle(.installing)
                retry._handle(.sendingManifest) // A repeated metadata request cannot regress the UI.
                assert(!(retry._ota.phase == .waiting))
                retry._handle(.completed(.success(())))
                guard case .success(.installed) = retryResults.first else { fatalError("Retry failed") }
                assert(InstallWorkspaceDiagnostic.active == 0)

                let stopped = AppInstaller(app: TestApp())
                stopped.start { _ in fatalError("Stop should not complete") }
                stopped._handle(.ready)
                try await drain()
                stopped.stop()
                assert(!(stopped._ota.phase == .waiting) && stopped._progressTask == nil)
            }
            // URL-open refusal is still fallback, not an inferred cancellation.
            UIApplication.shared.acceptsURL = false
            let fallback = AppInstaller(app: TestApp())
            fallback.start { _ in fatalError("URL refusal is not the user's Cancel choice") }
            fallback._handle(.ready)
            try await drain()
            assert(fallback.isPresentingFallbackPage && (fallback._ota.phase == .waiting))
            fallback.stop()
        }
        print("PASS: prompt waiting, explicit close, teardown, late callbacks, retry, active-transfer guard and fallback")
    }
}
'''
with tempfile.TemporaryDirectory(prefix='korsign-prompt-test-') as directory:
    path = Path(directory)
    swift = path / 'Check.swift'
    swift.write_text(stubs + state + source + checks)
    binary = path / 'check'
    subprocess.run(['xcrun', 'swiftc', '-swift-version', '5', '-parse-as-library', str(swift), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True, timeout=20)
