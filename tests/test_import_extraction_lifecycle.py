"""Production import extraction orchestration with a slow/failing fake extractor."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
source = (root / 'KorSign/Utilities/Handlers/AppFileHandler.swift').read_text()
method = source[source.index('\tfunc extract() async throws {'):source.index('\n\tfunc move() async throws {')]
# Accelerate the historical deadline so restoring it makes the slow-success check fail.
method = method.replace('.seconds(300)', '.milliseconds(20)')
program = r'''
import Foundation
import OSLog
extension Logger { static let misc = Logger(subsystem: "ImportLifecycleTest", category: "test") }
final class Download: @unchecked Sendable { var unpackageProgress = 0.0 }
struct ImportError: Error { enum Step { case extract }; let underlying: Error? }
enum FixtureError: Error { case extraction }
enum ArchiveExtraction {
 static func unzip(_ source: URL, to directory: URL, progress: ((Double) -> Void)?) throws {
  Thread.sleep(forTimeInterval: 0.1)
  if source.lastPathComponent == "failure" { throw FixtureError.extraction }
  progress?(1)
 }
}
final class Handler: @unchecked Sendable {
 let _ipa: URL
 let _uniqueWorkDir = URL(fileURLWithPath: "/unused-fixture")
 let _uuid = "fixture"
 let _download: Download? = nil
 var uniqueWorkDirPayload: URL?
 init(_ mode: String) { _ipa = URL(fileURLWithPath: "/" + mode) }
 func _error(_ step: ImportError.Step, reason: String, underlying: Error? = nil) -> ImportError {
  ImportError(underlying: underlying)
 }
''' + method + r'''
}
@main struct Check {
 static func main() async throws {
  let success = Handler("success")
  try await success.extract()
  precondition(success.uniqueWorkDirPayload?.lastPathComponent == "Payload")
  let failure = Handler("failure")
  do {
   try await failure.extract()
   fatalError("Extraction failure swallowed")
  } catch let error as ImportError {
   precondition(error.underlying is FixtureError)
   precondition(failure.uniqueWorkDirPayload == nil)
  }
  print("PASS: slow extraction succeeds; actual failure propagates; payload published only after completion")
 }
}
'''
with tempfile.TemporaryDirectory(prefix='korsign-import-lifecycle-') as directory:
    work = Path(directory)
    (work / 'check.swift').write_text(program)
    subprocess.run(['swiftc', '-parse-as-library', str(work / 'check.swift'), '-o', str(work / 'check')], check=True)
    subprocess.run([str(work / 'check')], check=True)
