"""Exercise the production queue with disposable installers, without iOS/network."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
source = (root / "KorSign/Backend/Observable/InstallQueue.swift").read_text()
for module in ("SwiftUI", "NimbleExtensions", "IDeviceSwift"):
    source = source.replace("import " + module, "")
source = source.replace("private ", "").replace("UserDefaults.standard", "defaults")
stubs = r"""
import Foundation
import Combine
let suite = "QueueTest-" + UUID().uuidString
let defaults = UserDefaults(suiteName: suite)!
protocol AppInfoPresentable { var id: String { get } }
struct TestApp: AppInfoPresentable { let id: String }
struct AnyApp { let base: AppInfoPresentable; let archive: Bool; var id: String { base.id } }
enum FileLogger {
 static func log(_ value: String, category: String) {}
 static func error(_ value: String, category: String) {}
}
extension String { static func localized(_ value: String) -> String { value } }
@MainActor final class UIApplication {
 enum State: Int { case active, background }
 static let shared = UIApplication()
 static let didBecomeActiveNotification = Notification.Name("active")
 var applicationState = State.active
}
@MainActor final class InstallQueueWindow {
 static let shared = InstallQueueWindow()
 func ensure() {}
 func teardown() {}
}
@MainActor final class HeartbeatManager {
 static let shared = HeartbeatManager()
 func start(_ value: Bool) {}
}
@MainActor enum UIAlertController {
 static var actions: [() -> Void] = []
 static func showAlertWithOk(title: String, message: String, action: @escaping () -> Void) { actions.append(action) }
}
@MainActor enum UIActivityViewController { static func show(activityItems: [URL]) {} }
@MainActor enum InstallCleanup {
 static var removed: [String] = []
 static func run(for apps: [AppInfoPresentable]) { removed += apps.map { $0.id } }
}
@MainActor final class AppInstaller {
 enum Outcome { case installed, finishedUnverified, cancelled, exported(URL?) }
 let app: AppInfoPresentable
 var onDownloadStarted: (() -> Void)?
 var hasStartedDownload = false
 var stopped = false
 var prepared = false
 var completion: ((Result<Outcome, Error>) -> Void)?
 init(app: AppInfoPresentable, isSharing: Bool = false) { self.app = app }
 func start(completion: @escaping (Result<Outcome, Error>) -> Void) { self.completion = completion }
 func stop() { stopped = true; hasStartedDownload = false }
 func prepare() { prepared = true }
 func presentInstallIfReady() {}
 func download() { hasStartedDownload = true; onDownloadStarted?() }
 func finish(_ result: Result<Outcome, Error>) { hasStartedDownload = false; completion?(result) }
}
"""
checks = r"""
@main struct Check {
 @MainActor static func main() async throws {
  defer { defaults.removePersistentDomain(forName: suite) }
  defaults.set(true, forKey: InstallQueue.dismissAfterInstallKey)
  let q = InstallQueue.shared
  q.enqueue(TestApp(id: "one"))
  let first = q.installer!
  q.enqueue(TestApp(id: "two"))
  q.enqueue(TestApp(id: "three"))
  assert(q.installer === first && q.index == 0)
  first.download()
  let second = q.installer!
  assert(q.index == 1 && !first.stopped && q._running.count == 1)
  first.download() // Duplicate HTTP activity cannot skip a prompt.
  assert(q.installer === second)
  second.download()
  let third = q.installer!
  assert(q.index == 2 && !second.stopped && q._running.count == 2)
  third.finish(.success(.installed))
  assert(!q.isFinished && q._running.count == 2)
  second.finish(.success(.finishedUnverified))
  assert(!q.isFinished)
  first.finish(.success(.installed))
  assert(q.isFinished && q._running.isEmpty)
  q.sheetDismissed()
  assert(Set(InstallCleanup.removed) == Set(["one", "three"]))

  // Appending after download started also overlaps, without stopping its server.
  q.enqueue(TestApp(id: "four"))
  let fourth = q.installer!
  fourth.download()
  q.enqueue(TestApp(id: "five"))
  let fifth = q.installer!
  assert(q.index == 1 && !fourth.stopped)
  fourth.finish(.failure(NSError(domain: "fixture", code: 1)))
  try await Task.sleep(nanoseconds: 30_000_000)
  assert(q.installer === fifth && !fifth.stopped)
  UIAlertController.actions.removeFirst()()
  assert(q.installer === fifth && !fifth.stopped)
  fifth.finish(.success(.installed))
  q.sheetDismissed()

  // Skipping the last prompt keeps previously accepted installs alive.
  q.enqueue(TestApp(id: "six"))
  let sixth = q.installer!
  q.enqueue(TestApp(id: "seven"))
  sixth.download()
  q.skip()
  assert(!sixth.stopped && !q.isFinished)
  sixth.finish(.success(.installed))
  assert(q.current == nil)
  // A finished last card can accept a new item while earlier installs remain.
  q.enqueue(TestApp(id: "eight"))
  let eighth = q.installer!
  q.enqueue(TestApp(id: "nine"))
  eighth.download()
  let ninth = q.installer!
  ninth.finish(.success(.installed))
  q.enqueue(TestApp(id: "ten"))
  let tenth = q.installer!
  assert(q._running.count == 1 && q.installer !== ninth)
  eighth.finish(.success(.installed))
  assert(q.installer === tenth && !q.isFinished)
  tenth.finish(.success(.installed))
  q.sheetDismissed()
  // iDevice preparation starts ahead, but device installs retain queue order.
  q.clear()
  defaults.set(1, forKey: "Feather.installationMethod")
  q.enqueue(TestApp(id: "prep-one"))
  let active = q.installer!
  q.enqueue(TestApp(id: "prep-two"))
  q.enqueue(TestApp(id: "prep-three"))
  let preparedSecond = q._prepared["prep-two"]!
  let preparedThird = q._prepared["prep-three"]!
  assert(preparedSecond.prepared && preparedThird.prepared)
  assert(preparedSecond.completion == nil && preparedThird.completion == nil)
  assert(q.installer === active)
  q.skip()
  assert(q.installer === preparedSecond && preparedSecond.completion != nil)
  q.clear()
  assert(preparedSecond.stopped && preparedThird.stopped && q._prepared.isEmpty)
  q.enqueue(TestApp(id: "fresh"))
  assert(q.installer!.app.id == "fresh")
  q.clear()
  print("PASS: overlapping queue, duplicate activity, out-of-order completion, verified cleanup, late enqueue, failure isolation and skip")
 }
}
"""
with tempfile.TemporaryDirectory(prefix="korsign-queue-") as directory:
    path = Path(directory)
    (path / "Check.swift").write_text(stubs + source + checks)
    subprocess.run(["swiftc", "-parse-as-library", str(path / "Check.swift"), "-o", str(path / "check")], check=True)
    subprocess.run([str(path / "check")], check=True)
