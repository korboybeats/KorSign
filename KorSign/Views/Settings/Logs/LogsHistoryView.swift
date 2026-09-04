//
//  LogsHistoryView.swift
//  KorSign
//
//  Created by Ryuk
//

import SwiftUI
import NimbleViews

// MARK: - View
struct LogsHistoryView: View {
	@State private var _entries: [LogEntry] = []
	@State private var _isExporting = false

	// MARK: Body
	var body: some View {
		NBNavigationView(.localized("Activity Logs"), displayMode: .inline) {
			LogConsoleView(entries: _entries, showCategory: true, onRefresh: _load)
				.background(Color(uiColor: LogConsoleView.consoleBackgroundColor))
				.ignoresSafeArea(edges: .bottom)
				.overlay {
					if _entries.isEmpty {
						Text(.localized("No logs yet"))
							.font(.footnote)
							.foregroundStyle(.white.opacity(0.35))
					}
				}
				.toolbar {
					ToolbarItem(placement: .topBarTrailing) {
						Button(.localized("Share"), systemImage: "square.and.arrow.up") {
							_isExporting = true
							Task {
								defer { _isExporting = false }
								do {
									let export = try await Task.detached { try FileLogger.export() }.value
									UIActivityViewController.show(activityItems: [export.url], retaining: export)
								} catch {
									Toast.error(.localized("Couldn't export logs"))
								}
							}
						}
						.labelStyle(.iconOnly)
						.disabled(_entries.isEmpty || _isExporting)
					}
					NBToolbarMenu(systemImage: "ellipsis.circle", style: .icon, placement: .topBarTrailing) {
						Button(.localized("Refresh"), systemImage: "arrow.clockwise") { _load() }
						Divider()
						Button(.localized("Clear"), systemImage: "trash", role: .destructive) {
							FileLogger.clear()
							_entries = []
						}
					}
				}
				.onAppear(perform: _load)
				.toolbarBackground(Color(uiColor: LogConsoleView.consoleBackgroundColor), for: .navigationBar)
				.toolbarBackground(.visible, for: .navigationBar)
				.toolbarColorScheme(.dark, for: .navigationBar)
		}
	}

	private func _load() {
		DispatchQueue.global(qos: .userInitiated).async {
			let entries = LogParser.parseFile(FileLogger.readAll(), limit: 2000)
			DispatchQueue.main.async { _entries = entries }
		}
	}
}
