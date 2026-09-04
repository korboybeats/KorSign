"""Mac-only real local dispatcher check; no install, network or daemon subscription.
The workspace singleton is replaced only inside this disposable test process.
A fresh local observer receives benign proxy fixtures. This does not prove iOS
callback delivery or that declining its installation prompt emits an event.
"""
from pathlib import Path
import tempfile,subprocess
root=Path(__file__).resolve().parents[1]
s=r'''
import Foundation
import ObjectiveC
@objc(KorSignDispatchProxyFixture) final class Proxy: NSObject {
    @objc var isLaunchProhibited: Bool { false }
    @objc var bundleIdentifier: String { "fixture.target" }
}
@objc(KorSignDispatchWorkspaceFixture) final class Workspace: NSObject {
    @objc class func defaultWorkspace() -> NSObject { instance }
    let remote = (NSClassFromString("LSApplicationWorkspaceRemoteObserver") as! NSObject.Type).init()
    @objc var remoteObserver: NSObject { remote }
    @objc func addObserver(_ observer: NSObject) { callVoid("addLocalObserver:", observer) }
    @objc func removeObserver(_ observer: NSObject) { callVoid("removeLocalObserver:", observer) }
    func callVoid(_ name: String, _ observer: NSObject) {
        let sel=NSSelectorFromString(name)
        let call=unsafeBitCast(remote.method(for:sel),to:(@convention(c)(AnyObject,Selector,AnyObject)->Void).self)
        call(remote,sel,observer)
    }
}
let instance = Workspace()
@main struct Check {
 static func main() {
    let selector=NSSelectorFromString("defaultWorkspace")
    let actual=class_getClassMethod(NSClassFromString("LSApplicationWorkspace"),selector)!
    let replacement=class_getClassMethod(Workspace.self,selector)!
    let original=method_setImplementation(actual,method_getImplementation(replacement))
    defer { method_setImplementation(actual,original) }
    var messages: [String] = []
    let diagnostic=InstallWorkspaceDiagnostic(identifier:"fixture.target") { messages.append($0) }!
    defer { diagnostic.stop() }
    let remote=instance.remote
    let selector2=NSSelectorFromString("messageObserversWithSelector:andApps:")
    guard remote.responds(to:selector2) else { print("Dispatcher unavailable on Mac");return }
    let call=unsafeBitCast(remote.method(for:selector2),to:(@convention(c)(AnyObject,Selector,Selector,NSArray)->Bool).self)
    print("Dispatch cancel returned",call(remote,selector2,NSSelectorFromString("applicationInstallsDidCancel:"),[Proxy()] as NSArray))
    print("Dispatch installed returned",call(remote,selector2,NSSelectorFromString("applicationsDidInstall:"),[Proxy()] as NSArray))
    assert(messages.contains { $0.contains("event=cancel") && $0.contains("matching=1") })
    assert(messages.contains { $0.contains("event=installed") && $0.contains("matching=1") })
    diagnostic.stop()
    let before=messages.count
    _ = call(remote,selector2,NSSelectorFromString("applicationInstallsDidCancel:"),[Proxy()] as NSArray)
    assert(messages.count == before)
    print("PASS: real Mac local dispatch reaches production callbacks; removal stops delivery")
 }
}
'''
with tempfile.TemporaryDirectory(prefix='korsign-local-dispatch-') as d:
 p=Path(d);(p/'check.swift').write_text(s)
 subprocess.run(['swiftc',str(root/'KorSign/Backend/Observable/OTAInstallState.swift'),str(root/'KorSign/Backend/Observable/InstalledAppProbe.swift'),str(p/'check.swift'),'-o',str(p/'check')],check=True)
 subprocess.run([str(p/'check')],check=True,timeout=10)
