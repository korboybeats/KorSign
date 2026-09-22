"""Production preparation task/gate under overlapping work, failure and cancellation."""
from pathlib import Path
import subprocess
import tempfile
root = Path(__file__).resolve().parents[1]
installer = (root / 'KorSign/Backend/Observable/AppInstaller.swift').read_text()
prepare = installer[installer.index('\tfunc prepare()'):installer.index('\tprivate func _run()')]
source = (root / 'KorSign/Backend/Observable/ArchivePreparationGate.swift').read_text()
source += (root / 'KorSign/Utilities/Handlers/InstallationArchive.swift').read_text()
source += r'''
enum FileLogger { static func log(_ text: String, category: String) {} }
@MainActor final class Fixture {
    static var active = 0
    static var peak = 0
    static var finished = 0
    let _installationMethod = 1
    let _isSharing = false
    var _hasFinished = false
    var _preparationTask: Task<(package: InstallationArchive, exported: URL?), Error>?
    let fails: Bool
    var calls = 0
    init(fails: Bool = false) { self.fails = fails }
    func _package() async throws -> (package: InstallationArchive, exported: URL?) {
        calls += 1
        Self.active += 1
        Self.peak = max(Self.peak, Self.active)
        defer { Self.active -= 1; Self.finished += 1 }
        let archive = InstallationArchive()
        try FileManager.default.createDirectory(at: archive.directory, withIntermediateDirectories: true)
        try Data("fixture".utf8).write(to: archive.url)
        // Detached work finishes before its preparation slot may be released.
        try await Task.detached { try await Task.sleep(nanoseconds: 40_000_000) }.value
        if fails { throw NSError(domain: "fixture", code: 1) }
        return (archive, nil)
    }
''' + prepare + r'''
}
@main struct Check {
    @MainActor static func main() async throws {
        let jobs = (0..<8).map { Fixture(fails: $0 == 0) }
        jobs.forEach { $0.prepare(); $0.prepare() }
        try await Task.sleep(nanoseconds: 10_000_000)
        assert(Fixture.active == 2)
        jobs[1]._preparationTask!.cancel() // already running
        jobs[5]._preparationTask!.cancel() // waiting for a slot
        var completed = 0
        var folders: [URL] = []
        for (index, job) in jobs.enumerated() {
            do {
                let result = try await job._preparationTask!.value
                assert(![0, 1, 5].contains(index))
                let bytes = try Data(contentsOf: result.package.url)
                assert(bytes == Data("fixture".utf8))
                folders.append(result.package.directory)
                completed += 1
            } catch { assert([0, 1, 5].contains(index)) }
            job._preparationTask = nil
            assert(job.calls <= 1, "Prepared the same archive twice")
        }
        assert(completed == 5 && Fixture.peak == 2 && Fixture.active == 0)
        assert(jobs[5].calls == 0, "Cancelled queued work still packaged")
        let next = Fixture(); next.prepare()
        _ = try await next._preparationTask!.value
        next._preparationTask = nil
        for _ in 0..<100 {
            if folders.allSatisfy({ !FileManager.default.fileExists(atPath: $0.path) }) { break }
            try await Task.sleep(nanoseconds: 10_000_000)
        }
        assert(folders.allSatisfy({ !FileManager.default.fileExists(atPath: $0.path) }))
        print("PASS: two-job limit, duplicate prevention, failure, queued/running cancellation, slot recovery and archive cleanup")
    }
}
'''
with tempfile.TemporaryDirectory(prefix='korsign-preparation-') as directory:
    path = Path(directory)
    (path / 'Check.swift').write_text(source)
    subprocess.run(['swiftc', '-parse-as-library', str(path / 'Check.swift'), '-o', str(path / 'check')], check=True)
    subprocess.run([str(path / 'check')], check=True, timeout=20)
