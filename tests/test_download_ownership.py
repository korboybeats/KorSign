"""Production download ownership methods with fake tasks and temporary files; no network."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
base = root / 'KorSign/Backend/Observable'
source = (base / 'DownloadManager.swift').read_text()
def method(name):
    prefix = '\tfunc ' if '\tfunc ' + name + '(' in source else '\tprivate func '
    start = source.index(prefix + name + '(')
    brace = source.index('{', start)
    depth = 1
    end = brace + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end].replace('private func', 'func')
methods = '\n'.join(method(name) for name in ['startDownload', 'resumeDownload', 'pauseDownload', 'cancelDownload', 'getDownloadTask', 'finishImport'])
delegates = (base / 'DownloadManager+Delegates.swift').read_text()
finish = delegates[delegates.index('\tfunc urlSession('):delegates.index('\n\tfunc urlSession(', delegates.index('\tfunc urlSession(') + 1)]
start = delegates.index('\tfunc urlSession(_ session: URLSession, task:')
complete = delegates[start:delegates.index('\n\tfunc urlSessionDidFinishEvents', start)]
download = (base / 'Download.swift').read_text().split('struct DownloadProgressSummary')[0]
download = '\n'.join(line for line in download.splitlines() if not line.startswith('import '))
program = r'''
import Foundation
@propertyWrapper struct Published<Value> { var wrappedValue: Value }
enum DownloadPhase { case queued, downloading, paused, importing, signing, completed }
// Swift's asynchronous main executor on macOS need not use the OS main thread.
enum Thread { static let isMainThread = true }
var stagingRoot = URL(fileURLWithPath: "/unused")
extension FileManager { var downloadStaging: URL { stagingRoot } }
class URLSessionTask: NSObject {}
final class URLSessionDownloadTask: URLSessionTask {
    var response: URLResponse? = nil
    enum State { case suspended, running, canceling, completed }
    var state = State.suspended
    var priority: Float = 0
    var originalRequest: URLRequest?
    var callback: ((Data?) -> Void)?
    var onResume: (() -> Void)?
    func resume() { state = .running; onResume?() }
    func cancel() { state = .canceling }
    func cancel(_ callback: @escaping (Data?) -> Void) { state = .canceling; self.callback = callback }
    func finishPause(_ data: Data?) { state = .completed; let cb = callback; callback = nil; cb?(data) }
}
final class URLSession {
    var tasks: [URLSessionDownloadTask] = []
    var onResume: ((URLSessionDownloadTask) -> Void)?
    func downloadTask(with request: URLRequest) -> URLSessionDownloadTask {
        let task = URLSessionDownloadTask(); task.originalRequest = request
        task.onResume = { [weak self, weak task] in if let task { self?.onResume?(task) } }
        tasks.append(task); return task
    }
    func downloadTask(withResumeData data: Data) -> URLSessionDownloadTask {
        downloadTask(with: URLRequest(url: URL(string: "https://example.invalid/resume")!))
    }
}
final class UIApplication { static let shared = UIApplication(); var delegate: AnyObject? = nil }
final class AppDelegate { func submitContinuedProcessingTask() {} }
final class UNUserNotificationCenter {
    static let center = UNUserNotificationCenter()
    static func current() -> UNUserNotificationCenter { center }
    func removeDeliveredNotifications(withIdentifiers: [String]) {}
}
final class Publisher { func send() {} }
''' + download + r'''
final class DownloadManager {
    static let shared = DownloadManager()
    var downloads: [Download] = []
    var isAppInBackground = false
    var _foregroundSession: URLSession! = URLSession()
    var _backgroundSession: URLSession! = URLSession()
    var objectWillChange = Publisher()
    var downloadActivity: Int? = nil
    var allActivityDownloads: [String: Int] = [:]
    var finishedDownloadingIDs: Set<String> = []
    var saved: [String: Data] = [:]
    var completedDownloadNames: [String] = []
    func endImport(for download: Download) { download.endImport() }
    func saveResumeData(for download: Download) { saved[download.id] = download.resumeData }
    func loadResumeData(for download: Download) -> Data? { saved[download.id] }
    func startProgressTimer() {}
    func ensureKeepAlive() {}
    func startLiveActivityIfNeeded() {}
    func forceNextProgressUpdate() {}
    func updateLiveActivity(activeDownloads: [Download]) {}
    func endLiveActivity() {}
    func releaseKeepAliveIfIdle() {}
    func dismissLiveActivityImmediately() {}
    func updateLiveActivityWithPausedState(activeDownloads: [Download]) {}
    func getDownloadIndex(by id: String) -> Int? { downloads.firstIndex(where: { $0.id == id }) }
    func sendCompletionNotification(for download: Download, status: String) {}
    func sendSystemNotification(title: String, body: String, identifier: String) {}
    func showUIErrorMessage(for download: Download, error: NSError) {}
    var imports: [URL] = []
    func handlePackageFile(url: URL, dl: Download) throws {
        dl.pendingFileURL = url; dl.beginImport(); imports.append(url)
    }
''' + methods + '\n' + finish + complete + r'''
}
@main struct Check {
    static func drain() async { await withCheckedContinuation { c in DispatchQueue.main.async { c.resume() } } }
    @MainActor static func main() async throws {
        stagingRoot = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
        let manager = DownloadManager()
        let session = manager._foregroundSession!
        session.onResume = { task in assert(manager.getDownloadTask(by: task) != nil) }
        let url = URL(string: "https://example.invalid/app.ipa")!
        let first = manager.startDownload(from: url, id: "first")
        let original = first.task!
        assert(manager.startDownload(from: url) === first)
        assert(manager.startDownload(from: URL(string: "https://example.invalid/version.ipa")!, id: "first") === first)
        manager.resumeDownload(first)
        assert(session.tasks.count == 1 && first.task === original)
        manager.pauseDownload(first)
        manager.resumeDownload(first)
        manager.resumeDownload(first)
        assert(first.isPausing && session.tasks.count == 1)
        original.finishPause(Data([1]))
        await drain()
        assert(session.tasks.count == 2 && first.isActive && !first.isPaused)
        assert(manager.getDownloadTask(by: original) == nil)
        assert(first.resumeData == nil && manager.saved[first.id] == nil)
        manager.resumeDownload(first)
        assert(session.tasks.count == 2)

        let secondTask = first.task!
        manager.pauseDownload(first)
        manager.resumeDownload(first)
        manager.cancelDownload(first)
        let replacement = manager.startDownload(from: url, id: "first")
        secondTask.finishPause(Data([2]))
        await drain()
        assert(session.tasks.count == 3 && replacement.isActive)
        assert(manager.saved[replacement.id] == nil)
        manager.cancelDownload(first) // Stale UI reference must not cancel its replacement.
        assert(manager.downloads.contains(where: { $0 === replacement }))

        // A recoverable failure with no resume data restarts once from the URL.
        replacement.task?.state = .completed
        manager.saved[replacement.id] = Data([9])
        manager.urlSession(session, task: replacement.task!, didCompleteWithError: NSError(domain: NSURLErrorDomain, code: NSURLErrorTimedOut))
        assert(manager.saved[replacement.id] == nil && replacement.isPaused)
        replacement.progress = 0.5; replacement.bytesDownloaded = 10
        manager.resumeDownload(replacement)
        manager.resumeDownload(replacement)
        assert(session.tasks.count == 4 && replacement.progress == 0 && replacement.bytesDownloaded == 0)
        replacement.beginImport()
        replacement.isPaused = true
        manager.resumeDownload(replacement)
        manager.pauseDownload(replacement)
        assert(session.tasks.count == 4 && !replacement.isPausing)
        manager.cancelDownload(replacement)
        assert(manager.downloads.contains(where: { $0 === replacement }))

        let completing = manager.startDownload(from: URL(string: "https://example.invalid/finished.ipa")!, id: "completing")
        let completingTask = completing.task!
        manager.pauseDownload(completing)
        manager.resumeDownload(completing)
        let temp = stagingRoot.appendingPathComponent("session.tmp")
        try Data("finished".utf8).write(to: temp)
        manager.urlSession(session, downloadTask: completingTask, didFinishDownloadingTo: temp)
        assert(completing.isImporting && completing.task == nil && manager.imports.count == 1)
        let tasksBeforeLateCallback = session.tasks.count
        completingTask.finishPause(Data([3]))
        manager.urlSession(session, task: completingTask, didCompleteWithError: NSError(domain: NSURLErrorDomain, code: NSURLErrorCancelled))
        await drain()
        assert(session.tasks.count == tasksBeforeLateCallback && completing.resumeData == nil)
        assert(try! Data(contentsOf: manager.imports[0]) == Data("finished".utf8))
        manager.finishImport(of: completing, succeeded: true)
        assert(!FileManager.default.fileExists(atPath: manager.imports[0].path))

        // Matching server filenames cannot overwrite another download's input.
        let a = Download(id: "same", url: url)
        let b = Download(id: "same", url: url)
        let inputA = stagingRoot.appendingPathComponent("a.tmp")
        let inputB = stagingRoot.appendingPathComponent("b.tmp")
        try Data("A".utf8).write(to: inputA)
        try Data("B".utf8).write(to: inputB)
        let outputA = try a.stageFile(at: inputA, suggestedFilename: "../app.ipa")
        let outputB = try b.stageFile(at: inputB, suggestedFilename: "../app.ipa")
        assert(outputA != outputB && outputA.lastPathComponent == "app.ipa")
        assert(try! Data(contentsOf: outputA) == Data("A".utf8))
        assert(try! Data(contentsOf: outputB) == Data("B".utf8))
        try Data("C".utf8).write(to: inputA)
        var rejected = false
        do { _ = try a.stageFile(at: inputA, suggestedFilename: "app.ipa") } catch { rejected = true }
        assert(rejected && (try! Data(contentsOf: outputA)) == Data("A".utf8))
        a.removeStagedFiles()
        assert(try! Data(contentsOf: outputB) == Data("B".utf8))
        assert(FileManager.default.fileExists(atPath: inputA.path))
        let local = Download(id: "local", url: inputA, onlyArchiving: true)
        manager.downloads.append(local)
        manager.finishImport(of: local, succeeded: false)
        assert(FileManager.default.fileExists(atPath: inputA.path))
        print("PASS: registration before callbacks, duplicate starts/resumes, pause/resume/cancel races, retry, stale references, staging isolation and cleanup")
    }
}
'''
with tempfile.TemporaryDirectory(prefix='korsign-download-check-') as directory:
    work = Path(directory)
    main = work / 'Check.swift'
    main.write_text(program)
    binary = work / 'check'
    subprocess.run(['swiftc', '-parse-as-library', str(main), '-o', str(binary)], check=True)
    subprocess.run([str(binary), directory], check=True)
