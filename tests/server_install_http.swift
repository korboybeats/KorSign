import Foundation
import SwiftUI
import Vapor

// Only platform services are stubbed; requests run through the production
// ServerInstaller routes and Vapor's real HTTP encoder/file streaming.
protocol AppInfoPresentable { var identifier: String? { get }; var name: String? { get }; var version: String? { get } }
struct TestApp: AppInfoPresentable { let identifier: String? = "fixture.app"; let name: String? = "Fixture"; let version: String? = "1" }
final class InstallerStatusViewModel: ObservableObject {
    enum InstallerStatus {
        case none, ready, sendingManifest, sendingPayload, installing
        case completed(Result<Void, Error>), broken(Error)
    }
    @Published var status = InstallerStatus.none
}
final class BackgroundTaskManager {
    init(taskName: String, expirationTitle: String, expirationBody: String) {}
    func start() {}
    func stop() {}
}
enum FileLogger {
    static func log(_ message: String, category: String) { print(message) }
    static func error(_ message: String, category: String) { print(message) }
}
extension ServerInstaller {
    func setupApp(port: Int) throws -> Application {
        let app = Application(.testing)
        app.http.server.configuration.hostname = "127.0.0.1"
        app.http.server.configuration.port = port
        return app
    }
    func sni() -> String { "127.0.0.1" }
    static func resolve(_ host: String) -> [String] { [host] }
    var payloadEndpoint: URL { URL(string: "http://127.0.0.1:\(port)/\(id).ipa")! }
    var plistEndpoint: URL { URL(string: "http://127.0.0.1:\(port)/\(id).plist")! }
    var displayImageSmallEndpoint: URL { URL(string: "http://127.0.0.1:\(port)/small.png")! }
    var displayImageLargeEndpoint: URL { URL(string: "http://127.0.0.1:\(port)/large.png")! }
    var installManifestData: Data { Data("manifest".utf8) }
    var displayImageSmallData: Data { Data() }
    var displayImageLargeData: Data { Data() }
    var html: String { "" }
}

@main struct HTTPChecks {
    @MainActor static func main() async throws {
        setbuf(stdout, nil)
        let archive = InstallationArchive()
        defer { withExtendedLifetime(archive) {} }
        let directory = archive.directory
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: directory) }
        let payload = archive.url
        let bytes = Data(repeating: 42, count: 128 * 1024)
        try bytes.write(to: payload)
        let model = InstallerStatusViewModel()
        let server = try ServerInstaller(app: TestApp(), viewModel: model)
        server.package = archive
        defer { server.stop() }

        func request(_ url: URL, method: String = "GET", range: String? = nil, encoding: String = "deflate") async throws -> (Data, HTTPURLResponse) {
            var request = URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData)
            request.setValue(encoding, forHTTPHeaderField: "Accept-Encoding")
            request.httpMethod = method
            request.setValue(range, forHTTPHeaderField: "Range")
            let (data, response) = try await URLSession.shared.data(for: request)
            // Drain status changes dispatched by the real route.
            await withCheckedContinuation { continuation in
                DispatchQueue.main.async { continuation.resume() }
            }
            return (data, response as! HTTPURLResponse)
        }
        _ = try await request(server.plistEndpoint)
        guard case .sendingManifest = model.status else { fatalError("Manifest state missing") }
        for encoding in ["deflate", "gzip", "identity"] {
            let (body, response) = try await request(server.payloadEndpoint, method: "HEAD", encoding: encoding)
            assert(response.statusCode == 200 && body.isEmpty)
            assert(response.value(forHTTPHeaderField: "Content-Encoding") == nil)
            assert(response.value(forHTTPHeaderField: "Content-Length") == String(bytes.count), "HEAD headers: \(response.allHeaderFields)")
            guard case .sendingManifest = model.status else { fatalError("HEAD changed installation state") }
        }
        let (body, response) = try await request(server.payloadEndpoint)
        assert(response.statusCode == 200 && body == bytes)
        assert(response.value(forHTTPHeaderField: "Content-Encoding") == nil)
        guard case .installing = model.status else { fatalError("GET completion did not enter verification") }
        _ = try await request(server.plistEndpoint)
        guard case .installing = model.status else { fatalError("Manifest retry regressed installation") }
        let (range, partial) = try await request(server.payloadEndpoint, range: "bytes=0-31")
        assert(partial.statusCode == 206 && range == bytes.prefix(32))
        try FileManager.default.removeItem(at: payload)
        let (_, failure) = try await request(server.payloadEndpoint)
        assert(failure.statusCode == 500)
        guard case .broken = model.status else { fatalError("File failure not reported") }
        print("Server HEAD/GET/range/error integration checks passed")
    }
}
