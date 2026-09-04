import Foundation

@main
struct OTAInstallChecks {
    static func main() {
        var state = OTAInstallState()
        assert(!state.timedOut(at: 1_000)) // Background preparation has no prompt deadline.
        state.advance(to: .waiting, now: 0)
        assert(!state.timedOut(at: 2)) // Returning focus cannot cancel a slow installer.
        state.advance(to: .waiting, now: 100) // Repeated manifest/HEAD cannot extend waiting.
        assert(state.deadline == 120)
        assert(state.timedOut(at: 120))
        state.advance(to: .downloading, now: 121)
        assert(!state.timedOut(at: 122))
        state.advance(to: .verifying, now: 125)
        state.advance(to: .downloading, now: 130) // Repeated GET cannot regress verification.
        assert(state.phase == .verifying && state.deadline == 725)
        assert(state.timedOut(at: 725))
        state.advance(to: .finished, now: 150)
        state.advance(to: .verifying, now: 151) // Late callback after cancellation/failure.
        assert(state.phase == .finished && !state.timedOut(at: 100_000))

        var tracking = OTAInstallState()
        let active = InstallProgressReading(fraction: 0.7, isFinished: false, isCancelled: false)
        let finished = InstallProgressReading(fraction: 1, isFinished: true, isCancelled: false)
        tracking.advance(to: .waiting, now: 0)
        assert(!tracking.progressEnded(active, now: 1)) // Ignore an earlier attempt before GET.
        tracking.advance(to: .downloading, now: 2)
        assert(!tracking.progressEnded(nil, now: 3)) // Missing from the outset is not completion.
        assert(!tracking.progressEnded(active, now: 4))
        tracking.advance(to: .verifying, now: 5)
        assert(!tracking.progressEnded(nil, now: 6))
        assert(!tracking.progressEnded(active, now: 6.5)) // Transient gap resets.
        assert(!tracking.progressEnded(nil, now: 7))
        assert(!tracking.progressEnded(nil, now: 7.5))
        assert(tracking.progressEnded(nil, now: 8)) // Real feed ends despite hidden app record.
        assert(tracking.progressEnded(finished, now: 9))
        tracking.advance(to: .finished, now: 10)
        assert(!tracking.progressEnded(finished, now: 11))
        var noActivity = OTAInstallState()
        noActivity.advance(to: .verifying, now: 0)
        assert(!noActivity.progressEnded(finished, now: 1)) // Stale completed progress.
        assert(!noActivity.progressEnded(nil, now: 2))
        assert(!noActivity.progressEnded(nil, now: 500))
        assert(!noActivity.progressEnded(InstallProgressReading(fraction: 0.8, isFinished: false, isCancelled: true), now: 501))

        var install = OTAInstallState()
        install.advance(to: .verifying, now: 0)
        var terminal = InstallProgressReading(fraction: 0.88, isFinished: false, isCancelled: false,
            isCurrent: false, installPhase: 1, expectedFinalPhase: 1, installState: 5, installStateName: "Finished")
        assert(!install.confirmsInstall(terminal)) // No observed activity for this request.
        assert(!install.progressEnded(active, now: 1))
        assert(install.confirmsInstall(terminal)) // Final install state need not coincide with 100%.
        terminal.installStateName = "Failed"
        assert(!install.confirmsInstall(terminal))
        terminal.installStateName = "Cancelled"
        assert(!install.confirmsInstall(terminal))
        terminal.installStateName = "Finished"
        terminal.installPhase = 0
        assert(!install.confirmsInstall(terminal)) // Download completion is not installation.
        terminal.installPhase = 3
        terminal.expectedFinalPhase = 3
        assert(!install.confirmsInstall(terminal)) // Neither is installing a placeholder.
        terminal.installPhase = 1
        terminal.expectedFinalPhase = nil
        assert(!install.confirmsInstall(terminal))
        terminal.installPhase = 2
        terminal.expectedFinalPhase = 2
        assert(install.confirmsInstall(terminal)) // Explicit final restore-data phase.
        install.advance(to: .finished, now: 2)
        assert(!install.confirmsInstall(terminal)) // Late callback cannot confirm a cancelled request.

        func record(installed: Bool = true, placeholder: Bool = false, version: String = "1", build: String = "10", path: String = "old", date: TimeInterval = 1) -> InstalledAppRecord {
            InstalledAppRecord(isInstalled: installed, isPlaceholder: placeholder, version: version,
                build: build, bundleURL: URL(fileURLWithPath: "/apps/\(path)/app.app"), registeredDate: Date(timeIntervalSince1970: date))
        }
        let old = record()
        func verified(_ current: InstalledAppRecord, previous: InstalledAppRecord? = old) -> Bool {
            current.confirmsReplacement(of: previous, version: "1", build: "10")
        }
        assert(!verified(old)) // Failed same-version update must not delete the signed copy.
        assert(!verified(record(path: "new"), previous: nil)) // Missing evidence fails closed.
        assert(!verified(record(installed: false, path: "new")))
        assert(!verified(record(placeholder: true, path: "new")))
        assert(!verified(record(version: "2", path: "new")))
        assert(!verified(record(build: "11", path: "new")))
        assert(verified(record(path: "new")))
        assert(verified(record(date: 2))) // Same-version reinstall with a new registration.
        assert(verified(record(), previous: record(installed: false))) // Fresh install.
        assert(!old.confirmsReplacement(of: record(installed: false), version: "1", build: nil))
        print("OTA installation state checks passed")
    }
}
