import Foundation
import ObjectiveC

/// Read-only LaunchServices evidence. Missing selectors/data mean unverified, not success.
final class InstalledAppProbe {
    // One probe per installer, read serially. LaunchServices removes its lookup
    // before callers necessarily sample the final update on this live object.
    private var lastProgress: Progress?

    func resetProgress() { lastProgress = nil }
    func read(_ identifier: String) -> (record: InstalledAppRecord?, progress: InstallProgressReading?) {
        let progress = readProgress(identifier)
        let selector = NSSelectorFromString("applicationProxyForIdentifier:")
        guard let type = NSClassFromString("LSApplicationProxy") as? NSObject.Type,
              type.responds(to: selector),
              let proxy = type.perform(selector, with: identifier)?.takeUnretainedValue() as? NSObject
        else { return (nil, progress) }

        func object(_ name: String) -> AnyObject? {
            let selector = NSSelectorFromString(name)
            guard proxy.responds(to: selector) else { return nil }
            return proxy.perform(selector)?.takeUnretainedValue()
        }
        func boolean(_ name: String) -> Bool? {
            let selector = NSSelectorFromString(name)
            guard proxy.responds(to: selector), let implementation = proxy.method(for: selector) else { return nil }
            // BOOL is a scalar; perform(_:)'s object return convention cannot read it.
            let call = unsafeBitCast(implementation, to: (@convention(c) (AnyObject, Selector) -> Bool).self)
            return call(proxy, selector)
        }

        guard let installed = boolean("isInstalled"), let placeholder = boolean("isPlaceholder") else {
            return (nil, progress)
        }
        return (InstalledAppRecord(
            isInstalled: installed, isPlaceholder: placeholder,
            version: object("shortVersionString") as? String,
            build: object("bundleVersion") as? String,
            bundleURL: object("bundleURL") as? URL,
            registeredDate: object("registeredDate") as? Date
        ), progress)
    }

    /// The workspace API was the working progress source on the jailed phone.
    /// Proxy.installProgress can remain nil even while an installation is running.
    private func readProgress(_ identifier: String) -> InstallProgressReading? {
        let workspaceSelector = NSSelectorFromString("defaultWorkspace")
        let progressSelector = NSSelectorFromString("installProgressForBundleID:makeSynchronous:")
        guard let type = NSClassFromString("LSApplicationWorkspace") as? NSObject.Type,
              type.responds(to: workspaceSelector),
              let workspace = type.perform(workspaceSelector)?.takeUnretainedValue() as? NSObject,
              workspace.responds(to: progressSelector),
              let implementation = workspace.method(for: progressSelector) else { return nil }
        // The second argument is an unsigned char, not an Objective-C object.
        let call = unsafeBitCast(implementation, to: (@convention(c)
            (AnyObject, Selector, NSString, UInt8) -> Unmanaged<AnyObject>?).self)
        let current = call(workspace, progressSelector, identifier as NSString, 1)?.takeUnretainedValue() as? Progress
        if let current { lastProgress = current }
        guard let progress = current ?? lastProgress else { return nil }
        let info = progress.userInfo
        let phase = (info[ProgressUserInfoKey("installPhase")] as? NSNumber)?.uintValue
        let state = (info[ProgressUserInfoKey("installState")] as? NSNumber)?.uintValue
        let expectedPhaseSelector = NSSelectorFromString("ls_expectedFinalInstallPhase")
        var expectedPhase: UInt?
        if progress.responds(to: expectedPhaseSelector), let implementation = progress.method(for: expectedPhaseSelector) {
            let getter = unsafeBitCast(implementation, to: (@convention(c) (AnyObject, Selector) -> UInt).self)
            expectedPhase = getter(progress, expectedPhaseSelector)
        }
        var stateName: String?
        let nameSelector = NSSelectorFromString("NSStringFromLSInstallState:")
        if let state, let method = class_getClassMethod(NSString.self, nameSelector) {
            let stringify = unsafeBitCast(method_getImplementation(method), to: (@convention(c)
                (AnyObject, Selector, UInt) -> Unmanaged<AnyObject>?).self)
            stateName = stringify(NSString.self, nameSelector, state)?.takeUnretainedValue() as? String
        }
        return InstallProgressReading(fraction: progress.fractionCompleted,
            isFinished: progress.isFinished, isCancelled: progress.isCancelled,
            isCurrent: current != nil, installPhase: phase, expectedFinalPhase: expectedPhase,
            installState: state, installStateName: stateName)

    }

}

