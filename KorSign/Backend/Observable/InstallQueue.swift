//
//  InstallQueue.swift
//  KorSign
//
//  Created by Ryuk on 24.08.2026.
//

import Foundation
import SwiftUI
import NimbleExtensions
import IDeviceSwift

/// Every install and export runs through here. One sheet at a time keeps the OTA server from
/// starting twice and lets a job survive a dismissed sheet.
@MainActor
final class InstallQueue: ObservableObject {
	static let shared = InstallQueue()
	static let dismissAfterInstallKey = "KorSign.dismissInstallSheetAfterSuccess"
	static let importAfterInstallKey = "KorSign.importAfterInstallSuccess"

	@Published private(set) var apps: [AnyApp] = []
	@Published private(set) var index = 0
	@Published private(set) var installer: AppInstaller?
	@Published private(set) var isFinished = false
	@Published private(set) var hasPendingImportRequest = false
	@Published var isSheetPresented = false

	private var _installed: [AppInfoPresentable] = []
	private var _requestsImportAfterDismiss = false
	private var _pendingFailure: Error?
	private var _foregroundObserver: NSObjectProtocol?

	private init() {
		_foregroundObserver = NotificationCenter.default.addObserver(
			forName: UIApplication.didBecomeActiveNotification,
			object: nil,
			queue: .main
		) { [weak self] _ in
			Task { @MainActor [weak self] in
				if let self {
					FileLogger.log("didBecomeActive current=\(self.current != nil) finished=\(self.isFinished) sheet=\(self.isSheetPresented) pendingImport=\(self.hasPendingImportRequest)", category: "install-import-debug")
				}
				self?._resumeWhenActive()
				self?._presentPendingFailureIfNeeded()
			}
		}
	}

	var current: AnyApp? { apps.indices.contains(index) ? apps[index] : nil }
	var upcoming: [AnyApp] { Array(apps.dropFirst(index + 1)) }
	var showsPill: Bool { current != nil && !isSheetPresented && !isFinished }

	/// A finished run has nothing left to reopen, so closing it retires the queue.
	func sheetDismissed() {
		FileLogger.log("sheetDismissed finished=\(isFinished) requestAfterDismiss=\(_requestsImportAfterDismiss) pendingImport=\(hasPendingImportRequest) appState=\(UIApplication.shared.applicationState.rawValue)", category: "install-import-debug")
		guard isFinished else { return }
		let requestsImport = _requestsImportAfterDismiss
		clear()
		if requestsImport { _queueImportRequest(source: "sheetDismissed") }
	}

	func consumeImportRequest() -> Bool {
		guard hasPendingImportRequest else { return false }
		hasPendingImportRequest = false
		FileLogger.log("import request consumed", category: "install-import-debug")
		return true
	}

	func enqueue(_ app: AppInfoPresentable, exporting: Bool = false) {
		let entry = AnyApp(base: app, archive: exporting)
		guard !apps.contains(where: { $0.id == entry.id }) else { return }

		if isFinished { _reset() }
		apps.append(entry)

		// Server installs can package and validate in the background. UI presentation
		// remains gated by _resumeWhenActive().
		activate()
		_resumeWhenActive()
	}

	/// Server preparation is UI-free; exports and iDevice installs retain their foreground flow.
	func activate() {
		guard
			installer == nil,
			let current
		else {
			return
		}
		let preparesServerInstall = !current.archive
			&& UserDefaults.standard.integer(forKey: "Feather.installationMethod") == 0
		guard UIApplication.shared.applicationState != .background || preparesServerInstall else { return }

		let installer = AppInstaller(app: current.base, isSharing: current.archive)
		self.installer = installer
		FileLogger.log("install preparation started appState=\(UIApplication.shared.applicationState.rawValue)", category: "install")
		installer.start { [weak self] result in self?._handle(result) }
	}

	private func _resumeWhenActive() {
		FileLogger.log("resumeWhenActive current=\(current != nil) finished=\(isFinished) sheet=\(isSheetPresented) pendingImport=\(hasPendingImportRequest) appState=\(UIApplication.shared.applicationState.rawValue)", category: "install-import-debug")
		guard
			current != nil,
			!isFinished,
			UIApplication.shared.applicationState == .active
		else {
			return
		}

		// Create the installer first so the sheet always has real content on its first frame.
		activate()
		InstallQueueWindow.shared.ensure()
		isSheetPresented = true
		DispatchQueue.main.async { [weak self] in self?.installer?.presentInstallIfReady() }
		FileLogger.log("install sheet presentation requested", category: "install-import-debug")
	}

