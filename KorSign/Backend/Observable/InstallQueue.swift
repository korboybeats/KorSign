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

/// Presents one install prompt at a time while accepted server installs keep running.
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
	private var _pendingFailures: [(error: Error, installer: AppInstaller?)] = []
	private var _isShowingFailure = false
	private var _running: [ObjectIdentifier: AppInstaller] = [:]
	private var _prepared: [String: AppInstaller] = [:]
	private var _currentCompleted = false
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
		if _currentCompleted {
			_advance()
		} else if let installer, installer.hasStartedDownload {
			_continueAfterDownload(installer)
		}

		// Server installs can package and validate in the background. UI presentation
		// remains gated by _resumeWhenActive().
		activate()
		_prepareUpcoming()
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

		if UserDefaults.standard.integer(forKey: "Feather.installationMethod") != 1 {
			for prepared in _prepared.values { prepared.stop() }
			_prepared.removeAll()
		}
		let installer = _prepared.removeValue(forKey: current.id)
			?? AppInstaller(app: current.base, isSharing: current.archive)
		self.installer = installer
		FileLogger.log("install preparation started appState=\(UIApplication.shared.applicationState.rawValue)", category: "install")
		installer.onDownloadStarted = { [weak self, weak installer] in
			guard let installer else { return }
			self?._continueAfterDownload(installer)
		}
		installer.start { [weak self, weak installer] result in
			guard let installer else { return }
			self?._handle(result, from: installer)
		}
		_prepareUpcoming()
	}

	private func _prepareUpcoming() {
		guard installer != nil, UserDefaults.standard.integer(forKey: "Feather.installationMethod") == 1 else { return }
		for entry in upcoming where !entry.archive && _prepared[entry.id] == nil {
			let preparation = AppInstaller(app: entry.base)
			_prepared[entry.id] = preparation
			preparation.prepare()
		}
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

	private func _continueAfterDownload(_ active: AppInstaller) {
		guard installer === active, index + 1 < apps.count else { return }
		_running[ObjectIdentifier(active)] = active
		installer = nil
		index += 1
		_currentCompleted = false
		activate()
	}

	private func _handle(_ result: Result<AppInstaller.Outcome, Error>, from active: AppInstaller) {
		if _running.removeValue(forKey: ObjectIdentifier(active)) != nil {
			if case .success(.installed) = result { _installed.append(active.app) }
			if case .failure(let error) = result {
				_pendingFailures.append((error, nil))
				_presentPendingFailureIfNeeded()
			}
			if _currentCompleted { _advance() }
			return
		}
		guard installer === active else { return }
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
			_currentCompleted = true
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
			DispatchQueue.main.asyncAfter(deadline: .now() + 1.2) { [weak self, weak active] in
				guard let self, self.installer === active else { return }
				self._advance()
			}
		case .failure(let error):
			FileLogger.error("install result=failure \(error.localizedDescription)", category: "install-import-debug")
			_pendingFailures.append((error, active))
			_presentPendingFailureIfNeeded()
		}
	}

	private func _presentPendingFailureIfNeeded() {
		guard UIApplication.shared.applicationState == .active, !_isShowingFailure, !_pendingFailures.isEmpty else { return }
		_isShowingFailure = true
		let failure = _pendingFailures.removeFirst()
		DispatchQueue.main.async { [weak self] in
			guard UIApplication.shared.applicationState == .active else {
				self?._isShowingFailure = false
				self?._pendingFailures.insert(failure, at: 0)
				return
			}
			UIAlertController.showAlertWithOk(
				title: .localized("Install"),
				message: String(describing: failure.error),
				action: {
					HeartbeatManager.shared.start(true)
					self?._isShowingFailure = false
					if let failed = failure.installer, self?.installer === failed { self?._abandon() }
					self?._presentPendingFailureIfNeeded()
				}
			)
		}
	}

	/// Keeps the last app on screen so its finished state and Open button survive.
	private func _advance() {
		FileLogger.log("advance index=\(index) count=\(apps.count) sheet=\(isSheetPresented) appState=\(UIApplication.shared.applicationState.rawValue)", category: "install-import-debug")
		guard index + 1 < apps.count else {
			guard _running.isEmpty else { return }
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
		_currentCompleted = false
		activate()
	}

	/// Dismiss first so the card doesn't blank out mid animation.
	private func _abandon() {
		FileLogger.log("abandon index=\(index) count=\(apps.count) sheet=\(isSheetPresented)", category: "install-import-debug")
		guard index + 1 < apps.count else {
			guard isSheetPresented else {
				if !_running.isEmpty { installer?.stop(); _currentCompleted = true; return }
				clear()
				return
			}

			installer?.stop()
			_currentCompleted = true
			if !_running.isEmpty { isSheetPresented = false; return }
			isFinished = true
			isSheetPresented = false
			return
		}

		_advance()
	}

	private func _reset() {
		for prepared in _prepared.values { prepared.stop() }
		_prepared.removeAll()
		installer?.stop()
		installer = nil
		apps.removeAll()
		index = 0
		isFinished = false
		_requestsImportAfterDismiss = false
		_pendingFailures.removeAll()
		for active in _running.values { active.stop() }
		_running.removeAll()
		_currentCompleted = false

		let installed = _installed
		_installed.removeAll()
		InstallCleanup.run(for: installed)
	}

	private func _queueImportRequest(source: String) {
		hasPendingImportRequest = true
		FileLogger.log("import request queued source=\(source) appState=\(UIApplication.shared.applicationState.rawValue)", category: "install-import-debug")
	}
}
