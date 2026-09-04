"""Exercise production picker callbacks with UIKit presentation stubs."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
source = (root / 'KorSign/Views/Common/DocumentPicker.swift').read_text()
source = '\n'.join(line for line in source.splitlines() if not line.startswith('import '))
stubs = r'''
import Foundation
struct UTType {}
enum ImportFolder { case apps; var bookmarkKey: String { "unused-fixture" } }
@MainActor protocol UIDocumentPickerDelegate: AnyObject {
    func documentPicker(_ controller: UIDocumentPickerViewController, didPickDocumentsAt urls: [URL])
    func documentPickerWasCancelled(_ controller: UIDocumentPickerViewController)
}
@MainActor protocol UIAdaptivePresentationControllerDelegate: AnyObject {
    func presentationControllerDidDismiss(_ controller: UIPresentationController)
}
@MainActor final class UIPresentationController {
    weak var delegate: UIAdaptivePresentationControllerDelegate?
}
@MainActor class UIViewController {
    var isBeingDismissed = false
    var isBeingPresented = false
    var presented: UIDocumentPickerViewController?
    func present(_ picker: UIDocumentPickerViewController, animated: Bool) { presented = picker }
}
@MainActor final class UIDocumentPickerViewController: UIViewController {
    weak var delegate: UIDocumentPickerDelegate?
    var presentationController: UIPresentationController? = UIPresentationController()
    var allowsMultipleSelection = false
    var directoryURL: URL?
    init(forOpeningContentTypes: [UTType], asCopy: Bool) { assert(asCopy) }
}
@MainActor enum UIApplication {
    static var presenter: UIViewController? = UIViewController()
    static func topViewController() -> UIViewController? { presenter }
}
@MainActor enum Presentation {
    static var pending: [() -> Void] = []
    static func afterDismiss(_ action: @escaping () -> Void) { pending.append(action) }
    static func drain() { let work = pending; pending = []; work.forEach { $0() } }
}
'''
checks = r'''
@main struct Check {
    @MainActor static func main() {
        var picked: [[URL]] = []
        let root = UIApplication.presenter!
        DocumentPicker.open([UTType()], multiple: true) { picked.append($0) }
        assert(root.presented == nil)
        Presentation.drain()
        let picker = root.presented!
        assert(picker.allowsMultipleSelection)
        let delegate = picker.delegate!
        let url = URL(fileURLWithPath: "/fixture.ipa")
        delegate.documentPicker(picker, didPickDocumentsAt: [url])
        delegate.documentPickerWasCancelled(picker)
        assert(picked.isEmpty)
        Presentation.drain()
        assert(picked == [[url]])

        root.presented = nil
        DocumentPicker.open([UTType()]) { picked.append($0) }
        Presentation.drain()
        let cancelled = root.presented!
        cancelled.presentationController!.delegate!.presentationControllerDidDismiss(cancelled.presentationController!)
        Presentation.drain()
        assert(cancelled.delegate == nil && picked.count == 1)

        root.presented = nil
        DocumentPicker.open([UTType()]) { picked.append($0) }
        Presentation.drain()
        let reopened = root.presented!
        reopened.delegate!.documentPickerWasCancelled(reopened)
        Presentation.drain()
        assert(reopened.delegate == nil && picked.count == 1)

        UIApplication.presenter = reopened
        DocumentPicker.open([UTType()]) { picked.append($0) }
        Presentation.drain()
        assert(reopened.presented == nil)
        print("PASS: deferred presentation, selection once, cancel/swipe retirement, reopen and nested-picker guard")
    }
}
'''
with tempfile.TemporaryDirectory(prefix='korsign-picker-check-') as directory:
    script = Path(directory) / 'Check.swift'
    script.write_text(stubs + '\n' + source + '\n' + checks)
    binary = Path(directory) / 'check'
    subprocess.run(['swiftc', '-parse-as-library', str(script), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
