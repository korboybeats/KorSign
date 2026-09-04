//
//  PrimaryTabEmptyState.swift
//  KorSign
//

import SwiftUI

/// Keeps the empty states in the main tabs aligned even when their symbols have
/// different intrinsic sizes.
struct PrimaryTabEmptyState<Actions: View>: View {
	let title: String
	let systemImage: String
	let description: String
	@ViewBuilder let actions: Actions

	init(
		_ title: String,
		systemImage: String,
		description: String,
		@ViewBuilder actions: () -> Actions
	) {
		self.title = title
		self.systemImage = systemImage
		self.description = description
		self.actions = actions()
	}

	var body: some View {
		VStack(spacing: 0) {
			Image(systemName: systemImage)
				.font(.system(size: 52))
				.foregroundStyle(.secondary)
				.frame(width: 64, height: 64)

			Text(title)
				.font(.title2.weight(.bold))
				.multilineTextAlignment(.center)
				.lineLimit(1)
				.frame(height: 30)
				.padding(.top, 12)

			Text(description)
				.font(.callout)
				.foregroundStyle(.secondary)
				.multilineTextAlignment(.center)
				.lineLimit(2)
				.frame(height: 42, alignment: .top)
				.padding(.top, 4)

			actions
				.frame(height: 40)
				.padding(.top, 12)
		}
		.padding(.horizontal, 24)
	}
}

/// Shared larger action label for the main-tab empty states.
struct PrimaryTabEmptyStateButton: View {
	let title: String

	init(_ title: String) {
		self.title = title
	}

	var body: some View {
		Text(title)
			.font(.body.weight(.semibold))
			.padding(.horizontal, 22)
			.frame(height: 40)
			.background(Color(uiColor: .quaternarySystemFill))
			.clipShape(Capsule())
	}
}
