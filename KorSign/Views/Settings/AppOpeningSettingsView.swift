import SwiftUI
import NimbleViews

struct AppOpeningSettingsView: View {
    @AppStorage("KorSign.openFilePickerOnLaunch") private var onLaunch = false
    @AppStorage("KorSign.openFilePickerOnReopen") private var onReopen = false

    var body: some View {
        NBList(.localized("App Opening")) {
            Section {
                Toggle(.localized("Open File Picker on Launch"), isOn: $onLaunch)
            } footer: {
                Text(.localized("Open Library and the IPA picker when starting the app."))
            }
            Section {
                Toggle(.localized("Open File Picker When Reopening"), isOn: $onReopen)
            } footer: {
                Text(.localized("Open Library and the IPA picker when returning from the background. A picker already on screen stays open."))
            }
        }
    }
}
