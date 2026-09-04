"""Compile the production signing adapter and commit gate with a harmless signer stub."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
handler = (root / 'KorSign/Utilities/Handlers/ZsignHandler.swift').read_text()
handler = handler.replace('import Zsign\n', '').replace('import UIKit\n', '')
workflow = (root / 'KorSign/Utilities/Handlers/SigningHandler.swift').read_text()
start = workflow.index('\t\tlet handler = ZsignHandler(')
end = workflow.index('\n\t}\n', start)
commit_gate = workflow[start:end]

program = r'''
import Foundation
struct Options {
    enum Mode { case `default`, onlyModify }
    var signingOption = Mode.default
    var disInjectionFiles: [String] = []
    var appEntitlementsFile: URL? = nil
    var removeProvisioning = false
}
final class OptionsManager { static let shared = OptionsManager(); var options = Options() }
final class CertificatePair { var password: String? = "test"; var nickname: String? = "test" }
enum SigningFileHandlerError: Error { case missingCertifcate, signFailed, disinjectFailed }
extension String {
    static func localized(_ value: String, arguments: String...) -> String { value }
}
extension Bundle { var exec: String? { nil } }
final class SigningLog { static let shared = SigningLog(); func info(_ value: String) {} }
final class StdoutCapture {
    static let shared = StdoutCapture()
    var active = false
    func start(_ receive: (String) -> Void) { assert(!active); active = true }
    func stop() { assert(active); active = false }
}
final class Storage {
    enum Kind { case provision, certificate }
    struct Profile { var Name = "test" }
    static let shared = Storage()
    func getFile(_ kind: Kind, from: CertificatePair) -> URL? { nil }
    func getProvisionFileDecoded(for: CertificatePair) -> Profile? { nil }
}
enum Zsign {
    static var result = false
    static var callback: Bool? = nil
    static var calls = 0
    static func removeDylibs(appExecutable: String, using: [String]) -> Bool { true }
    static func sign(appPath: String, provisionPath: String = "", p12Path: String = "",
                     p12Password: String = "", entitlementsPath: String, adhoc: Bool = false,
                     removeProvision: Bool, completion: (Bool) -> Void) -> Bool {
        calls += 1
        if let callback { completion(callback) }
        return result
    }
}
''' + handler + r'''
final class CommitGate {
    var _options = Options()
    var appCertificate: CertificatePair? = CertificatePair()
    let movedAppPath = URL(fileURLWithPath: "/unused-test-bundle")
    var moves = 0
    var registrations = 0
    func move() async throws { moves += 1 }
    func addToDatabase() async throws { registrations += 1 }
    func modify() async throws {
''' + commit_gate + r'''
    }
}
@main struct Check {
    static func main() async throws {
        // Native initialization failure omits the callback; later failure calls it.
        for callback in [nil, false, true] as [Bool?] {
            Zsign.callback = callback
            Zsign.result = callback == true
            let gate = CommitGate()
            var failed = false
            do { try await gate.modify() }
            catch SigningFileHandlerError.signFailed { failed = true }
            assert(failed == !Zsign.result)
            assert(gate.moves == (failed ? 0 : 1))
            assert(gate.registrations == (failed ? 0 : 1))
            assert(!StdoutCapture.shared.active)

            let adhoc = ZsignHandler(appUrl: gate.movedAppPath)
            failed = false
            do { try await adhoc.adhocSign() }
            catch SigningFileHandlerError.signFailed { failed = true }
            assert(failed == !Zsign.result)
            assert(!StdoutCapture.shared.active)
        }
        let missing = CommitGate()
        missing.appCertificate = nil
        let calls = Zsign.calls
        do { try await missing.modify(); assertionFailure("Missing certificate accepted") }
        catch SigningFileHandlerError.missingCertifcate {}
        assert(Zsign.calls == calls && missing.registrations == 0)

        // Modify-only remains intentionally independent of signing credentials.
        missing._options.signingOption = .onlyModify
        try await missing.modify()
        assert(Zsign.calls == calls && missing.registrations == 1)
        print("PASS: early/later signing failures block move and registration; success, ad-hoc, missing certificate, modify-only, and log cleanup")
    }
}
'''
with tempfile.TemporaryDirectory(prefix='korsign-signing-check-') as directory:
    source = Path(directory) / 'Check.swift'
    binary = Path(directory) / 'check'
    source.write_text(program)
    subprocess.run(['swiftc', '-parse-as-library', str(source), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
