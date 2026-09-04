"""Exercise production backup manifest validation and restore with temporary files.

Storage, preferences and tweak services are isolated stubs; no app data is used.
"""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
source = (root / 'KorSign/Backend/Observable/BackupManager.swift').read_text()
models = source[source.index('struct BackupComponents:'):source.index('@MainActor\nfinal class BackupManager')]
start = source.index('\tfunc restore(')
restore = source[start:source.index('\n\tprivate func _findRoot', start)]
program = r'''
import Foundation
extension String {
    static func localized(_ value: String, arguments: CVarArg...) -> String { value }
}
''' + models + r'''
var library = URL(fileURLWithPath: "/unused")
final class CertificatePair { var uuid: String?; init(_ id: String) { uuid = id } }
final class Storage {
    static let shared = Storage()
    var certificates: [CertificatePair] = []
    var writes = 0
    func requireReady() throws {}
    func getAllCertificates() -> [CertificatePair] { certificates }
    func addCertificate(uuid: String, password: String?, nickname: String?, ppq: Bool,
                        expiration: Date, completion: (Error?) -> Void) {
        writes += 1; certificates.append(CertificatePair(uuid)); completion(nil)
    }
    func sourceExists(_ id: String) -> Bool { false }
    func addSource(_ url: URL, name: String?, identifier: String, iconURL: URL?, completion: (Error?) -> Void) {
        writes += 1; completion(nil)
    }
}
final class UserDefaults {
    static let standard = UserDefaults()
    var writes = 0
    func set(_ value: Any, forKey: String) { writes += 1 }
}
final class TweakManager {
    static let shared = TweakManager()
    var writes = 0
    func mergeFromBackup(tweaksDir: URL) throws -> Int { writes += 1; return 1 }
}
extension FileManager {
    func certificates(_ uuid: String) -> URL { library.appendingPathComponent("Certificates").appendingPathComponent(uuid) }
    func removeFileIfNeeded(at url: URL) throws {
        if fileExists(atPath: url.path) { try removeItem(at: url) }
    }
}
final class BackupManager {
    let _fm = FileManager.default
    static func isBackupableSettingKey(_ key: String) -> Bool { true }
''' + restore + r'''
}
@main struct Check {
    static func main() throws {
        let fm = FileManager.default
        let root = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
        library = root.appendingPathComponent("library")
        try fm.createDirectory(at: library.appendingPathComponent("Certificates"), withIntermediateDirectories: true)
        let sentinel = library.appendingPathComponent("sentinel")
        try Data("untouched".utf8).write(to: sentinel)
        let valid = "A1234567-1234-1234-1234-123456789ABC"
        func manifest(_ ids: [String]) -> BackupManifest {
            BackupManifest(version: 2, createdAt: Date(), appVersion: "3.0.1",
                contents: [.certificates, .sources, .settings, .tweaks],
                certificates: ids.map { .init(uuid: $0, expiration: Date(), ppq: false) },
                sources: [.init(identifier: "test", url: URL(string: "https://example.invalid")!)])
        }
        func archive(_ ids: [String]) throws -> BackupArchive {
            let work = root.appendingPathComponent(UUID().uuidString)
            try fm.createDirectory(at: work.appendingPathComponent("certs/" + valid), withIntermediateDirectories: true)
            try Data("new".utf8).write(to: work.appendingPathComponent("certs/" + valid + "/certificate.p12"))
            return BackupArchive(manifest: manifest(ids), root: work, work: work)
        }
        // Invalid ID last: even a preceding valid certificate must not be restored.
        for invalid in ["", ".", "..", "../sentinel", "/tmp", "a/b", "a\\b", valid + "/..", valid + "\0", "not-a-uuid"] {
            let input = try archive([valid, invalid])
            var rejected = false
            do { _ = try BackupManager().restore(input, components: [.certificates, .sources, .settings, .tweaks]) }
            catch { rejected = true }
            assert(rejected)
            assert(Storage.shared.writes == 0 && UserDefaults.standard.writes == 0 && TweakManager.shared.writes == 0)
            assert(!fm.fileExists(atPath: fm.certificates(valid).path))
            assert(try! Data(contentsOf: sentinel) == Data("untouched".utf8))
        }
        for duplicate in [valid, valid.lowercased()] {
            let input = try archive([valid, duplicate])
            var rejected = false
            do { _ = try BackupManager().restore(input, components: [.certificates]) } catch { rejected = true }
            assert(rejected && Storage.shared.writes == 0)
        }
        // Legacy manifest inference and lower-case UUID spelling remain accepted.
        var legacy = manifest([valid.lowercased()])
        legacy.version = 1; legacy.contents = nil
        let decoded = try JSONDecoder().decode(BackupManifest.self, from: JSONEncoder().encode(legacy))
        try decoded.validateCertificateIdentifiers()
        assert(decoded.storedContents.contains(.certificates))
        assert(decoded.certificates[0].uuid == valid.lowercased())
        try manifest([]).validateCertificateIdentifiers()

        let input = try archive([valid])
        _ = try BackupManager().restore(input, components: [.certificates])
        assert(Storage.shared.writes == 1)
        let restored = fm.certificates(valid).appendingPathComponent("certificate.p12")
        assert(try! Data(contentsOf: restored) == Data("new".utf8))
        try Data("existing".utf8).write(to: restored)
        _ = try BackupManager().restore(input, components: [.certificates])
        assert(Storage.shared.writes == 1)
        assert(try! Data(contentsOf: restored) == Data("existing".utf8))
        let lowerCase = try archive([valid.lowercased()])
        _ = try BackupManager().restore(lowerCase, components: [.certificates])
        assert(Storage.shared.writes == 1)
        assert(try! Data(contentsOf: restored) == Data("existing".utf8))
        print("PASS: invalid/duplicate IDs reject before writes; valid restore, legacy IDs and existing certificates preserved")
    }
}
'''
with tempfile.TemporaryDirectory(prefix='korsign-backup-check-') as directory:
    swift = Path(directory) / 'Check.swift'
    binary = Path(directory) / 'check'
    swift.write_text(program)
    subprocess.run(['swiftc', '-parse-as-library', str(swift), '-o', str(binary)], check=True)
    subprocess.run([str(binary), directory], check=True)
