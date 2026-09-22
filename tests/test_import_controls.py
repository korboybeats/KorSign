"""Exercise production import pause/resume/cancel synchronization."""
from pathlib import Path
import subprocess, tempfile
root = Path(__file__).resolve().parents[1]
source = (root / 'KorSign/Backend/Observable/Download.swift').read_text()
control = source[source.index('final class ImportControl:'):source.index('class Download:')]
checks = r'''
import Foundation
''' + control + r'''
let control = ImportControl()
assert(control.setPaused(true))
let completed = DispatchSemaphore(value: 0)
DispatchQueue.global().async {
    do { try control.checkpoint(); assertionFailure("Cancelled checkpoint returned") }
    catch { assert(error is CancellationError) }
    completed.signal()
}
assert(completed.wait(timeout: .now() + 0.1) == .timedOut)
control.cancel()
assert(completed.wait(timeout: .now() + 2) == .success)
assert(control.isCancelled)
let resumed = ImportControl()
resumed.setPaused(true)
let ready = DispatchSemaphore(value: 0)
DispatchQueue.global().async { try! resumed.checkpoint(); ready.signal() }
assert(ready.wait(timeout: .now() + 0.1) == .timedOut)
resumed.setPaused(false)
assert(ready.wait(timeout: .now() + 2) == .success)
try resumed.beginCommit()
assert(!resumed.setPaused(true))
resumed.cancel()
assert(!resumed.isCancelled)
print("PASS: pause blocks, resume continues, stop wakes paused worker, commit boundary prevents late cancellation")
'''
with tempfile.TemporaryDirectory() as directory:
    path = Path(directory) / 'Check.swift'
    path.write_text(checks)
    subprocess.run(['swift', str(path)], check=True)
