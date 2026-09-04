"""Production updater flow/polling with controlled callbacks; no network, device or app data."""
from pathlib import Path
import subprocess
import tempfile
root = Path(__file__).resolve().parents[1]
source = (root / 'KorSign/Backend/Observable/SelfUpdateManager.swift').read_text()
phase = source[source.index('enum SelfUpdatePhase:'):source.index('\nfinal class SelfUpdateManager:')]
flow = source[source.index('\t/// One cancellable task'):source.index('\n\t/// IDeviceSwift errors')]
poll = source[source.index('\t/// Progress can show activity'):source.index('\n\t@MainActor\n\tprivate func installViaIDevice')]
poll = poll.replace('Bundle.main.bundleIdentifier', 'Optional("fixture")')
poll = poll.replace('try await Task.sleep(nanoseconds: 250_000_000)', 'await Task.yield()')
poll = poll.replace('private func pollInstallProgress', 'func pollInstallProgress')
stubs = r'''
import Foundation
import OSLog
extension String { static func localized(_ text: String) -> String { text } }
extension Logger { static let misc = Logger(subsystem: "UpdaterTest", category: "test") }
enum FileLogger {
    static func log(_ text: String, category: String) {}
    static func error(_ text: String, category: String) {}
}
enum Method { case server, idevice }
struct SelfUpdateRelease { let version = "fixture" }
struct CertificatePair { let nickname: String? = "fixture" }
struct Provision { let Name: String? = nil }
struct Storage {
    static let shared = Storage()
    func getProvisionFileDecoded(for: CertificatePair) -> Provision? { nil }
}
struct BackgroundTaskManager {
    init(taskName: String, expirationTitle: String, expirationBody: String) {}
    func start() {}
    func stop() {}
}
@MainActor enum UIApplication {
    static var values: [Double?] = [nil]
    static var reads = 0
    static func installProgress(for: String) async -> Double? {
        reads += 1
        return values.count > 1 ? values.removeFirst() : values[0]
    }
}
@MainActor final class Manager {
    var _flowGeneration = 0
    var _flow: Task<Void, Never>?
    var phase: SelfUpdatePhase = .idle
    var installProgress = 0.0
    var method = Method.server
    var canSelfInstall = true
    var pending: [Int: CheckedContinuation<Void, Error>] = [:]
    func resolvedCertificate() -> CertificatePair? { CertificatePair() }
    static func describe(_ error: Error) -> String { error.localizedDescription }
    func installViaServer(release: SelfUpdateRelease, certificate: CertificatePair, generation: Int) async throws {
        phase = .signing
        try await withCheckedThrowingContinuation { pending[generation] = $0 }
    }
    func installViaIDevice(release: SelfUpdateRelease, certificate: CertificatePair, generation: Int) async throws {
        try await installViaServer(release: release, certificate: certificate, generation: generation)
    }
    func finish(_ generation: Int, _ result: Result<Void, Error> = .success(())) {
        pending.removeValue(forKey: generation)!.resume(with: result)
    }
'''
checks = r'''
}
@MainActor func until(_ condition: () -> Bool) async {
    let deadline = Date().addingTimeInterval(3)
    while !condition() { precondition(Date() < deadline); await Task.yield() }
}
@main struct Check {
    @MainActor static func main() async throws {
        let m = Manager()
        m.beginUpdate(to: SelfUpdateRelease())
        await until { m.pending[1] != nil }
        let old = m._flow!
        m.beginUpdate(to: SelfUpdateRelease())
        await until { m.pending[2] != nil }
        m.finish(1)
        await old.value
        assert(m.phase == .signing) // Cancelled old success cannot reset current work.
        m.finish(2)
        await m._flow!.value
        assert(m.phase == .unverified) // Server handoff is never verified success.

        m.beginUpdate(to: SelfUpdateRelease())
        await until { m.pending[3] != nil }
        let failing = m._flow!
        m.endFlow()
        m.beginUpdate(to: SelfUpdateRelease())
        await until { m.pending[5] != nil }
        m.finish(3, .failure(NSError(domain: "old", code: 1)))
        await failing.value
        assert(m.phase == .signing)
        m.finish(5)
        await m._flow!.value
        assert(m.phase == .unverified)

        m.method = .idevice
        m.beginUpdate(to: SelfUpdateRelease())
        await until { m.pending[6] != nil }
        m.finish(6)
        await m._flow!.value
        assert(m.phase == .done)

        // Missing/vanished/partial/stalled progress never synthesizes 100 percent.
        for samples: [Double?] in [[nil], [0.7, nil], [0.7, 0], [0.7]] {
            UIApplication.values = samples
            UIApplication.reads = 0
            m.installProgress = 0
            try await m.pollInstallProgress(generation: 6)
            assert(m.installProgress < 1)
            assert(UIApplication.reads <= 2400)
        }
        UIApplication.values = [0.7]
        UIApplication.reads = 0
        let polling = Task { try await m.pollInstallProgress(generation: 6) }
        await until { UIApplication.reads > 0 }
        polling.cancel()
        do { try await polling.value; fatalError("Cancellation swallowed") } catch is CancellationError {}
        do { try await m.pollInstallProgress(generation: 5); fatalError("Stale poll accepted") } catch is CancellationError {}
        print("PASS: stale success/error rejection, server unverified versus proxy completion, missing/vanished/stalled progress and cancellation")
    }
}
'''
with tempfile.TemporaryDirectory(prefix='korsign-updater-flow-') as directory:
    path = Path(directory)
    (path / 'Check.swift').write_text(phase + stubs + flow + poll + checks)
    subprocess.run(['swiftc', '-parse-as-library', '-O', '-assert-config', 'Debug',
                    str(path / 'Check.swift'), '-o', str(path / 'check')], check=True)
    subprocess.run([str(path / 'check')], check=True, timeout=15)
