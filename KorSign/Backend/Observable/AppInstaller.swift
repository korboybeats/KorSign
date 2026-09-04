//
//  AppInstaller.swift
//  KorSign
//
//  Created by Ryuk
//

import Combine
import Foundation
import SwiftUI
import IDeviceSwift

/// Install pipeline without a UI, so the single-app card and the batch queue can share it.
@MainActor
final class AppInstaller: ObservableObject {
	enum Outcome {
		case installed
		case finishedUnverified
		case cancelled
		case exported(URL?)
	}

	let app: AppInfoPresentable
	let viewModel: InstallerStatusViewModel

	/// redirect page fallback.
	@Published var isPresentingFallbackPage = false
	@Published private(set) var finishedUnverified = false

	private let _isSharing: Bool
	private let _installationMethod = UserDefaults.standard.integer(forKey: "Feather.installationMethod")
	private let _serverMethod = UserDefaults.standard.integer(forKey: "Feather.serverMethod")
	private let _useShareSheet = UserDefaults.standard.bool(forKey: "Feather.useShareSheetForArchiving")

	private var _server: ServerInstaller?
	private var _progressTask: Task<Void, Never>?
	private var _statusObserver: AnyCancellable?
	private var _completion: ((Result<Outcome, Error>) -> Void)?
	private var _hasFinished = false
	private var _pendingInstallURL: URL?
	private var _isInstallOpenScheduled = false
	private var _foregroundObserver: NSObjectProtocol?
	private var _ota = OTAInstallState()
	private let _installProbe = InstalledAppProbe()
	private var _workspaceDiagnostic: InstallWorkspaceDiagnostic?
	private var _previousInstallation: InstalledAppRecord?
	private var _expectedVersion: String?
	private var _expectedBuild: String?

	var fallbackPageURL: URL? { _server?.pageEndpoint }
	private func _advanceOTA(to phase: OTAInstallState.Phase) {
		guard phase.rawValue > _ota.phase.rawValue else { return }
		objectWillChange.send()
		_ota.advance(to: phase, now: ProcessInfo.processInfo.systemUptime)
	}

	init(app: AppInfoPresentable, isSharing: Bool = false) {
		self.app = app
		self._isSharing = isSharing
		self.viewModel = InstallerStatusViewModel(isIdevice: _installationMethod == 1)

		if !isSharing, _installationMethod == 0 {
			_server = try? ServerInstaller(app: app, viewModel: viewModel)
			_foregroundObserver = NotificationCenter.default.addObserver(
				forName: UIApplication.didBecomeActiveNotification,
				object: nil,
				queue: .main
			) { [weak self] _ in
				Task { @MainActor [weak self] in self?.presentInstallIfReady() }
			}
		}
	}

	deinit {
		_workspaceDiagnostic?.stop()
		_progressTask?.cancel()
		if let _foregroundObserver { NotificationCenter.default.removeObserver(_foregroundObserver) }
	}

	func start(completion: @escaping (Result<Outcome, Error>) -> Void) {
		guard _completion == nil, !_hasFinished else { return }
		_completion = completion

		guard _isSharing || app.identifier != Bundle.main.bundleIdentifier! || _installationMethod == 1 else {
			_finish(.failure(Self.error(.localized("You cannot update '%@' with itself, please use an alternative tool to update it.", arguments: Bundle.main.name))))
			return
		}

		_statusObserver = viewModel.$status
			.receive(on: DispatchQueue.main)
			.sink { [weak self] in self?._handle($0) }

		Task { await _run() }
	}

	/// Stops without reporting an outcome; the caller has already moved on.
	func stop() {
		FileLogger.log("installation stopped by caller", category: "install")
		_hasFinished = true
		_workspaceDiagnostic?.stop()
		_workspaceDiagnostic = nil
		_completion = nil
		_pendingInstallURL = nil
		_advanceOTA(to: .finished)
		_server?.stop()
		_statusObserver = nil
		_progressTask?.cancel()
		_progressTask = nil
	}

	// MARK: Pipeline

	private func _run() async {
		let keepAlive = BackgroundTaskManager(
			taskName: "Install",
			expirationTitle: .localized("Installation continuing"),
			expirationBody: .localized("The installation will continue when you reopen the app")
		)
		keepAlive.start()
		defer { keepAlive.stop() }

		do {
			let (package, exported) = try await _package()
			defer { withExtendedLifetime(package) {} }
			guard !_hasFinished else { return }

			guard !_isSharing else {
				_finish(.success(.exported(_useShareSheet ? exported : nil)))
				return
			}

			switch _installationMethod {
			case 1:
				try await InstallationProxy(viewModel: viewModel)
					.install(at: package.url, suspend: app.identifier == Bundle.main.bundleIdentifier!)
			default:
				await _serveForOTA(package)
			}
		} catch {
			_progressTask?.cancel()
			_finish(.failure(error))
		}
	}

