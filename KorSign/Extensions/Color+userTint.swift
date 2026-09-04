//
//  Color+userTint.swift
//  KorSign
//
//  Created by Ryuk on 24.08.2026.
//

import SwiftUI
import AltSourceKit

enum AppTintTheme: String, CaseIterable {
	case defaultTheme = "default"
	case classic
	case v2
	case custom

	var name: String {
		switch self {
		case .defaultTheme: return "Default"
		case .classic: return "Classic"
		case .v2: return "V2"
		case .custom: return "Custom"
		}
	}

	var fixedHex: String? {
		switch self {
		case .defaultTheme: return Color.defaultUserTintHex
		case .classic: return "#848EF9"
		case .v2: return "#B496DC"
		case .custom: return nil
		}
	}

	func resolvedHex(customHex: String) -> String {
		fixedHex ?? customHex
	}

	static func inferred(from hex: String) -> AppTintTheme {
		let normalizedHex = hex
			.trimmingCharacters(in: .whitespacesAndNewlines)
			.replacingOccurrences(of: "#", with: "")
			.uppercased()
		if normalizedHex == "FFAC15" { return .defaultTheme }
		if normalizedHex == "848EF9" { return .classic }
		if normalizedHex == "B496DC" { return .v2 }
		return .custom
	}
}

extension Color {
	static let userTintColorKey = "Feather.userTintColor"
	static let selectedTintThemeKey = "Feather.selectedTintTheme"
	static let customUserTintKey = "Feather.customTintColor"
	static let defaultUserTintHex = "#FFAC15"

	static var userTint: Color {
		Color(hex: resolvedUserTintHex())
	}

	static func resolvedUserTintHex(defaults: UserDefaults = .standard) -> String {
		let selectedTheme = AppTintTheme(
			rawValue: defaults.string(forKey: selectedTintThemeKey) ?? ""
		) ?? .defaultTheme
		let customHex = defaults.string(forKey: customUserTintKey) ?? defaultUserTintHex
		return selectedTheme.resolvedHex(customHex: customHex)
	}

	static func synchronizeUserTint(defaults: UserDefaults = .standard) {
		defaults.set(resolvedUserTintHex(defaults: defaults), forKey: userTintColorKey)
	}

	/// Converts wide-gamut picker colors to a valid six-digit sRGB value.
	func userTintHex() -> String {
		let resolvedColor = UIColor(self).resolvedColor(with: UITraitCollection.current)
		let sRGB = CGColorSpace(name: CGColorSpace.sRGB)
		let convertedColor = sRGB.flatMap {
			resolvedColor.cgColor.converted(to: $0, intent: .relativeColorimetric, options: nil)
		}

		var red: CGFloat = 0
		var green: CGFloat = 0
		var blue: CGFloat = 0
		var alpha: CGFloat = 0
		let color = convertedColor.map(UIColor.init(cgColor:)) ?? resolvedColor
		guard color.getRed(&red, green: &green, blue: &blue, alpha: &alpha) else {
			return Color.defaultUserTintHex
		}

		func byte(_ component: CGFloat) -> Int {
			Int((min(max(component, 0), 1) * 255).rounded())
		}

		return String(format: "#%02X%02X%02X", byte(red), byte(green), byte(blue))
	}

	/// Darker sibling of the user's tint for secondary states.
	static var userTintDeep: Color {
		Color(uiColor: UIColor(userTint).darkened())
	}
}

private extension UIColor {
	func darkened() -> UIColor {
		var hue: CGFloat = 0
		var saturation: CGFloat = 0
		var brightness: CGFloat = 0
		var alpha: CGFloat = 0

		guard getHue(&hue, saturation: &saturation, brightness: &brightness, alpha: &alpha) else { return self }

		return UIColor(
			hue: hue,
			saturation: min(saturation * 1.1, 1),
			// Floor keeps a near-black tint from vanishing into a dark background.
			brightness: min(max(brightness * 0.85, 0.32), 0.85),
			alpha: alpha
		)
	}
}
