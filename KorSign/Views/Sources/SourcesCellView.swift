//
//  SourcesCellView.swift
//  KorSign
//
//  Created by samara on 1.05.2025.
//

import SwiftUI
import NimbleViews
import NukeUI

// MARK: - View
struct SourcesCellView: View {
	@Environment(\.horizontalSizeClass) private var horizontalSizeClass

	var source: AltSource
	var isEditMode: Bool = false

	@State private var _isExcluded: Bool = false

	private var _sourceIdentifier: String {
		source.identifier ?? source.sourceURL?.absoluteString ?? ""
	}

	// MARK: Body
	var body: some View {
		let isRegular = horizontalSizeClass != .compact

		let cellContent = HStack {
			FRIconCellView(
				title: source.name ?? .localized("Unknown"),
				subtitle: source.sourceURL?.absoluteString ?? "",
				iconUrl: source.iconURL
			)
			if _isExcluded {
				Image(systemName: "eye.slash")
					.foregroundColor(.secondary)
					.font(.caption2)
			}
		}
		.padding(isRegular ? 12 : 0)
		.background(
			isRegular
			? RoundedRectangle(cornerRadius: 18, style: .continuous)
				.fill(Color(.quaternarySystemFill))
			: nil
		)

		if isEditMode {
			cellContent
		} else {
			cellContent
				.swipeActions {
					_actions(for: source)
					_excludeAction()
					_contextActions(for: source)
				}
				.contextMenu {
					_contextActions(for: source)
					_excludeAction()
					Divider()
					_actions(for: source)
				}
		}
	}
}

// MARK: - Extension: View
extension SourcesCellView {
	@ViewBuilder
	private func _actions(for source: AltSource) -> some View {
		Button(.localized("Delete"), systemImage: "trash", role: .destructive) {
			Storage.shared.deleteSource(for: source)
		}
	}

	@ViewBuilder
	private func _contextActions(for source: AltSource) -> some View {
		Button(.localized("Copy"), systemImage: "doc.on.clipboard") {
			UIPasteboard.general.string = source.sourceURL?.absoluteString
		}
	}

	@ViewBuilder
	private func _excludeAction() -> some View {
		Button {
			let newValue = !_isExcluded
			RepositorySettings.setSourceExcluded(_sourceIdentifier, excluded: newValue)
			_isExcluded = newValue
		} label: {
			Label(
				_isExcluded ? .localized("Show in All") : .localized("Hide from All"),
				systemImage: _isExcluded ? "eye" : "eye.slash"
			)
		}
		.tint(.orange)
	}
}

// MARK: - Extension: onAppear
extension SourcesCellView {
	func onAppearLoadExcluded() -> some View {
		self.onAppear {
			_isExcluded = RepositorySettings.isSourceExcluded(_sourceIdentifier)
		}
	}
}
