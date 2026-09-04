import Foundation
import ObjectiveC

// Exercise the real Objective-C lookup, including scalar BOOL return values.
@objc(KorSignProbeFixture)
final class ProbeFixture: NSObject {
    @objc class func applicationProxyForIdentifier(_ identifier: String) -> NSObject? {
        switch identifier {
        case "missing": return nil
        case "unsupported": return NSObject()
        default: return probeFixture
        }
    }
    @objc var isInstalled: Bool { true }
    @objc var isPlaceholder: Bool { false }
    @objc var shortVersionString: String { "1.2" }
    @objc var bundleVersion: String { "34" }
    @objc var bundleURL: URL { URL(fileURLWithPath: "/apps/test.app") }
    @objc var registeredDate: Date { Date(timeIntervalSince1970: 123) }
    @objc var installProgress: Progress? { nil } // Reproduce the jailed-phone proxy.

}

private let probeFixture = ProbeFixture()

@objc(KorSignWorkspaceFixture)
final class WorkspaceFixture: NSObject {
    var observer: NSObject?
    var exposesRemote = true
    @objc var remoteObserver: NSObject? { exposesRemote ? self : nil }
    @objc var currentObserverCount: UInt64 { observer == nil ? 0 : 1 }
    @objc var isObservinglsd: Bool { observer != nil }
    var adds = 0
    var removes = 0
    @objc func addObserver(_ value: NSObject) { observer = value; adds += 1 }
    @objc func removeObserver(_ value: NSObject) { assert(observer === value); observer = nil; removes += 1 }
    @objc class func defaultWorkspace() -> NSObject { workspaceFixture }
    @objc func installProgressForBundleID(_ identifier: String, makeSynchronous synchronous: UInt8) -> Progress? {
        assert(synchronous == 1)
        guard identifier != "no-progress" else { return nil }
        return publishedProgress
    }
}
private let workspaceFixture = WorkspaceFixture()
private var publishedProgress: Progress? = {
    let progress = Progress(totalUnitCount: 10)
    progress.completedUnitCount = 6
    return progress
}()

@main
struct ProbeChecks {
    static func main() {
        let selector = NSSelectorFromString("applicationProxyForIdentifier:")
        let method = class_getClassMethod(NSClassFromString("LSApplicationProxy"), selector)!
        let fixture = class_getClassMethod(ProbeFixture.self, selector)!
        let original = method_setImplementation(method, method_getImplementation(fixture))
        defer { method_setImplementation(method, original) }
        let workspaceSelector = NSSelectorFromString("defaultWorkspace")
        let workspaceMethod = class_getClassMethod(NSClassFromString("LSApplicationWorkspace"), workspaceSelector)!
        let workspaceImplementation = class_getClassMethod(WorkspaceFixture.self, workspaceSelector)!
        let originalWorkspace = method_setImplementation(workspaceMethod, method_getImplementation(workspaceImplementation))
        defer { method_setImplementation(workspaceMethod, originalWorkspace) }
        var messages: [String] = []
        let diagnostic = InstallWorkspaceDiagnostic(identifier: "fixture.app") { messages.append($0) }!
        assert(workspaceFixture.adds == 1 && workspaceFixture.observer === diagnostic)
        assert(messages.contains { $0.contains("stage=before-add") && $0.contains("count=0 observingService=false") })
        assert(messages.contains { $0.contains("stage=after-add") && $0.contains("count=1 observingService=true") })
        let cancel = NSSelectorFromString("applicationInstallsDidCancel:")
        assert(diagnostic.responds(to: cancel))
        diagnostic.applicationInstallsDidCancel(["fixture.app", "private.other", NSObject()])
        assert(messages.last!.contains("event=cancel") && messages.last!.contains("matching=1 unknown=1"))
        assert(!messages.joined().contains("private.other"))
        diagnostic.applicationsDidInstall(["fixture.app"])
        assert(messages.last!.contains("event=installed"))
        diagnostic.stop()
        diagnostic.stop()
        assert(workspaceFixture.removes == 1 && workspaceFixture.observer == nil)
        assert(messages.contains { $0.contains("stage=after-remove") && $0.contains("count=0 observingService=false") })
        workspaceFixture.exposesRemote = false
        let unsupported = InstallWorkspaceDiagnostic(identifier: "fixture.app") { messages.append($0) }!
        assert(messages.contains { $0.contains("remote=unavailable") })
        unsupported.stop()
        workspaceFixture.exposesRemote = true
        let evidence = InstalledAppProbe().read("fixture")
        assert(evidence.record?.isInstalled == true)
        assert(evidence.record?.isPlaceholder == false)
        assert(evidence.record?.version == "1.2" && evidence.record?.build == "34")
        assert(evidence.record?.bundleURL?.path == "/apps/test.app")
        assert(evidence.record?.registeredDate == Date(timeIntervalSince1970: 123))
        assert(evidence.progress?.fraction == 0.6)
        assert(evidence.progress?.isFinished == false && evidence.progress?.isCancelled == false)
        assert(InstalledAppProbe().read("missing").progress?.fraction == 0.6)
        assert(InstalledAppProbe().read("unsupported").progress?.fraction == 0.6)
        assert(InstalledAppProbe().read("no-progress").progress == nil)
        assert(InstalledAppProbe().read("missing").record == nil)
        assert(InstalledAppProbe().read("unsupported").record == nil)
        // Log-5 regression: lookup disappears at 88%, but the live object receives
        // its final install state. Use actual Foundation/LaunchServices accessors.
        let probe = InstalledAppProbe()
        let live = Progress(totalUnitCount: 100)
        live.completedUnitCount = 88
        live.setUserInfoObject(NSNumber(value: 1), forKey: ProgressUserInfoKey("installPhase"))
        live.setUserInfoObject(NSNumber(value: 1), forKey: ProgressUserInfoKey("installState"))
        publishedProgress = live
        var tracking = OTAInstallState()
        tracking.advance(to: .verifying, now: 0)
        let active = probe.read("missing").progress
        assert(active?.installStateName == "Active" && active?.installPhase == 1)
        assert(active?.expectedFinalPhase == 1)
        assert(!tracking.progressEnded(active, now: 1))
        publishedProgress = nil
        live.setUserInfoObject(NSNumber(value: 5), forKey: ProgressUserInfoKey("installState"))
        let terminal = probe.read("missing")
        assert(terminal.record == nil)
        assert(terminal.progress?.fraction == 0.88 && terminal.progress?.isFinished == false)
        assert(terminal.progress?.isCurrent == false && terminal.progress?.installStateName == "Finished")
        assert(tracking.confirmsInstall(terminal.progress))
        live.setUserInfoObject(NSNumber(value: 4), forKey: ProgressUserInfoKey("installState"))
        assert(!tracking.confirmsInstall(probe.read("missing").progress))
        probe.resetProgress()
        assert(probe.read("missing").progress == nil)
        print("Installed-app probe and retained terminal-state checks passed")
    }
}
