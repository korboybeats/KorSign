"""Exercise the production handoff with simulated iOS lifecycle events."""
from pathlib import Path
import subprocess
import tempfile
source = Path('KorSign/Backend/Observable/SelfUpdateManager.swift').read_text()
start = source.index('\t@MainActor\n\tprivate func installViaServer')
end = source.index('\n\t/// Progress can show activity', start)
method = source[start:end].replace('private func', 'func')
program = '''import Foundation
struct SelfUpdateRelease { let version = "3.0.1" }
struct CertificatePair {}
extension String { static func localized(_ text: String) -> String { text } }
enum Phase { case signing, installing }
enum Cancelled: Error { case cancelled }
@MainActor enum Task {
    static var cancelled = false
    static var sleeps = 0
    static func checkCancellation() throws { if cancelled { throw Cancelled.cancelled } }
    static func sleep(nanoseconds: UInt64) async throws { sleeps += 1 }
}
@MainActor final class Observation { func cancel() { NotificationCenter.default.handler = nil } }
@MainActor final class NotificationCenter {
    static let `default` = NotificationCenter()
    var handler: ((Int) -> Void)?
    func publisher(for: String) -> NotificationCenter { self }
    func sink(_ callback: @escaping (Int) -> Void) -> Observation { handler = callback; return Observation() }
}
@MainActor final class UIApplication {
    enum State { case active, inactive, background }
    static let shared = UIApplication()
    static let willResignActiveNotification = "resign"
    var states: [State] = [.active]
    var applicationState: State { states.count > 1 ? states.removeFirst() : states[0] }
    var openResult = true
    var showsPrompt = true
    var suspensions = 0
    func open(_ url: URL) async -> Bool {
        if showsPrompt { NotificationCenter.default.handler?(0) }
        return openResult
    }
    func suspend(exitAfterSuspending: Bool) { assert(!exitAfterSuspending); suspensions += 1 }
}
@MainActor final class Manager {
    var phase = Phase.signing
    var polls = 0
    func requestServerSign(version: String, certificate: CertificatePair) async throws -> URL { URL(string:"https://example.test")! }
    func pollInstallProgress(generation: Int) async throws { polls += 1 }
    func checkFlow(_ generation: Int) throws { try Task.checkCancellation() }
''' + method + '''
}
@main struct Check {
    @MainActor static func main() async throws {
        let app = UIApplication.shared
        for scenario in 0..<5 {
            app.states = scenario == 2 ? [.active, .background] : [.active, .inactive, .active]
            app.openResult = scenario != 1
            app.showsPrompt = scenario != 3
            app.suspensions = 0
            Task.cancelled = scenario == 4
            Task.sleeps = 0
            let manager = Manager()
            do { _ = try await manager.installViaServer(release: SelfUpdateRelease(), certificate: CertificatePair(), generation: 1) }
            catch { assert([1,4].contains(scenario)) }
            assert(app.suspensions == (scenario == 0 ? 1 : 0))
            assert(manager.polls == ([1,4].contains(scenario) ? 0 : 1))
            assert(NotificationCenter.default.handler == nil)
            if scenario == 3 { assert(Task.sleeps == 240) }
        }
        print("PASS: prompt handoff, rejected URL, already backgrounded, missing lifecycle and cancellation")
    }
}
'''
with tempfile.TemporaryDirectory() as temp:
    swift = Path(temp)/'check.swift'
    swift.write_text(program)
    binary = Path(temp)/'check'
    subprocess.run(['swiftc', '-parse-as-library', str(swift), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
