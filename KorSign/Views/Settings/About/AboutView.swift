//
//  AboutView.swift
//  KorSign
//
//  Created by samara on 30.04.2025.
//

import SwiftUI
import NimbleViews

// MARK: - Extension: Model
extension AboutView {
	struct CreditsModel: Codable, Hashable {
		let name: String?
		let desc: String?
		let github: String
	}
}

// MARK: - View
struct AboutView: View {
	// Hardcoded: upstream's creditsv2.json now 404s.
	private let _credits: [CreditsModel] = [
		.init(name: "Korboy", desc: "KorSign Developer", github: "korboybeats"),
		.init(name: "Ryuk", desc: "RyukSign Author and Upstream Maintainer", github: "faroukbmiled"),
		.init(name: "claration", desc: "Feather — original project", github: "claration"),
		.init(name: "Asami", desc: "Developer", github: "Nyasami"),
		.init(name: "Lakhan Lothiyi", desc: "AltStore Repositories", github: "llsc12"),
	]

	private let _sourceURL = "https://github.com/korboybeats/KorSign"
	private let _ryukSignURL = "https://github.com/faroukbmiled/Ryuk%53ign"
	private let _featherURL = "https://github.com/claration/Feather"
	private let _licenseURL = "https://github.com/korboybeats/KorSign/blob/main/LICENSE"

	// MARK: Body
	var body: some View {
		NBList(.localized("About")) {
			Section {
				VStack {
					FRAppIconView(size: 72)

					Text(Bundle.main.name)
						.font(.largeTitle)
						.bold()
						.foregroundStyle(Color.accentColor)

					HStack(spacing: 4) {
						Text(.localized("Version"))
						Text(Bundle.main.version)
					}
					.font(.footnote)
					.foregroundStyle(.secondary)
				}
			}
			.frame(maxWidth: .infinity)
			.listRowBackground(EmptyView())

			NBSection(.localized("Credits")) {
				ForEach(_credits, id: \.github) { credit in
					_credit(name: credit.name, desc: credit.desc, github: credit.github)
				}
			}

			NBSection(.localized("Source & License")) {
				Button(.localized("KorSign Source Code"), systemImage: "chevron.left.forwardslash.chevron.right") {
					UIApplication.open(_sourceURL)
				}
				Button(.localized("License (GPL-3.0)"), systemImage: "doc.text") {
					UIApplication.open(_licenseURL)
				}
				Button(.localized("Based on RyukSign"), systemImage: "arrow.triangle.branch") {
					UIApplication.open(_ryukSignURL)
				}
				Button(.localized("Originally based on Feather"), systemImage: "arrow.triangle.branch") {
					UIApplication.open(_featherURL)
				}
			} footer: {
				Text(.localized("KorSign is free software under the GPL-3.0 license. It is a modified fork of RyukSign, which is derived from Feather by claration. KorSign's complete corresponding source is available at the Source Code link above."))
			}
		}
	}
}

// MARK: - Extension: view
extension AboutView {
	@ViewBuilder
	private func _credit(
		name: String?,
		desc: String?,
		github: String
	) -> some View {
		Button {
			UIApplication.open("https://github.com/\(github)")
		} label: {
			HStack {
				FRIconCellView(
					title: name ?? github,
					subtitle: desc ?? "",
					iconUrl: URL(string: "https://github.com/\(github).png")!,
					size: 45,
					isCircle: true
				)

				Image(systemName: "arrow.up.right")
					.foregroundColor(.secondary.opacity(0.65))
			}
		}
	}
}