	func clear() {
		FileLogger.log("queue clear current=\(current != nil) finished=\(isFinished) pendingImport=\(hasPendingImportRequest)", category: "install-import-debug")
		_reset()
		isSheetPresented = false
		InstallQueueWindow.shared.teardown()
	}

	func skip() {
		_abandon()
	}

	private func _handle(_ result: Result<AppInstaller.Outcome, Error>) {
		switch result {
		case .success(.cancelled):
			FileLogger.log("install result=cancelled", category: "install-import-debug")
			_abandon()
		case .success(.exported(let package)):
			FileLogger.log("install result=exported", category: "install-import-debug")
			_abandon()

			guard let package else { return }
			// Let the card leave first or the share sheet presents onto a dying view.
			DispatchQueue.main.asyncAfter(deadline: .now() + 0.35) {
				UIActivityViewController.show(activityItems: [package])
			}
		case .success(let outcome):
			if case .installed = outcome, let app = installer?.app { _installed.append(app) }
			if case .finishedUnverified = outcome {
				FileLogger.log("install tracking finished without verification; skipping deletion", category: "install")
			}
			if index + 1 == apps.count, UserDefaults.standard.bool(forKey: Self.dismissAfterInstallKey) {
				FileLogger.log("install tracking finished sheet=\(isSheetPresented) appState=\(UIApplication.shared.applicationState.rawValue); dismissing immediately", category: "install-import-debug")
				_advance()
				return
			}
			FileLogger.log("install tracking finished sheet=\(isSheetPresented) appState=\(UIApplication.shared.applicationState.rawValue); advancing in 1.2s", category: "install-import-debug")
			// Let the finished ring land before the next app takes over.
			DispatchQueue.main.asyncAfter(deadline: .now() + 1.2) { [weak self] in self?._advance() }
		case .failure(let error):
			FileLogger.error("install result=failure \(error.localizedDescription)", category: "install-import-debug")
			_pendingFailure = error
			_presentPendingFailureIfNeeded()
		}
	}

	private func _presentPendingFailureIfNeeded() {
		guard UIApplication.shared.applicationState == .active, let error = _pendingFailure else { return }
		_pendingFailure = nil
		DispatchQueue.main.async { [weak self] in
			guard UIApplication.shared.applicationState == .active else {
				self?._pendingFailure = error
				return
			}
			UIAlertController.showAlertWithOk(
				title: .localized("Install"),
				message: String(describing: error),
				action: {
					HeartbeatManager.shared.start(true)
					self?._abandon()
				}
			)
		}
	}

	/// Keeps the last app on screen so its finished state and Open button survive.
	private func _advance() {
		FileLogger.log("advance index=\(index) count=\(apps.count) sheet=\(isSheetPresented) appState=\(UIApplication.shared.applicationState.rawValue)", category: "install-import-debug")
		guard index + 1 < apps.count else {
			let defaults = UserDefaults.standard
			let dismisses = defaults.bool(forKey: Self.dismissAfterInstallKey)
			let requestsImport = dismisses && defaults.bool(forKey: Self.importAfterInstallKey)
			FileLogger.log("final install dismissSetting=\(dismisses) importSetting=\(defaults.bool(forKey: Self.importAfterInstallKey)) requestsImport=\(requestsImport) sheet=\(isSheetPresented)", category: "install-import-debug")
			isFinished = true
			if !isSheetPresented {
				clear()
				if requestsImport { _queueImportRequest(source: "advanceWithoutSheet") }
			} else if dismisses {
				_requestsImportAfterDismiss = requestsImport
				isSheetPresented = false
				FileLogger.log("install sheet dismissal requested requestAfterDismiss=\(_requestsImportAfterDismiss)", category: "install-import-debug")
			}
			return
		}

		installer?.stop()
		installer = nil
		index += 1
		activate()
	}

	/// Dismiss first so the card doesn't blank out mid animation.
	private func _abandon() {
		FileLogger.log("abandon index=\(index) count=\(apps.count) sheet=\(isSheetPresented)", category: "install-import-debug")
		guard index + 1 < apps.count else {
			guard isSheetPresented else {
				clear()
				return
			}

			installer?.stop()
			isFinished = true
			isSheetPresented = false
			return
		}

		_advance()
	}

	private func _reset() {
		installer?.stop()
		installer = nil
		apps.removeAll()
		index = 0
		isFinished = false
		_requestsImportAfterDismiss = false
		_pendingFailure = nil

		let installed = _installed
		_installed.removeAll()
		InstallCleanup.run(for: installed)
	}

	private func _queueImportRequest(source: String) {
		hasPendingImportRequest = true
		FileLogger.log("import request queued source=\(source) appState=\(UIApplication.shared.applicationState.rawValue)", category: "install-import-debug")
	}
}
