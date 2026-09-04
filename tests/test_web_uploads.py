"""Offline production upload/replace checks with fake HTTP events and temporary files."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
server = (root / 'KorSign/Backend/Server/WebManagerServer.swift').read_text()
dav = (root / 'KorSign/Backend/Server/WebManagerServer+WebDAV.swift').read_text()
workspace = (root / 'KorSign/Backend/Server/UploadWorkspace.swift').read_text()
stream = server[server.index('\tfunc streamToFile('):server.rindex('\n}')]
copy = server[server.index('\tstatic func stagedCopy('):server.index('\n\tfunc shutdown()')]
resolve = server[server.index('\tfunc resolve('):server.index('\n\tfunc sanitizedFilename')]
move = dav[dav.index('\tprivate func _moveOrCopy('):dav.index('\n\tprivate func _proppatchOK')].replace('private func', 'func')
put = dav[dav.index('\t\t\tlet path = req.url.path'):dav.index('\n\t\tapp.on(.init(rawValue: "MKCOL")')]
put = put[:put.rfind('\n\t\t}')]

stubs = r'''
import Foundation
var copyRoot: URL!
enum Failure: Error { case injected }
final class FileHandle {
    static var failWrite = false, failClose = false, failSync = false
    let real: Foundation.FileHandle
    init(forWritingTo url: URL) throws { real = try Foundation.FileHandle(forWritingTo: url) }
    func write(contentsOf data: Data) throws {
        if Self.failWrite { throw Failure.injected }
        try real.write(contentsOf: data)
    }
    func synchronize() throws {
        if Self.failSync { throw Failure.injected }
        try real.synchronize()
    }
    func close() throws {
        if Self.failClose { Self.failClose = false; throw Failure.injected }
        try real.close()
    }
}
extension FileManager {
    func createDirectoryIfNeeded(at url: URL) throws { try createDirectory(at: url, withIntermediateDirectories: true) }
}
struct HTTPResponseStatus: Equatable {
    let code: Int
    static let ok = Self(code: 200), created = Self(code: 201), noContent = Self(code: 204)
    static let forbidden = Self(code: 403), notFound = Self(code: 404), conflict = Self(code: 409)
    static let preconditionFailed = Self(code: 412), internalServerError = Self(code: 500)
}
struct Response { let status: HTTPResponseStatus }
final class EventLoopFuture<T> {
    var result: Result<T, Error>?
    var completions = 0
    var callbacks: [(Result<T, Error>) -> Void] = []
    func complete(_ result: Result<T, Error>) {
        completions += 1
        assert(completions == 1, "Double completion")
        self.result = result
        callbacks.forEach { $0(result) }
    }
    func map<U>(_ transform: @escaping (T) -> U) -> EventLoopFuture<U> {
        let future = EventLoopFuture<U>()
        let callback: (Result<T, Error>) -> Void = { future.complete($0.map(transform)) }
        if let result { callback(result) } else { callbacks.append(callback) }
        return future
    }
}
final class EventLoopPromise<T> {
    let futureResult = EventLoopFuture<T>()
    func succeed(_ value: T) { futureResult.complete(.success(value)) }
    func fail(_ error: Error) { futureResult.complete(.failure(error)) }
}
struct EventLoop {
    func makePromise<T>(of: T.Type) -> EventLoopPromise<T> { EventLoopPromise<T>() }
    func makeSucceededFuture<T>(_ value: T) -> EventLoopFuture<T> {
        let future = EventLoopFuture<T>(); future.complete(.success(value)); return future
    }
    func makeFailedFuture<T>(_ error: Error) -> EventLoopFuture<T> {
        let future = EventLoopFuture<T>(); future.complete(.failure(error)); return future
    }
}
struct Buffer { let readableBytesView: Data }
enum Part { case buffer(Buffer), error(Error), end }
final class Body {
    var handler: ((Part) -> EventLoopFuture<Void>)!
    func drain(_ handler: @escaping (Part) -> EventLoopFuture<Void>) { self.handler = handler }
    @discardableResult func send(_ part: Part) -> EventLoopFuture<Void> { handler(part) }
}
struct Headers {
    var values: [String: String] = [:]
    func first(name: String) -> String? { values[name] }
}
struct Request {
    let url: URL
    let body = Body()
    let eventLoop = EventLoop()
    var headers = Headers()
}
enum WebManagerRouter {
    enum Destination { case library, inbox }
    static var inputs: [URL] = []
    static var cleanups: [() -> Void] = []
    static func destination(for url: URL) -> Destination { url.pathExtension == "ipa" ? .library : .inbox }
    static func route(_ url: URL, onImported: (() -> Void)? = nil) { inputs.append(url); if let onImported { cleanups.append(onImported) } }
}
final class WebManagerServer {
    let inbox: URL
    var reports = 0, scheduled = 0
    init(_ inbox: URL) { self.inbox = inbox }
    func _onReceive(_ name: String) { reports += 1 }
    func scheduleDebouncedRoute(forPath path: String, url: URL) { scheduled += 1 }
    func _path(fromDestination header: String) -> String? { header }
'''
# Redirect only staging copies into the fixture; production IO and replacement stay real.
copy = copy.replace('fm.temporaryDirectory', 'copyRoot')
program = workspace + stubs + '\n'.join([stream, copy, resolve, move]) + '\nfunc put(_ req: Request, url: URL) -> EventLoopFuture<Response> {\n' + put + '\n}\n}\n'
program += r'''
@main struct Check {
    static func main() throws {
        let fm = FileManager.default
        let root = URL(fileURLWithPath: CommandLine.arguments[1])
        copyRoot = root.appendingPathComponent("copies")
        let inbox = root.appendingPathComponent("inbox")
        try fm.createDirectory(at: inbox, withIntermediateDirectories: true)
        let server = WebManagerServer(inbox)
        let destination = inbox.appendingPathComponent("app.ipa")
        func write(_ text: String, _ url: URL) throws { try Data(text.utf8).write(to: url) }
        func read(_ url: URL) -> String { String(data: try! Data(contentsOf: url), encoding: .utf8)! }
        func request() -> Request { Request(url: URL(string: "https://fixture/app.ipa")!) }
        func send(_ req: Request, _ text: String) { req.body.send(.buffer(Buffer(readableBytesView: Data(text.utf8)))) }
        func failed<T>(_ future: EventLoopFuture<T>) { guard case .failure = future.result else { fatalError("Expected failure") } }
        func clean() {
            assert(try! fm.contentsOfDirectory(atPath: inbox.path).allSatisfy { !$0.hasPrefix(UploadWorkspace.prefix) })
        }
        try write("old", destination)
        let blocked = root.appendingPathComponent("blocked")
        try write("keep", blocked)
        failed(server.put(request(), url: blocked.appendingPathComponent("app.ipa")))
        assert(read(blocked) == "keep" && server.scheduled == 0)
        let savedCopyRoot = copyRoot
        copyRoot = blocked
        let copyFailure = request()
        let copyResult = server.streamToFile(copyFailure, destination: destination, route: true, successStatus: .ok)
        send(copyFailure, "new"); copyFailure.body.send(.end)
        failed(copyResult)
        assert(read(destination) == "old" && server.reports == 0 && WebManagerRouter.inputs.isEmpty)
        copyRoot = savedCopyRoot
        clean()
        for mode in ["disconnect", "write", "sync", "close"] {
            let req = request()
            let result = server.put(req, url: destination)
            if mode == "write" { FileHandle.failWrite = true }
            send(req, "partial")
            assert(read(destination) == "old")
            FileHandle.failWrite = false
            if mode == "disconnect" { failed(req.body.send(.error(Failure.injected))) }
            if mode == "sync" { FileHandle.failSync = true }
            if mode == "close" { FileHandle.failClose = true }
            req.body.send(.end)
            FileHandle.failSync = false
            req.body.send(.end) // late end cannot route or complete again
            failed(result)
            assert(read(destination) == "old" && server.scheduled == 0 && server.reports == 0)
            clean()
        }
        // Finder/Windows' initial empty PUT is valid; only committed requests schedule routing.
        let empty = request()
        let emptyResult = server.put(empty, url: destination)
        empty.body.send(.end)
        assert(try! emptyResult.result!.get().status == .created)
        assert(read(destination).isEmpty && server.scheduled == 1)
        let full = request()
        _ = server.put(full, url: destination)
        send(full, "full"); full.body.send(.end)
        assert(read(destination) == "full" && server.scheduled == 2)
        clean()
        // Concurrent browser requests never import or delete the other request's bytes.
        let a = request(), b = request()
        _ = server.streamToFile(a, destination: destination, route: true, successStatus: .ok)
        _ = server.streamToFile(b, destination: destination, route: true, successStatus: .ok)
        send(a, "A"); send(b, "B"); a.body.send(.end); b.body.send(.end)
        assert(read(destination) == "B" && server.reports == 2)
        assert(WebManagerRouter.inputs.map(read) == ["A", "B"])
        let firstDirectory = WebManagerRouter.inputs[0].deletingLastPathComponent()
        let secondDirectory = WebManagerRouter.inputs[1].deletingLastPathComponent()
        WebManagerRouter.cleanups[0]()
        assert(!fm.fileExists(atPath: firstDirectory.path))
        assert(fm.fileExists(atPath: secondDirectory.path))
        assert(read(destination) == "B" && read(WebManagerRouter.inputs[1]) == "B")
        clean()
        // A commit failure preserves a pre-existing directory and never reports/routes.
        let folder = inbox.appendingPathComponent("folder")
        try fm.createDirectory(at: folder, withIntermediateDirectories: true)
        let kept = folder.appendingPathComponent("kept")
        try write("keep", kept)
        let bad = request()
        let badResult = server.streamToFile(bad, destination: folder, route: true, successStatus: .ok)
        send(bad, "wrong"); bad.body.send(.end)
        failed(badResult)
        assert(read(kept) == "keep" && server.reports == 2)
        clean()
        // MOVE/COPY share atomic replacement and respect Overwrite: F.
        for move in [false, true] {
            let source = inbox.appendingPathComponent("source.ipa")
            try write("source", source)
            var req = Request(url: URL(string: "https://fixture/source.ipa")!)
            req.headers.values = ["Destination": "/app.ipa", "Overwrite": "F"]
            assert(server._moveOrCopy(req, move: move).status == .preconditionFailed)
            assert(read(destination) == "B" && read(source) == "source")
            req.headers.values["Destination"] = "/folder"
            req.headers.values["Overwrite"] = "T"
            assert(server._moveOrCopy(req, move: move).status == .conflict)
            assert(read(kept) == "keep" && read(source) == "source")
            req.headers.values["Destination"] = "/source.ipa"
            assert(server._moveOrCopy(req, move: move).status == .forbidden)
            req.headers.values["Destination"] = "/app.ipa"
            assert(server._moveOrCopy(req, move: move).status == .noContent)
            assert(read(destination) == "source")
            assert(fm.fileExists(atPath: source.path) == !move)
            try write("B", destination)
            clean()
        }
        assert(server.resolve("/" + UploadWorkspace.prefix + "private/app.ipa") == nil)
        print("PASS: disconnect/write/sync/close/commit failure preservation, late events, zero/full PUT, independent imports, MOVE/COPY overwrite and cleanup")
    }
}
'''
with tempfile.TemporaryDirectory(prefix='korsign-web-upload-check-') as directory:
    source = Path(directory) / 'Check.swift'
    source.write_text(program)
    binary = Path(directory) / 'check'
    subprocess.run(['swiftc', '-parse-as-library', str(source), '-o', str(binary)], check=True)
    subprocess.run([str(binary), directory], check=True, timeout=30)
