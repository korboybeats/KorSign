//
//  AppearanceTintColorView.swift
//  KorSign
//
//  Created by samara on 14.06.2025.
//

import SwiftUI
import NimbleViews

// MARK: - View
struct AppearanceTintColorView: View {
	@AppStorage("Feather.selectedTintTheme") private var _selectedTheme: String = AppTintTheme.defaultTheme.rawValue
	@AppStorage("Feather.userTintColor") private var _effectiveColorHex: String = Color.defaultUserTintHex
	private let _tintOptions: [AppTintTheme] = [.defaultTheme, .classic, .v2]

	// MARK: Body
	var body: some View {
		ScrollView(.horizontal, showsIndicators: false) {
			LazyHGrid(rows: [GridItem(.fixed(100))], spacing: 12) {
				ForEach(_tintOptions, id: \.rawValue) { option in
					let color = Color(hex: option.fixedHex ?? Color.defaultUserTintHex)
					let cornerRadius = NBRadius.large
					VStack(spacing: 8) {
						Circle()
							.fill(color)
							.frame(width: 30, height: 30)
							.overlay(
								Circle()
									.strokeBorder(Color.black.opacity(0.3), lineWidth: 2)
							)

						Text(option.name)
							.font(.subheadline)
							.foregroundColor(.secondary)
					}
					.frame(width: 120, height: 100)
					.background(Color(uiColor: .secondarySystemGroupedBackground))
					.clipShape(RoundedRectangle(cornerRadius: cornerRadius, style: .continuous))
					.overlay(
						RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
							.strokeBorder(_selectedTheme == option.rawValue ? color : .clear, lineWidth: 2)
					)
					.onTapGesture {
						_applyPreset(option)
					}
					.accessibilityLabel(Text(option.name))
				}
			}
		}
	}

	private func _applyPreset(_ theme: AppTintTheme) {
		let hex = theme.fixedHex ?? Color.defaultUserTintHex
		_selectedTheme = theme.rawValue
		_effectiveColorHex = hex
		UIApplication.topViewController()?.view.window?.tintColor = UIColor(Color(hex: hex))
	}
}