	/// Copying and zipping the bundle stays off the main actor; both are long and fully blocking.
	private func _package() async throws -> (package: InstallationArchive, exported: URL?) {
		let handler = ArchiveHandler(app: app, viewModel: viewModel)
		let isSharing = _isSharing
		let useShareSheet = _useShareSheet

		return try await Task.detached(priority: .userInitiated) {
			try await handler.move()
			let package = try await handler.archive()

			guard isSharing else { return (package, nil) }
			return (package, try await handler.moveToArchive(package.url, shouldOpen: !useShareSheet))
		}.value
	}

	private func _serveForOTA(_ package: InstallationArchive) async {
		guard let server = _server else {
			_finish(.failure(Self.error(.localized("Could not build the installation link, check your connection and try again."))))
			return
		}

		guard !_hasFinished else { return }
		server.package = package
		guard let identifier = app.identifier, !identifier.isEmpty else {
			_finish(.failure(Self.error(.localized("The signed app has no bundle identifier."))))
			return
		}
		let probe = _installProbe
		_previousInstallation = await Task.detached { probe.read(identifier).record }.value
		guard !_hasFinished else { return }
		if let directory = Storage.shared.getAppDirectory(for: app),
		   let data = try? Data(contentsOf: directory.appendingPathComponent("Info.plist")),
		   let info = try? PropertyListSerialization.propertyList(from: data, format: nil) as? [String: Any] {
			_expectedVersion = info["CFBundleShortVersionString"] as? String
			_expectedBuild = info["CFBundleVersion"] as? String
		}
		FileLogger.log("verification baseline=\(String(describing: _previousInstallation)) expectedVersion=\(_expectedVersion ?? "unknown") expectedBuild=\(_expectedBuild ?? "unknown")", category: "install")

		if _serverMethod == 1 {
			viewModel.status = .sendingManifest
			server.manifestUrl = await ManifestService.resolve(for: app, payload: server.payloadEndpoint)
		}

		var failure = server.startupError
		if failure == nil {
			failure = await server.selfCheck()
		}

		guard !_hasFinished else { return }
		viewModel.status = failure.map { .broken($0) } ?? .ready
	}

	// MARK: Status

	private func _handle(_ status: InstallerStatusViewModel.InstallerStatus) {
		guard !_hasFinished else { return }
		FileLogger.log("installer status=\(String(describing: status))", category: "install")
		switch status {
		case .ready where _installationMethod == 0:
			_openInstall(_serverMethod == 0 ? _server?.iTunesLink : _server?.iTunesLinkExternal)
		case .sendingManifest:
			break // Manifest probes do not prove acceptance or cancellation.
		case .sendingPayload where _installationMethod == 0:
			isPresentingFallbackPage = false
			_advanceOTA(to: .downloading)
		case .installing where _installationMethod == 0:
			_advanceOTA(to: .verifying)
		case .completed(let result):
			_progressTask?.cancel()
			_progressTask = nil
			_finish(result.map { self.finishedUnverified ? .finishedUnverified : .installed })
		case .broken(let error):
			_progressTask?.cancel()
			_progressTask = nil
			_finish(.failure(error))
		default:
			break
		}
	}

	/// Opens a prepared OTA request only while UIKit can present it. The URL remains pending
	/// across backgrounding, so packaging and server validation never need to wait for the UI.
	func presentInstallIfReady() {
		guard
			!_hasFinished,
			!_isInstallOpenScheduled,
			_pendingInstallURL != nil,
			UIApplication.shared.applicationState == .active
		else { return }

		_isInstallOpenScheduled = true
		DispatchQueue.main.async { [weak self] in
			guard let self else { return }
			self._isInstallOpenScheduled = false
			guard
				!self._hasFinished,
				UIApplication.shared.applicationState == .active,
				let url = self._pendingInstallURL
			else { return }

			self._pendingInstallURL = nil
			self._advanceOTA(to: .waiting)
			self._installProbe.resetProgress()
			// Temporary Dev-only evidence collection; never drives install state or cleanup.
			if Bundle.main.bundleIdentifier?.hasSuffix(".dev") == true, let identifier = self.app.identifier {
				self._workspaceDiagnostic = InstallWorkspaceDiagnostic(identifier: identifier) {
					FileLogger.log($0, category: "install-observer")
				}
			}
			self._startProgressPolling()
			FileLogger.log("opening \(url.absoluteString)", category: "install")
			UIApplication.shared.open(url) { [weak self] opened in
				FileLogger.log("itms-services accepted by iOS: \(opened)", category: "install")

				guard let self, !self._hasFinished else { return }
				if !opened {
					FileLogger.error("iOS refused the scheme, falling back to the redirect page", category: "install")
					self.isPresentingFallbackPage = true
				}
			}
		}
	}