/// Temporary Dev-only diagnostic. A callback is evidence to review, not an install outcome.
/// Register/stop on the main actor; callbacks may arrive on a private workspace queue.
final class InstallWorkspaceDiagnostic: NSObject {
    private let identifier: String
    private let attempt = UUID().uuidString
    private let log: (String) -> Void
    private var workspace: NSObject?

    init?(identifier: String, log: @escaping (String) -> Void) {
        self.identifier = identifier
        self.log = log
        super.init()
        let selector = NSSelectorFromString("defaultWorkspace")
        guard let type = NSClassFromString("LSApplicationWorkspace") as? NSObject.Type,
              type.responds(to: selector),
              let workspace = type.perform(selector)?.takeUnretainedValue() as? NSObject,
              workspace.responds(to: NSSelectorFromString("addObserver:")),
              workspace.responds(to: NSSelectorFromString("removeObserver:")) else {
            log("observer unavailable attempt=\(attempt)")
            return nil
        }
        self.workspace = workspace
        logRegistration("before-add", workspace: workspace)
        changeRegistration("addObserver:", workspace: workspace)
        logRegistration("after-add", workspace: workspace)
        log("observer registration requested attempt=\(attempt); callback delivery unverified")
    }

    func stop() {
        guard let workspace else { return }
        self.workspace = nil
        logRegistration("before-remove", workspace: workspace)
        changeRegistration("removeObserver:", workspace: workspace)
        logRegistration("after-remove", workspace: workspace)
        log("observer removed attempt=\(attempt)")
    }

    private func changeRegistration(_ name: String, workspace: NSObject) {
        let selector = NSSelectorFromString(name)
        // Both methods return void; do not use perform's object-return convention.
        let call = unsafeBitCast(workspace.method(for: selector),
            to: (@convention(c) (AnyObject, Selector, AnyObject) -> Void).self)
        call(workspace, selector, self)
    }

    /// Aggregate registration evidence only; a count change does not prove remote delivery.
    private func logRegistration(_ stage: String, workspace: NSObject) {
        let selector = NSSelectorFromString("remoteObserver")
        guard workspace.responds(to: selector),
              let remote = workspace.perform(selector)?.takeUnretainedValue() as? NSObject else {
            log("observer registration stage=\(stage) attempt=\(attempt) remote=unavailable")
            return
        }
        var count = "unavailable"
        let countSelector = NSSelectorFromString("currentObserverCount")
        if remote.responds(to: countSelector), let implementation = remote.method(for: countSelector) {
            let getter = unsafeBitCast(implementation,
                to: (@convention(c) (AnyObject, Selector) -> UInt64).self)
            count = String(getter(remote, countSelector))
        }
        var observing = "unavailable"
        let observingSelector = NSSelectorFromString("isObservinglsd")
        if remote.responds(to: observingSelector), let implementation = remote.method(for: observingSelector) {
            let getter = unsafeBitCast(implementation,
                to: (@convention(c) (AnyObject, Selector) -> Bool).self)
            observing = String(getter(remote, observingSelector))
        }
        log("observer registration stage=\(stage) attempt=\(attempt) count=\(count) observingService=\(observing)")
    }

    private func record(_ event: String, applications: NSArray?) {
        var matching = 0
        var unknown = 0
        for value in applications ?? [] {
            var bundleID = value as? String
            if bundleID == nil, let proxy = value as? NSObject {
                let selector = NSSelectorFromString("bundleIdentifier")
                if proxy.responds(to: selector) {
                    bundleID = proxy.perform(selector)?.takeUnretainedValue() as? String
                }
            }
            if bundleID == identifier { matching += 1 }
            if bundleID == nil { unknown += 1 }
        }
        // Do not log other apps' identifiers, raw proxies, or metadata.
        log("observer event=\(event) attempt=\(attempt) count=\(applications?.count ?? 0) matching=\(matching) unknown=\(unknown)")
    }

    @objc func applicationInstallsDidCancel(_ applications: NSArray?) {
        record("cancel", applications: applications)
    }
    @objc func applicationInstallsDidStart(_ applications: NSArray?) {
        record("start", applications: applications)
    }
    @objc func applicationsWillInstall(_ applications: NSArray?) {
        record("willInstall", applications: applications)
    }
    @objc func applicationsDidInstall(_ applications: NSArray?) {
        record("installed", applications: applications)
    }
    @objc func applicationsDidFailToInstall(_ applications: NSArray?) {
        record("failed", applications: applications)
    }
}
