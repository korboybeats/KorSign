"""Exercise production IPA cleanup on success, failure, and repeated cleanup."""
from pathlib import Path
import subprocess
import tempfile
root = Path(__file__).resolve().parents[1]
source = (root / 'KorSign/Utilities/Handlers/AppFileHandler.swift').read_text()
method = source[source.index('\tfunc clean() async throws {'):source.index('\n}\n\n/// Copyable error')]
program = r'''
import Foundation
let sandbox = URL(fileURLWithPath: CommandLine.arguments[1])
extension FileManager {
 func unsigned(_ id: String) -> URL { sandbox.appendingPathComponent(id) }
 func removeFileIfNeeded(at url: URL) throws { if fileExists(atPath: url.path) { try removeItem(at: url) } }
}
final class Handler {
 let _fileManager = FileManager.default
 let _uuid = UUID().uuidString
 let _uniqueWorkDir = sandbox.appendingPathComponent(UUID().uuidString)
 var _didAddToDatabase = false
''' + method + r'''
}
@main struct Check {
 static func main() async throws {
  let fm = FileManager.default
  let original = sandbox.appendingPathComponent("original.ipa")
  try Data("original".utf8).write(to: original)
  for saved in [false, true] {
   let handler = Handler()
   handler._didAddToDatabase = saved
   try fm.createDirectory(at: handler._uniqueWorkDir, withIntermediateDirectories: true)
   try Data("partial".utf8).write(to: handler._uniqueWorkDir.appendingPathComponent("partial"))
   let published = fm.unsigned(handler._uuid)
   try fm.createDirectory(at: published, withIntermediateDirectories: true)
   try await handler.clean()
   try await handler.clean()
   precondition(!fm.fileExists(atPath: handler._uniqueWorkDir.path))
   precondition(fm.fileExists(atPath: published.path) == saved)
   precondition(try! Data(contentsOf: original) == Data("original".utf8))
  }
  print("PASS: partial extraction and unregistered payload removed; registered payload/original preserved; cleanup idempotent")
 }
}
'''
with tempfile.TemporaryDirectory(prefix='korsign-cleanup-') as directory:
    work = Path(directory)
    (work/'check.swift').write_text(program)
    subprocess.run(['swiftc','-parse-as-library',str(work/'check.swift'),'-o',str(work/'check')],check=True)
    subprocess.run([str(work/'check'),str(work)],check=True)
