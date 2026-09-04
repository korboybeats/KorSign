import SwiftUI

extension View {
	/// Give Add Source room on iPad while preserving the phone's detents.
	func adaptiveSheetSizing(phone detents: Set<PresentationDetent> = []) -> some View {
		modifier(AdaptiveSheetSizing(detents: detents))
	}
}

private struct AdaptiveSheetSizing: ViewModifier {
	let detents: Set<PresentationDetent>

	@ViewBuilder
	func body(content: Content) -> some View {
		if UIDevice.current.userInterfaceIdiom == .pad {
			if #available(iOS 18, *) {
				content.presentationSizing(.page)
			} else {
				content.presentationDetents([.large])
			}
		} else if !detents.isEmpty {
			content.presentationDetents(detents)
		} else {
			content
		}
	}
}