	// Direct open keeps the install to one tap; the redirect page is only for builds that refuse the scheme.
	private func _openInstall(_ link: String?) {
		guard let link, let url = URL(string: link) else {
			_finish(.failure(Self.error(.localized("Could not build the installation link, check your connection and try again."))))
			return
		}

		_pendingInstallURL = url
		FileLogger.log("install link ready appState=\(UIApplication.shared.applicationState.rawValue)", category: "install")
		presentInstallIfReady()
	}

	private func _finish(_ result: Result<Outcome, Error>) {
		guard !_hasFinished else { return }
		_hasFinished = true
		_workspaceDiagnostic?.stop()
		_workspaceDiagnostic = nil
		_pendingInstallURL = nil
		_progressTask?.cancel()
		_progressTask = nil
		FileLogger.log("installation finished: \(String(describing: result))", category: "install")
		_advanceOTA(to: .finished)
		_server?.stop()
		_statusObserver = nil

		let completion = _completion
		_completion = nil
		completion?(result)
	}

	private static func error(_ message: String) -> Error {
		NSError(domain: "Install", code: -1, userInfo: [NSLocalizedDescriptionKey: message])
	}

	// MARK: Progress

	private func _startProgressPolling() {
		guard _progressTask == nil else { return }
		let probe = _installProbe
		_progressTask = Task { [weak self] in
			var lastEvidence = ""
			while !Task.isCancelled {
				guard let identifier = self?.app.identifier else { break }
				let evidence = await Task.detached(priority: .utility) { probe.read(identifier) }.value
				guard !Task.isCancelled, let self, !self._hasFinished else { return }
				let description = "progress=\(String(describing: evidence.progress)) record=\(String(describing: evidence.record))"
				if description != lastEvidence {
					FileLogger.log("verification \(description)", category: "install")
					lastEvidence = description
				}
				if (self._ota.phase == .downloading || self._ota.phase == .verifying),
				   evidence.progress?.isCancelled == true || evidence.progress?.installStateName == "Cancelled"
					|| evidence.progress?.installStateName == "Failed" {
					self.viewModel.status = .broken(Self.error(.localized("iOS reported an unsuccessful installation. The signed app has been kept.")))
					return
				}
				let progressConfirmed = self._ota.confirmsInstall(evidence.progress)
				let recordConfirmed = self._ota.phase == .verifying && evidence.record?.confirmsReplacement(
					of: self._previousInstallation, version: self._expectedVersion, build: self._expectedBuild) == true
				if progressConfirmed || recordConfirmed {
					FileLogger.log("installation confirmed by \(progressConfirmed ? "final install state" : "changed app record")", category: "install")
					self.viewModel.installProgress = 1
					self.viewModel.status = .completed(.success(()))
					return
				}
				if self._ota.progressEnded(evidence.progress, now: ProcessInfo.processInfo.systemUptime) {
					self.finishedUnverified = true
					FileLogger.log("workspace progress ended; registration unavailable or unchanged; retaining signed app", category: "install")
					self.viewModel.installProgress = 1
					self.viewModel.status = .completed(.success(()))
					return
				}
				if let raw = evidence.progress?.fraction, raw.isFinite {
					self.viewModel.installProgress = min(0.99, max(0, (raw - 0.6) / 0.3))
				}
				if self._ota.timedOut(at: ProcessInfo.processInfo.systemUptime) {
					let message: String
					switch self._ota.phase {
					case .waiting: message = .localized("Installation didn't start. The signed app has been kept. Try installing it again.")
					case .downloading: message = .localized("The installation download did not finish in time. The signed app has been kept. Try again with KorSign open.")
					default: message = .localized("Installation could not be verified. Check the app on your Home Screen. The signed app has been kept.")
					}
					self.viewModel.status = .broken(Self.error(message))
					return
				}
				try? await Task.sleep(nanoseconds: 250_000_000)
			}
		}
	}
}
