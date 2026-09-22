import SwiftUI
import NimbleViews

struct HapticsSettingsView: View {
    @AppStorage(AppHaptics.enabledKey) private var enabled = true
    @AppStorage(AppHaptics.Category.navigation.rawValue) private var navigation = true
    @AppStorage(AppHaptics.Category.actions.rawValue) private var actions = true
    @AppStorage(AppHaptics.Category.results.rawValue) private var results = true

    var body: some View {
        NBList(.localized("Haptics")) {
            Section {
                Toggle(.localized("Haptic Feedback"), isOn: $enabled)
            }
            Section {
                Toggle(.localized("Navigation"), isOn: $navigation)
                Toggle(.localized("Button Actions"), isOn: $actions)
                Toggle(.localized("Results & Alerts"), isOn: $results)
            } footer: {
                VStack(alignment: .leading, spacing: 6) {
                    Text(.localized("Navigation: Tabs and opening pages."))
                    Text(.localized("Button Actions: Buttons across the app."))
                    Text(.localized("Results & Alerts: Success, warnings, and errors."))
                }
            }
            .disabled(!enabled)
        }
    }
}
