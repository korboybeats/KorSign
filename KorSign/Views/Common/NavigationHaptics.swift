import SwiftUI

/// Attach to the destination, never the link: native rows must own hit testing.
private struct NavigationHaptics: ViewModifier {
    @State private var didAppear = false

    func body(content: Content) -> some View {
        content.onAppear {
            guard !didAppear else { return }
            didAppear = true
            AppHaptics.navigation()
        }
    }
}

extension View {
    func navigationHaptics() -> some View { modifier(NavigationHaptics()) }
}
