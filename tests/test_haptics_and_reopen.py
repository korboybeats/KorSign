"""Exercise production haptic policy and reopen transitions without an attached phone."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
navigation = (root / 'KorSign/Views/Common/NavigationHaptics.swift').read_text()
assert 'Gesture' not in navigation and '.onAppear' in navigation
assert 'guard !didAppear' in navigation
haptics = (root / 'KorSign/Utilities/AppHaptics.swift').read_text()
haptics = '\n'.join(line for line in haptics.splitlines() if not line.startswith('import '))
observer = (root / 'KorSign/Views/Sources/Apps/DownloadButtonView.swift').read_text()
observer = 'class TabSelectionObserver' + observer.split('class TabSelectionObserver', 1)[1].split('\nstruct DownloadButtonView:', 1)[0]
stubs = r'''
import Foundation
protocol ObservableObject {}
@propertyWrapper struct Published<Value> { var wrappedValue: Value }
enum ScenePhase { case active, inactive, background }
enum TabEnum { case library, sources, settings }
final class TabBarPreferences { static let shared = TabBarPreferences(); var resolvedLaunchTab = TabEnum.settings }
struct Animation { static func easeOut(duration: Double) -> Animation { Animation() } }
func withAnimation(_ animation: Animation, _ action: () -> Void) { action() }
enum UINotificationFeedbackGenerator { enum FeedbackType { case success, warning, error } }
final class UIApplication { static let shared = UIApplication(); var applicationState = ScenePhase.active }
enum NBHaptic {
    static var events: [String] = []
    static func tap() { events.append("tap") }
    static func selection() { events.append("navigation") }
    static func notify(_ type: UINotificationFeedbackGenerator.FeedbackType) { events.append("result") }
}
func drain() { RunLoop.current.run(until: Date().addingTimeInterval(0.12)) }
'''
checks = r'''
let defaults = UserDefaults.standard
let keys = [AppHaptics.enabledKey, "KorSign.haptics.navigation", "KorSign.haptics.actions", "KorSign.haptics.results", "KorSign.libraryPlusHaptics", "KorSign.libraryEditHaptics", "KorSign.tabBarHaptics", "KorSign.openFilePickerOnLaunch", "KorSign.openFilePickerOnReopen"]
let previous = keys.map { defaults.object(forKey: $0) }
defer { for (key, value) in zip(keys, previous) { if let value { defaults.set(value, forKey: key) } else { defaults.removeObject(forKey: key) } } }
keys.forEach { defaults.removeObject(forKey: $0) }
assert(AppHaptics.isEnabled(.actions))
defaults.set(false, forKey: "KorSign.libraryPlusHaptics")
defaults.set(true, forKey: "KorSign.libraryEditHaptics")
defaults.set(false, forKey: "KorSign.tabBarHaptics")
AppHaptics.migratePreferences()
assert(!AppHaptics.isEnabled(.actions) && !AppHaptics.isEnabled(.navigation))
defaults.set(true, forKey: "KorSign.haptics.actions")
AppHaptics.migratePreferences()
assert(AppHaptics.isEnabled(.actions)) // Migration cannot overwrite a new choice.
AppHaptics.action()
assert(NBHaptic.events == ["tap"]) // UI feedback must not wait for the next run loop.
AppHaptics.notice(); drain()
assert(NBHaptic.events == ["tap"]) // One immediate action/result pulse.
defaults.set(false, forKey: AppHaptics.enabledKey)
AppHaptics.action(); AppHaptics.result(.error); drain()
assert(NBHaptic.events.count == 1)
defaults.set(true, forKey: AppHaptics.enabledKey)
AppHaptics.navigation(); drain()
assert(NBHaptic.events.count == 1) // Category choice survived master off/on.
defaults.set(false, forKey: "KorSign.haptics.results")
AppHaptics.result(.error); drain()
assert(NBHaptic.events.count == 1)
UIApplication.shared.applicationState = .background
AppHaptics.action(); drain()
assert(NBHaptic.events.count == 1)
UIApplication.shared.applicationState = .active
AppHaptics.action(); drain()
assert(NBHaptic.events.count == 2)

defaults.set(true, forKey: "KorSign.haptics.navigation")
AppHaptics.navigation()
assert(NBHaptic.events.last == "navigation" && NBHaptic.events.count == 3)
drain()
let queued = DispatchSemaphore(value: 0)
DispatchQueue.global().async {
    AppHaptics.action()
    queued.signal()
}
assert(queued.wait(timeout: .now() + 2) == .success)
assert(NBHaptic.events.count == 3) // A background caller cannot emit on its thread.
drain()
assert(NBHaptic.events.count == 4)

drain()
AppHaptics.tabTouch()
assert(NBHaptic.events.last == "tap" && NBHaptic.events.count == 5)
drain()
defaults.set(false, forKey: "KorSign.haptics.navigation")
AppHaptics.tabTouch()
assert(NBHaptic.events.count == 5) // Tab impact still belongs to Navigation.

let selection = TabSelectionObserver()
assert(!selection.hasPendingLaunchImport)
defaults.set(true, forKey: "KorSign.openFilePickerOnReopen")
selection.handleScenePhase(.active)
selection.handleScenePhase(.inactive)
selection.handleScenePhase(.active)
assert(!selection.hasPendingLaunchImport) // Fresh activation and Control Center stay quiet.
selection.handleScenePhase(.background)
selection.handleScenePhase(.inactive)
selection.handleScenePhase(.active)
assert(selection.hasPendingLaunchImport && selection.selectedTab == .library)
selection.hasPendingLaunchImport = false
selection.handleScenePhase(.active)
assert(!selection.hasPendingLaunchImport) // One request per background return.
selection.handleScenePhase(.background)
selection.handleScenePhase(.active, installationActive: true)
assert(!selection.hasPendingLaunchImport) // Active install must not trigger reopening picker.
selection.handleScenePhase(.active)
assert(!selection.hasPendingLaunchImport) // Suppressed request is not delayed.
selection.isImportPickerPresented = true
selection.handleScenePhase(.background)
selection.handleScenePhase(.active)
assert(!selection.hasPendingLaunchImport) // Returning from Files cannot stack a picker.
selection.isImportPickerPresented = false
defaults.set(false, forKey: "KorSign.openFilePickerOnReopen")
selection.handleScenePhase(.background)
selection.handleScenePhase(.active)
assert(!selection.hasPendingLaunchImport)
print("PASS: haptic defaults/migration, master/category gates, coalescing, foreground gate, reopen-only transitions and existing-picker guard")
'''
with tempfile.TemporaryDirectory(prefix='korsign-haptics-test-') as directory:
    script = Path(directory) / 'Check.swift'
    script.write_text(stubs + '\n' + haptics + '\n' + observer + '\n' + checks)
    subprocess.run(['swift', str(script)], check=True)
