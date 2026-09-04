"""Production tweak staging lifetime, with isolated files and fake injection jobs."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
source = (root / 'KorSign/Utilities/Handlers/TweakHandler.swift').read_text()
a = source.index('\tpublic func getInputFiles()')
b = source.index('\n\t/// Stages one tweak file', a)
method = source[a:b]
program = r'''
import Foundation
struct Options {
    var experiment_replaceSubstrateWithEllekit = false
    var injectIntoExtensions = true
    let injectPath = 0
    let injectFolder = 0
}
struct Spec {
    struct File { let enabled = true; let fileName = "managed" }
    let files = [File()]
}
enum Targeting { case all, mainOnly }
enum Logger { static let misc = Log() }
struct Log { func info(_ value: String) {} }
struct SigningLog {
    static let shared = SigningLog()
    func info(_ value: String, category: String = "") {}
    func error(_ value: String, category: String = "") {}
}
extension String {
    static func localized(_ value: String, arguments: String = "") -> String { value }
}
// Redirect only temporary-directory allocation; all actual file operations remain real.
final class Files {
    let root: URL
    var directory: URL?
    init(_ root: URL) { self.root = root }
    func uniqueTemporaryDirectory(_ label: String) -> URL {
        let url = root.appendingPathComponent(label + UUID().uuidString)
        directory = url
        return url
    }
    func createDirectoryIfNeeded(at url: URL) throws {
        try FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
    }
    func copyItem(at source: URL, to dest: URL) throws {
        try FileManager.default.copyItem(at: source, to: dest)
    }
    func removeItem(at url: URL) throws { try FileManager.default.removeItem(at: url) }
}
@MainActor final class Handler {
    let _fileManager: Files
    var _options = Options()
    var _urls: [URL] = []
    var _enabledSpecs: [Spec] = []
    var _hasAnyInjection: Bool { !_enabledSpecs.isEmpty || !_urls.isEmpty }
    var _filePickerFixURL: URL?
    var failJob = false
    var waitForCancellation = false
    var sawConsumer = false
    let output: URL
    init(_ root: URL, source: URL) {
        _fileManager = Files(root)
        _filePickerFixURL = source
        output = root.appendingPathComponent(UUID().uuidString + ".dylib")
    }
    func _checkEllekit() async throws {}
    func _runJob(urls: [URL], baseTmpDir: URL, path: Int, folder: Int) async throws -> [String] {
        assert(FileManager.default.fileExists(atPath: baseTmpDir.path))
        try Data("leftover extraction".utf8).write(to: baseTmpDir.appendingPathComponent("data.tar"))
        // Yield while this consumer still owns the staged file.
        try await Task.sleep(nanoseconds: waitForCancellation ? 10_000_000_000 : 1_000_000)
        assert(FileManager.default.fileExists(atPath: urls.last!.path))
        if failJob { throw CocoaError(.fileReadCorruptFile) }
        try FileManager.default.copyItem(at: urls.last!, to: output)
        return [output.lastPathComponent]
    }
    func _injectIntoTargets(dylibNames: [String], targeting: Targeting, path: Int, folder: Int) {
        assert(FileManager.default.fileExists(atPath: _fileManager.directory!.path))
        assert(FileManager.default.fileExists(atPath: output.path))
        sawConsumer = true
    }
    func _processSpecFile(_ file: Spec.File, spec: Spec, baseTmpDir: URL) async throws {
        try Data("partial managed work".utf8).write(to: baseTmpDir.appendingPathComponent("managed"))
        throw CocoaError(.fileReadCorruptFile) // Production catches per-spec failures.
    }
''' + method + r'''
}
@main struct Check {
    @MainActor static func main() async throws {
        let root = URL(fileURLWithPath: CommandLine.arguments[1])
        let source = root.appendingPathComponent("original.dylib")
        let bytes = Data("original".utf8)
        try bytes.write(to: source)
        let unrelated = root.appendingPathComponent("unrelated")
        try bytes.write(to: unrelated)
        for mode in 0..<4 {
            let handler = Handler(root, source: source)
            handler.failJob = mode == 1
            if mode == 2 { handler._enabledSpecs = [Spec()] }
            if mode == 3 { handler._filePickerFixURL = root.appendingPathComponent("missing") }
            var failed = false
            do { try await handler.getInputFiles() } catch { failed = true }
            assert(failed == (mode == 1 || mode == 3))
            assert(!FileManager.default.fileExists(atPath: handler._fileManager.directory!.path))
            if mode == 0 || mode == 2 {
                assert(handler.sawConsumer)
                assert(try! Data(contentsOf: handler.output) == bytes)
            }
            assert(try! Data(contentsOf: source) == bytes)
            assert(try! Data(contentsOf: unrelated) == bytes)
        }
        let cancelled = Handler(root, source: source)
        cancelled.waitForCancellation = true
        let task = Task { try await cancelled.getInputFiles() }
        try await Task.sleep(nanoseconds: 100_000_000)
        task.cancel()
        do { try await task.value; fatalError("Expected cancellation") } catch is CancellationError {}
        assert(!FileManager.default.fileExists(atPath: cancelled._fileManager.directory!.path))
        assert(try! Data(contentsOf: source) == bytes)
        print("PASS: staging retained during consumption; removed after success, copy/job/spec failure and cancellation; originals/output preserved")
    }
}
'''
with tempfile.TemporaryDirectory(prefix='korsign-tweak-staging-') as directory:
    work = Path(directory)
    swift = work / 'Check.swift'
    swift.write_text(program)
    binary = work / 'check'
    subprocess.run(['xcrun', 'swiftc', '-swift-version', '5', '-parse-as-library', str(swift), '-o', str(binary)], check=True)
    subprocess.run([str(binary), directory], check=True, timeout=20)
