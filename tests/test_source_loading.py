"""Run the production source loader with manually completed callbacks; no network or app data."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
source = (root / 'KorSign/Views/Sources/SourcesViewModel.swift').read_text()
for module in ['AltSourceKit', 'SwiftUI', 'NimbleJSON']:
    source = source.replace(f'import {module}', '')
stubs = r'''
import Foundation
import Combine
import OSLog
extension Logger { static let misc = Logger(subsystem: "SourceLoadingTest", category: "test") }
struct ASRepository { let name: String }
struct AltSource: Hashable {
    let name: String?
    var sourceURL: URL? { URL(string: "https://example.invalid/" + name!) }
}
final class FetchedResults<Element>: RandomAccessCollection {
    var values: [Element]
    init(_ values: [Element]) { self.values = values }
    var startIndex: Int { values.startIndex }
    var endIndex: Int { values.endIndex }
    subscript(index: Int) -> Element { values[index] }
}
final class NBFetchService {
    static let lock = NSLock()
    static var pending: [(URL, (Result<ASRepository, Error>) -> Void)] = []
    static var count: Int { lock.lock(); defer { lock.unlock() }; return pending.count }
    func fetch(from url: URL, completion: @escaping (Result<ASRepository, Error>) -> Void) {
        Self.lock.lock(); defer { Self.lock.unlock() }
        Self.pending.append((url, completion))
    }
    static func finish(_ index: Int, _ name: String) {
        lock.lock(); let callback = pending[index].1; lock.unlock()
        callback(.success(ASRepository(name: name)))
    }
    static func url(_ index: Int) -> URL {
        lock.lock(); defer { lock.unlock() }; return pending[index].0
    }
}
final class BackgroundTaskManager {
    static var instances: [BackgroundTaskManager] = []
    var stopped = false
    init(taskName: String, expirationTitle: String, expirationBody: String) { Self.instances.append(self) }
    func start() {}
    func stop() { stopped = true }
}
@MainActor func until(_ condition: () -> Bool) async {
    let deadline = Date().addingTimeInterval(4)
    while !condition() {
        precondition(Date() < deadline, "Timed out")
        await Task.yield()
    }
}
'''
checks = r'''
@main struct Check {
    @MainActor static func main() async {
        let a = AltSource(name: "A"), b = AltSource(name: "B"), c = AltSource(name: "C")
        let model = SourcesViewModel()
        // A is cancelled while its callback remains alive; B owns the new background task.
        let first = Task { await model.fetchSources(FetchedResults([a, c]), batchSize: 1) }
        await until { NBFetchService.count == 1 }
        model.resetLoadingState()
        let second = Task { await model.fetchSources(FetchedResults([b])) }
        await until { NBFetchService.count == 2 }
        let active = BackgroundTaskManager.instances.last!
        NBFetchService.finish(0, "stale A")
        await first.value
        assert(!model.isFinished && !active.stopped && model.sources.isEmpty)
        assert(NBFetchService.count == 2) // Cancelled A cannot start its second batch.
        NBFetchService.finish(1, "current B")
        await second.value
        assert(model.isFinished && active.stopped && model.sources[b]?.name == "current B")
        await model.fetchSources(FetchedResults([b]))
        assert(NBFetchService.count == 2) // Stale completion did not corrupt the completed key.

        // Inverse completion order: old results arrive after the replacement has completed.
        let old = Task { await model.fetchSources(FetchedResults([a]), refresh: true) }
        await until { NBFetchService.count == 3 }
        model.resetLoadingState()
        let fresh = Task { await model.fetchSources(FetchedResults([b]), refresh: true) }
        await until { NBFetchService.count == 4 }
        NBFetchService.finish(3, "new B")
        await fresh.value
        NBFetchService.finish(2, "old A")
        await old.value
        assert(model.sources[b]?.name == "new B" && model.sources[a] == nil && model.isFinished)
        await model.fetchSources(FetchedResults([b]))
        assert(NBFetchService.count == 4)

        // Identical concurrent requests still coalesce; pull-to-refresh still fetches.
        let refresh = Task { await model.fetchSources(FetchedResults([b]), refresh: true) }
        await until { NBFetchService.count == 5 }
        let coalesced = Task { await model.fetchSources(FetchedResults([b])) }
        for _ in 0..<20 { await Task.yield() }
        NBFetchService.finish(4, "refreshed")
        await refresh.value
        await coalesced.value
        assert(NBFetchService.count == 5 && model.sources[b]?.name == "refreshed")

        // A cancelled waiting caller cannot start another load once the active one finishes.
        let running = Task { await model.fetchSources(FetchedResults([b]), refresh: true) }
        await until { NBFetchService.count == 6 }
        let waiter = Task { await model.fetchSources(FetchedResults([a])) }
        for _ in 0..<20 { await Task.yield() }
        waiter.cancel()
        NBFetchService.finish(5, "B again")
        await running.value
        await waiter.value
        assert(NBFetchService.count == 6 && model.sources[b]?.name == "B again")

        // Read the live source list after waiting, so deleted entries are not resurrected.
        let blocking = Task { await model.fetchSources(FetchedResults([b]), refresh: true) }
        await until { NBFetchService.count == 7 }
        let live = FetchedResults([a])
        let waiting = Task { await model.fetchSources(live) }
        for _ in 0..<20 { await Task.yield() }
        live.values = [c]
        NBFetchService.finish(6, "B")
        await blocking.value
        await until { NBFetchService.count == 8 }
        assert(NBFetchService.url(7) == c.sourceURL)
        NBFetchService.finish(7, "C")
        await waiting.value
        assert(model.sources[c]?.name == "C" && model.sources[a] == nil)
        await model.fetchSources(FetchedResults([]))
        assert(model.sources.isEmpty && model.isFinished)
        print("PASS: stale callback publication/cleanup, stopped batches, cache/coalescing, refresh, cancelled waiters, live snapshots and empty lists")
    }
}
'''
with tempfile.TemporaryDirectory(prefix='korsign-source-loading-') as directory:
    path = Path(directory)
    (path / 'Check.swift').write_text(stubs + source + checks)
    subprocess.run(['swiftc', '-parse-as-library', '-O', '-assert-config', 'Debug',
                    str(path / 'Check.swift'), '-o', str(path / 'check')], check=True)
    subprocess.run([str(path / 'check')], check=True, timeout=20)
