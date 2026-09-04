"""Production updater download ownership with isolated files and a fake async transport."""
from pathlib import Path
import subprocess
import tempfile
root = Path(__file__).resolve().parents[1]
source = (root / 'KorSign/Backend/Observable/SelfUpdateManager.swift').read_text()
method = source[source.index('\t@MainActor\n\tprivate func download('):source.index('\n/// One delegate per download')]
method = method.replace('private func download', 'func download').replace('FileManager.default.temporaryDirectory', 'testRoot')
delegate = source[source.index('private final class SelfUpdateDownloadProgress'):source.index('\nprivate extension Data')]
program = r'''
import Foundation
let testRoot = URL(fileURLWithPath: CommandLine.arguments[1])
protocol URLSessionDownloadDelegate {}
struct URLSessionDownloadTask {}
@MainActor final class URLSession {
    static let shared = URLSession()
    var pending: [(SelfUpdateDownloadProgress, CheckedContinuation<(URL, URLResponse), Error>)] = []
    func download(from: URL, delegate: SelfUpdateDownloadProgress) async throws -> (URL, URLResponse) {
        try await withCheckedThrowingContinuation { pending.append((delegate, $0)) }
    }
    func finish(_ i: Int, status: Int = 200) throws -> URL {
        let file = testRoot.appendingPathComponent("transport-" + String(i))
        try Data("body".utf8).write(to: file)
        let response = HTTPURLResponse(url: URL(string: "https://example.invalid")!, statusCode: status,
                                       httpVersion: nil, headerFields: nil)!
        pending[i].1.resume(returning: (file, response))
        return file
    }
}
enum Phase: Equatable { case downloading(Double), importing }
@MainActor final class Manager {
    var _flowGeneration = 1
    var phase: Phase = .downloading(0)
    func checkFlow(_ generation: Int) throws {
        try Task.checkCancellation()
        guard generation == _flowGeneration else { throw CancellationError() }
    }
''' + method + delegate.replace('private final class', 'final class') + r'''
@MainActor func until(_ check: () -> Bool) async {
    let deadline = Date().addingTimeInterval(3)
    while !check() { precondition(Date() < deadline); await Task.yield() }
}
@main struct Check {
    @MainActor static func main() async throws {
        let m = Manager(), session = URLSession.shared
        let url = URL(string: "https://example.invalid")!
        let first = Task { try await m.download(from: url, generation: 1) }
        await until { session.pending.count == 1 }
        m._flowGeneration = 2
        let second = Task { try await m.download(from: url, generation: 2) }
        await until { session.pending.count == 2 }
        session.pending[0].0.update(0.9)
        for _ in 0..<20 { await Task.yield() }
        assert(m.phase == .downloading(0))
        let oldTemp = try session.finish(0)
        do { _ = try await first.value; fatalError("Old download accepted") } catch is CancellationError {}
        assert(!FileManager.default.fileExists(atPath: oldTemp.path))
        let temp = try session.finish(1)
        let output = try await second.value
        assert(!FileManager.default.fileExists(atPath: temp.path))
        assert(try! Data(contentsOf: output) == Data("body".utf8))
        m.phase = .importing
        session.pending[1].0.update(1)
        for _ in 0..<20 { await Task.yield() }
        assert(m.phase == .importing)
        let third = Task { try await m.download(from: url, generation: 2) }
        await until { session.pending.count == 3 }
        _ = try session.finish(2)
        let other = try await third.value
        assert(output != other && FileManager.default.fileExists(atPath: output.path))
        let bad = Task { try await m.download(from: url, generation: 2) }
        await until { session.pending.count == 4 }
        let badTemp = try session.finish(3, status: 500)
        do { _ = try await bad.value; fatalError("HTTP failure accepted") } catch {}
        assert(!FileManager.default.fileExists(atPath: badTemp.path))
        print("PASS: overlapping download ownership, stale progress rejection, unique output names and HTTP-error cleanup")
    }
}
'''
with tempfile.TemporaryDirectory(prefix='korsign-updater-download-') as directory:
    path = Path(directory)
    (path / 'Check.swift').write_text(program)
    subprocess.run(['swiftc', '-parse-as-library', '-O', '-assert-config', 'Debug',
                    str(path / 'Check.swift'), '-o', str(path / 'check')], check=True)
    subprocess.run([str(path / 'check'), directory], check=True, timeout=15)
