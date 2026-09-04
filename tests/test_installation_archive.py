"""Offline archive ownership check; production handlers with fake zip/HTTP services."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
owner = (root / 'KorSign/Utilities/Handlers/InstallationArchive.swift').read_text()
handler = (root / 'KorSign/Utilities/Handlers/ArchiveHandler.swift').read_text()
server = (root / 'KorSign/Backend/Server/ServerInstaller.swift').read_text()
installer = (root / 'KorSign/Backend/Observable/AppInstaller.swift').read_text()
compute = (root / 'KorSign/Backend/Server/ServerInstaller+Compute.swift').read_text()
manifest = compute[compute.index('\tvar installManifest:'):]
resolver = (root / 'KorSign/Backend/Server/ManifestService.swift').read_text()
# Stub only the external HTTP probe; metadata/URL generation remains production code.
resolver = resolver[:resolver.index('\tprivate static func _serves')] + '\tprivate static func _serves(_ url: URL) async -> Bool { false }\n}'
pipeline = installer[installer.index('\tprivate func _run()'):installer.index('\tprivate func _serveForOTA(')]
# Substitute only the test executable's missing application bundle identity.
pipeline = pipeline.replace('Bundle.main.bundleIdentifier!', '"fixture.host"')
for module in ['UIKit.UIApplication', 'Zip', 'IDeviceSwift', 'Vapor', 'NIOSSL', 'NIOTLS']:
    handler = handler.replace(f'import {module}\n', '')
    server = server.replace(f'import {module}\n', '')

stubs = r'''
import Foundation
import SwiftUI
import OSLog
extension Logger { static let misc = Logger(subsystem: "ArchiveCheck", category: "test") }
var sourceDirectory: URL!
var exportsDirectory: URL!
protocol AppInfoPresentable { var name: String? { get }; var version: String? { get }; var identifier: String? { get } }
struct TestApp: AppInfoPresentable {
    var name: String? { MainActor.preconditionIsolated(); return "Example" }
    var version: String? { MainActor.preconditionIsolated(); return "1" }
    var identifier: String? { MainActor.preconditionIsolated(); return "fixture.app" }
}
struct NamedApp: AppInfoPresentable {
    let name: String?
    let version: String?
    let identifier: String? = "fixture.app"
}
extension String { static func localized(_ value: String) -> String { value } }
final class Storage {
    static let shared = Storage()
    func getAppDirectory(for app: AppInfoPresentable) -> URL? { MainActor.preconditionIsolated(); return sourceDirectory }
}
enum SigningFileHandlerError: Error { case appNotFound }
enum ZipCompression: CaseIterable { case normal }
enum AppArchiver {
    static var shouldFail = false
    static var lastDestination: URL?
    static func zip(payload: URL, to url: URL, compression: ZipCompression, progress: (Double) -> Void) throws {
        lastDestination = url
        try Data("fixture".utf8).write(to: url)
        if shouldFail { throw SigningFileHandlerError.appNotFound }
    }
}
extension FileManager {
    var archives: URL { exportsDirectory }
    func createDirectoryIfNeeded(at url: URL) throws {
        try createDirectory(at: url, withIntermediateDirectories: true)
    }
}
extension URL { func toSharedDocumentsURL() -> URL? { self } }
enum UIApplication { static func open(_ url: URL) {} }
final class BackgroundTaskManager {
    init(taskName: String, expirationTitle: String, expirationBody: String) {}
    func start() {}
    func stop() {}
}
enum FileLogger {
    static func log(_ message: String, category: String) {}
    static func error(_ message: String, category: String) {}
}
final class InstallerStatusViewModel: ObservableObject {
    enum InstallerStatus {
        case none, ready, sendingManifest, sendingPayload, installing
        case completed(Result<Void, Error>), broken(Error)
    }
    @Published var status = InstallerStatus.none
    var packageProgress = 0.0
}
struct HTTPStatus: Equatable {
    let code: Int
    static let ok = Self(code: 200), partialContent = Self(code: 206)
    static let notFound = Self(code: 404), badGateway = Self(code: 502)
}
struct Abort: Error { init(_ status: HTTPStatus, reason: String = "") {} }
enum HTTPMethod: String { case GET, HEAD }
enum HeaderName: String { case contentLength, range, contentType }
struct HTTPHeaders: ExpressibleByDictionaryLiteral {
    enum Compression { case disable }
    var responseCompression: Compression?
    var values: [String: String] = [:]
    init(dictionaryLiteral elements: (String, String)...) { values = Dictionary(uniqueKeysWithValues: elements) }
    func first(name: HeaderName) -> String? { values[name.rawValue] }
    mutating func add(name: HeaderName, value: String) { values[name.rawValue] = value }
}
final class Response {
    struct Body { let data: Data; init(data: Data) { self.data = data }; init(string: String) { data = Data(string.utf8) } }
    let body: Body
    let status: HTTPStatus
    var headers: HTTPHeaders
    var completion: ((Result<Void, Error>) -> Void)?
    init(status: HTTPStatus, version: Int = 1, headers: HTTPHeaders = [:], body: Body = .init(data: Data())) {
        self.status = status; self.headers = headers; self.body = body
    }
}
struct FileIO {
    enum MediaType { case binary }
    func streamFile(at path: String, mediaType: MediaType, onCompleted: @escaping (Result<Void, Error>) -> Void = { _ in }) -> Response {
        assert(FileManager.default.fileExists(atPath: path))
        let response = Response(status: .ok)
        // Like Vapor, the response retains its completion until consumed or discarded.
        response.completion = onCompleted
        return response
    }
}
struct Request {
    let method: HTTPMethod
    let url: URL
    let fileio = FileIO()
    let version = 1
    var headers: HTTPHeaders = [:]
}
final class HTTPServer {
    let stopping = DispatchSemaphore(value: 0)
    let releaseShutdown = DispatchSemaphore(value: 0)
    let stopped = DispatchSemaphore(value: 0)
    func start() throws {}
    func shutdown() { stopping.signal(); releaseShutdown.wait() }
}
final class Application {
    let server = HTTPServer()
    var route: ((Request) -> Response)?
    func get(_ path: String, use: @escaping (Request) -> Response) { route = use }
    func shutdown() { server.stopped.signal() }
}
extension ServerInstaller {
    var testApplication: Application { _server! }
    func setupApp(port: Int) throws -> Application { Application() }
    func sni() -> String { "localhost" }
    static func resolve(_ host: String) -> [String] { [] }
    var payloadEndpoint: URL { URL(string: "https://localhost/payload")! }
    var plistEndpoint: URL { URL(string: "https://localhost/manifest")! }
    var displayImageSmallEndpoint: URL { URL(string: "https://localhost/small")! }
    var displayImageLargeEndpoint: URL { URL(string: "https://localhost/large")! }
    var displayImageSmallData: Data { Data() }
    var displayImageLargeData: Data { Data() }
    var html: String { "" }
}
'''

stubs += '\nextension ServerInstaller {\n' + manifest + resolver + '\n'

pipeline_stubs = r'''
@MainActor final class InstallationProxy {
    static var shouldFail = false
    static var reads = 0
    init(viewModel: InstallerStatusViewModel) {}
    func install(at url: URL, suspend: Bool) async throws {
        try await Task.sleep(nanoseconds: 50_000_000)
        assert(try! Data(contentsOf: url) == Data("fixture".utf8))
        Self.reads += 1
        if Self.shouldFail { throw SigningFileHandlerError.appNotFound }
    }
}
@MainActor final class PipelineCheck {
    enum Outcome { case exported(URL?) }
    let app: AppInfoPresentable = TestApp()
    let viewModel = InstallerStatusViewModel()
    var _hasFinished = false
    var _isSharing = false
    let _useShareSheet = true
    let _installationMethod = 1
    var _progressTask: Task<Void, Never>?
    var result: Result<Outcome, Error>?
    func _finish(_ result: Result<Outcome, Error>) { self.result = result }
    func _serveForOTA(_ package: InstallationArchive) async { fatalError("Pairing fixture only") }
    func run() async { await _run() }
''' + pipeline + '\n}\n'

checks = r'''
@main struct Check {
    @MainActor static func waitRemoved(_ url: URL) async throws {
        for _ in 0..<200 {
            if !FileManager.default.fileExists(atPath: url.path) { return }
            try await Task.sleep(nanoseconds: 10_000_000)
        }
        fatalError("Owner did not remove \(url)")
    }
    static func wait(_ semaphore: DispatchSemaphore) { semaphore.wait() }
    @MainActor static func prepare(_ model: InstallerStatusViewModel) async throws -> InstallationArchive {
        let handler = ArchiveHandler(app: TestApp(), viewModel: model)
        try await handler.move()
        return try await handler.archive()
    }
    @MainActor static func main() async throws {
        let fm = FileManager.default
        let root = URL(fileURLWithPath: CommandLine.arguments[1])
        sourceDirectory = root.appendingPathComponent("Example.app")
        exportsDirectory = root.appendingPathComponent("exports")
        try fm.createDirectory(at: sourceDirectory, withIntermediateDirectories: true)
        try fm.createDirectory(at: exportsDirectory, withIntermediateDirectories: true)
        let original = sourceDirectory.appendingPathComponent("original")
        try Data("original".utf8).write(to: original)

        // The returned owner survives the producer, including an async consumer's delay.
        var archive: InstallationArchive? = try await prepare(InstallerStatusViewModel())
        let folder = archive!.directory
        try await Task.sleep(nanoseconds: 20_000_000)
        assert(try! Data(contentsOf: archive!.url) == Data("fixture".utf8))
        archive = nil
        try await waitRemoved(folder)

        // Production pipeline keeps the owner through delayed pairing reads, even on error.
        for fail in [false, true] {
            InstallationProxy.shouldFail = fail
            let pipeline = PipelineCheck()
            await pipeline.run()
            if fail { guard case .failure = pipeline.result else { fatalError("Lost install failure") } }
            try await waitRemoved(AppArchiver.lastDestination!.deletingLastPathComponent())
        }
        assert(InstallationProxy.reads == 2)
        let cancelled = PipelineCheck()
        cancelled._hasFinished = true
        await cancelled.run()
        assert(InstallationProxy.reads == 2, "Stopped packaging started installation")
        try await waitRemoved(AppArchiver.lastDestination!.deletingLastPathComponent())

        // Partial packaging failure releases only that handler's disposable folder.
        AppArchiver.shouldFail = true
        do { _ = try await prepare(InstallerStatusViewModel()); fatalError("Expected zip failure") }
        catch SigningFileHandlerError.appNotFound {}
        try await waitRemoved(AppArchiver.lastDestination!.deletingLastPathComponent())
        AppArchiver.shouldFail = false

        // Shutdown itself retains the archive, including when there are no HTTP readers.
        // Real manifest generation from an HTTP worker must never read the app object.
        let manifestURL = await ManifestService.resolve(for: TestApp(), payload: URL(string: "https://example.test/payload")!)!
        let fields = URLComponents(url: manifestURL, resolvingAgainstBaseURL: false)!.queryItems!
        assert(fields.first { $0.name == "bundleid" }?.value == "fixture.app")
        let idle = try ServerInstaller(app: TestApp(), viewModel: InstallerStatusViewModel())
        let route = idle.testApplication.route!
        let request = Request(method: .GET, url: idle.plistEndpoint)
        let manifestData = await Task.detached { route(request).body.data }.value
        let plist = try PropertyListSerialization.propertyList(from: manifestData, format: nil) as! [String: Any]
        let metadata = (plist["items"] as! [[String: Any]])[0]["metadata"] as! [String: String]
        assert(metadata["bundle-identifier"] == "fixture.app" && metadata["title"] == "Example")
        let idleApplication = idle.testApplication
        idle.package = try await prepare(InstallerStatusViewModel())
        let idleFolder = idle.package!.directory
        idle.stop()
        await Task.detached { wait(idleApplication.server.stopping) }.value
        try await Task.sleep(nanoseconds: 20_000_000)
        assert(fm.fileExists(atPath: idleFolder.path), "Shutdown lost its owner")
        idleApplication.server.releaseShutdown.signal()
        try await waitRemoved(idleFolder)

        // HEAD, successful GET and failed GET all retain ownership through shutdown.
        for (method, fail) in [(HTTPMethod.HEAD, false), (.GET, false), (.GET, true)] {
            let model = InstallerStatusViewModel()
            let server = try ServerInstaller(app: TestApp(), viewModel: model)
            let application = server.testApplication
            server.package = try await prepare(model)
            let folder = server.package!.directory
            var response: Response? = application.route!(Request(method: method, url: server.payloadEndpoint))
            await Task.yield()
            if method == .HEAD {
                guard case .none = model.status else { fatalError("HEAD changed state") }
            }
            server.stop()
            server.stop() // repeated teardown must not release an outstanding reader
            await Task.detached { wait(application.server.stopping) }.value
            assert(fm.fileExists(atPath: folder.path))
            application.server.releaseShutdown.signal()
            await Task.detached { wait(application.server.stopped) }.value
            try await Task.sleep(nanoseconds: 20_000_000)
            assert(fm.fileExists(atPath: folder.path), "Pending response lost its owner")
            if method == .GET { response!.completion?(fail ? .failure(SigningFileHandlerError.appNotFound) : .success(())) }
            response = nil // HEAD body is discarded without invoking its completion.
            try await waitRemoved(folder)
        }

        // Export moves the file outside the owner's cleanup boundary.
        var handler: ArchiveHandler? = ArchiveHandler(app: TestApp(), viewModel: InstallerStatusViewModel())
        try await handler!.move()
        var exportedArchive: InstallationArchive? = try await handler!.archive()
        let exportFolder = exportedArchive!.directory
        let exported = try await handler!.moveToArchive(exportedArchive!.url)!
        // Existing files, directories and links are never replaced during collision retry.
        let duplicate = root.appendingPathComponent("duplicate.ipa")
        try Data("second".utf8).write(to: duplicate)
        let base = exported.deletingPathExtension().lastPathComponent
        assert(base == "Example 1")
        let occupiedDirectory = exportsDirectory.appendingPathComponent(base + " (2).ipa")
        try fm.createDirectory(at: occupiedDirectory, withIntermediateDirectories: true)
        let occupiedLink = exportsDirectory.appendingPathComponent(base + " (3).ipa")
        try fm.createSymbolicLink(at: occupiedLink, withDestinationURL: original)
        let second = try await handler!.moveToArchive(duplicate)!
        assert(second.lastPathComponent == base + " (4).ipa")
        assert(try! Data(contentsOf: second) == Data("second".utf8))
        assert(try! Data(contentsOf: exported) == Data("fixture".utf8))
        assert(fm.fileExists(atPath: occupiedDirectory.path))
        assert(try! fm.destinationOfSymbolicLink(atPath: occupiedLink.path) == original.path)

        // A real non-collision failure propagates and leaves the prepared source intact.
        let normalExports = exportsDirectory!
        let blocked = root.appendingPathComponent("blocked-exports")
        try Data("keep".utf8).write(to: blocked)
        exportsDirectory = blocked
        try Data("prepared".utf8).write(to: duplicate)
        do { _ = try await handler!.moveToArchive(duplicate); fatalError("Expected failure") } catch {}
        assert(try! Data(contentsOf: duplicate) == Data("prepared".utf8))
        assert(try! Data(contentsOf: blocked) == Data("keep".utf8))
        exportsDirectory = normalExports

        for (name, version) in [(nil, nil), ("", ""), ("../My/App\\Name\n\"", "1/2"),
                                (String(repeating: "한😀", count: 200), "version"),
                                ("a" + String(repeating: "\u{301}", count: 200), nil)] as [(String?, String?)] {
            let named = ArchiveHandler(app: NamedApp(name: name, version: version), viewModel: InstallerStatusViewModel())
            let input = root.appendingPathComponent(UUID().uuidString + ".ipa")
            try Data("named".utf8).write(to: input)
            let output = try await named.moveToArchive(input)!
            assert(output.deletingLastPathComponent().standardizedFileURL == normalExports.standardizedFileURL)
            assert(output.lastPathComponent.utf8.count < 255 && output.pathExtension == "ipa", "filename=\(output.lastPathComponent), bytes=\(output.lastPathComponent.utf8.count), ext=\(output.pathExtension)")
            assert(!output.lastPathComponent.contains("\n") && !output.lastPathComponent.contains("\""))
            assert(try! Data(contentsOf: output) == Data("named".utf8))
        }
        assert(ArchiveHandler.exportStem(name: "Example", version: "1") == "Example 1")
        assert(ArchiveHandler.exportStem(name: nil, version: nil) == "App")
        print("PASS: missing/unsafe/long Unicode metadata, same-time collisions and occupied paths, failed-move source preservation")
        do {
            _ = try await handler!.moveToArchive(root.appendingPathComponent("missing"))
            fatalError("Export failure was swallowed")
        } catch {}
        exportedArchive = nil
        handler = nil
        try await waitRemoved(exportFolder)
        assert(try! Data(contentsOf: exported) == Data("fixture".utf8))
        assert(try! Data(contentsOf: original) == Data("original".utf8))
        print("PASS: main-queue metadata capture, worker manifest generation, producer handoff, partial failure, HEAD/GET reader lifetime, delayed shutdown and export retention")
    }
}
'''

with tempfile.TemporaryDirectory(prefix='korsign-archive-ownership-') as directory:
    source = Path(directory) / 'Check.swift'
    source.write_text(stubs + owner + handler + server + pipeline_stubs + checks)
    binary = Path(directory) / 'check'
    subprocess.run(['swiftc', '-parse-as-library', '-O', '-assert-config', 'Debug', str(source), '-o', str(binary)], check=True)
    subprocess.run([str(binary), directory], check=True, timeout=30)
