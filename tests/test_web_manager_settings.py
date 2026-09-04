"""Production Web Manager settings/lifecycle with fake listeners and isolated defaults."""
from pathlib import Path
import subprocess
import tempfile
root = Path(__file__).resolve().parents[1]
source = (root / 'KorSign/Backend/Observable/WebManager.swift').read_text()
source = source.replace('import UIKit', 'import Combine').replace('UserDefaults.standard', 'defaults')
source = source.replace('private init()', 'init()').replace('@objc private func', 'private func')
start = source.index('\n\t\tNotificationCenter.default.addObserver(')
end = source.index('\n\t}\n', start)
source = source[:start] + source[end:]
stubs = r'''
import Foundation
import OSLog
let suite = "KorSignWebSettings-" + UUID().uuidString
let defaults = UserDefaults(suiteName: suite)!
extension String {
    static func localized(_ text: String) -> String { text }
    static func localized(_ text: String, arguments: CVarArg...) -> String { text }
}
extension Logger { static let misc = Logger(subsystem: "WebSettingsTest", category: "test") }
enum Toast { static func success(_ message: String, systemImage: String) {} }
enum ServerInstaller { static func getLocalAddress() -> String? { "127.0.0.1" } }
class BackgroundTaskManager {
    init(taskName: String, expirationTitle: String, expirationBody: String) {}
    func start() {}
    func stop() {}
}
final class WebManagerServer {
    struct Auth { let username: String; let password: String }
    static var created = 0
    static var stopped = 0
    static var failStart = false
    let port: Int
    let auth: Auth?
    var requiresAuthentication: Bool { auth != nil }
    init(port: Int, auth: Auth?, onReceive: (String) -> Void) throws {
        if Self.failStart { throw NSError(domain: "fixture", code: 1) }
        self.port = port
        self.auth = auth
        Self.created += 1
    }
    func shutdown() { Self.stopped += 1 }
}
'''
checks = r'''
@main struct Check {
    static func main() {
        defer { defaults.removePersistentDomain(forName: suite) }
        let manager = WebManager()
        assert(manager.username == "korsign")
        defaults.set("ryuk", forKey: "Feather.webManager.user")
        assert(WebManager().username == "korsign")
        assert(defaults.string(forKey: "Feather.webManager.user") == "korsign")
        defaults.set("custom-user", forKey: "Feather.webManager.user")
        assert(WebManager().username == "custom-user")
        manager.requireAuth = true
        manager.username = "fixture-user"
        manager.password = ""
        manager.start()
        assert(!manager.isRunning && manager.lastError != nil && WebManagerServer.created == 0)
        manager.password = "fixture-password"
        manager.username = ""
        manager.start()
        assert(!manager.isRunning && WebManagerServer.created == 0)
        manager.username = "fixture-user"
        manager.port = 0
        manager.start()
        assert(!manager.isRunning && WebManagerServer.created == 0)
        manager.port = 8080
        manager.start()
        assert(manager.isRunning && manager.authActive && manager.lastError == nil)
        assert(WebManagerServer.created == 1)
        manager.start()
        assert(WebManagerServer.created == 1)
        // Even a non-UI settings write cannot make status/URLs describe a different listener.
        manager.requireAuth = false
        manager.port = 9090
        assert(manager.authActive && manager.httpURL == "http://127.0.0.1:8080/")
        assert(manager.webdavURL == "dav://127.0.0.1:8080/")
        manager.stop()
        assert(!manager.isRunning && !manager.authActive)
        manager.start()
        assert(manager.isRunning && !manager.authActive && manager.httpURL.hasSuffix(":9090/"))
        manager.stop()
        manager.requireAuth = true
        manager.start()
        assert(manager.isRunning && manager.authActive)
        manager.stop()
        WebManagerServer.failStart = true
        manager.start()
        assert(!manager.isRunning && !manager.authActive && manager.lastError != nil)
        WebManagerServer.failStart = false
        manager.start()
        assert(manager.isRunning && manager.authActive && manager.lastError == nil)
        manager.stop()
        print("PASS: required credentials fail closed, port validation, active auth/URL snapshots, stop/edit/start, startup failure and retry")
    }
}
'''
with tempfile.TemporaryDirectory(prefix='korsign-web-settings-') as directory:
    path = Path(directory)
    (path / 'Check.swift').write_text(stubs + source + checks)
    subprocess.run(['swiftc', '-parse-as-library', '-O', '-assert-config', 'Debug',
                    str(path / 'Check.swift'), '-o', str(path / 'check')], check=True)
    subprocess.run([str(path / 'check')], check=True, timeout=15)
