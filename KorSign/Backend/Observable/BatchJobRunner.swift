//
//  BatchJobRunner.swift
//  KorSign
//
//  Created by Ryuk
//

import Foundation
import SwiftUI

// MARK: - Model
struct BatchItem: Identifiable {
	enum State: Equatable {
		case queued
		case working
		case signed
		case alreadySigned
		case installed
		case failed(String)
		case skipped
	}

	let id: String
	let app: AppInfoPresentable
	var state: State = .queued
	var signed: Signed?

	init(app: AppInfoPresentable) {
		self.id = app.uuid ?? UUID().uuidString
		self.app = app
	}

	var installable: AppInfoPresentable { signed ?? app }
}

// MARK: - Runner
@MainActor
final class BatchJobRunner: ObservableObject {
	enum Mode {
		case sign
		case install
		case signAndInstall

		var signs: Bool { self != .install }
		var installs: Bool { self != .sign }
	}

	enum Phase: Equatable {
		case signing
		case installing
		case finished
	}

	@Published private(set) var items: [BatchItem]
	@Published private(set) var phase: Phase
	@Published private(set) var currentIndex: Int = 0
	@Published private(set) var currentInstaller: AppInstaller?
	/// Signing cannot be interrupted mid-app, so cancelling has to release the screen right away.
	@Published private(set) var isCancelled = false

	let mode: Mode
	private let _options: Options
	private let _overrides: [String: Options]
	private let _icons: [String: UIImage]
	private let _certificate: CertificatePair?
	private let _resignsSigned: Bool
	private var _cancelled = false
	private var _started = false
	private var _installContinuation: CheckedContinuation<Result<AppInstaller.Outcome, Error>, Never>?
	private var _installed: [AppInfoPresentable] = []
	private var _retired = false

	init(
		apps: [AppInfoPresentable],
		mode: Mode,
		options: Options,
		overrides: [String: Options] = [:],
		icons: [String: UIImage] = [:],
		certificate: CertificatePair?,
		resignsSigned: Bool = true
	) {
		self.items = apps.map(BatchItem.init)
		self.mode = mode
		self._options = options
		self._overrides = overrides
		self._icons = icons
		self._certificate = certificate
		self._resignsSigned = resignsSigned
		self.phase = mode.signs ? .signing : .installing
	}

	var isFinished: Bool { phase == .finished }

	var succeeded: Int {
		items.filter { item in
			switch item.state {
			case .installed: true
			case .signed, .alreadySigned: !mode.installs
			default: false
			}
		}.count
	}

	var failed: Int {
		items.filter {
			if case .failed = $0.state { return true }
			return false
		}.count
	}

	func run() async {
		guard !_started else { return }
		_started = true

		// One assertion for the whole queue per-app ones drop to zero between apps and let iOS suspend us
		let keepAlive = BackgroundTaskManager(
			taskName: "Batch",
			expirationTitle: .localized("Batch continuing"),
			expirationBody: .localized("The remaining apps will continue when you reopen the app")
		)
		keepAlive.start()
		defer { keepAlive.stop() }

		if mode.signs {
			await _signAll()
		}

		if mode.installs, !_cancelled {
			await _installAll()
		}

		phase = .finished
		_cleanupIfRetired()
	}

	func cancel() {
		_cancelled = true
		isCancelled = true
		currentInstaller?.stop()
		_resumeInstall(.success(.cancelled))

		for index in items.indices where items[index].state == .queued || items[index].state == .working {
			items[index].state = .skipped
		}
	}

	/// A declined iOS install prompt leaves the status pending forever, with nothing else to wake it.
	func skipCurrentInstall() {
		guard _installContinuation != nil else { return }
		currentInstaller?.stop()
		_resumeInstall(.success(.cancelled))
	}

	/// Release Library records only after the results UI is gone and work has stopped.
	func retire() {
		_retired = true
		if !isFinished { cancel() }
		_cleanupIfRetired()
	}

	private func _cleanupIfRetired() {
		guard _retired, isFinished else { return }
		let installed = _installed
		_installed.removeAll()
		InstallCleanup.run(for: installed)
	}

	// MARK: Phases

	private func _signAll() async {
		phase = .signing

		for index in items.indices {
			guard !_cancelled else { return }

			currentIndex = index

			let app = items[index].app

			guard _resignsSigned || !app.isSigned else {
				items[index].state = .alreadySigned
				continue
			}

			items[index].state = .working

			let options = _overrides[items[index].id] ?? _options.resolved(for: app)
			let icon = _icons[items[index].id]

			let result = await withCheckedContinuation { (continuation: CheckedContinuation<Result<Signed, Error>, Never>) in
				FR.signPackageFile(app, using: options, icon: icon, certificate: _certificate) { result in
					continuation.resume(returning: result)
				}
			}

			switch result {
			case .success(let signed):
				items[index].signed = signed
				items[index].state = .signed

				if options.post_deleteAppAfterSigned, !app.isSigned {
					Storage.shared.deleteApp(for: app)
				}
			case .failure(let error):
				items[index].state = .failed(error.localizedDescription)
			}
		}
	}

	private func _installAll() async {
		phase = .installing

		for index in items.indices {
			guard !_cancelled else { return }
			// Still queued means install-only; anything else never produced a package.
			switch items[index].state {
			case .signed, .alreadySigned, .queued: break
			default: continue
			}

			currentIndex = index
			items[index].state = .working

			let installer = AppInstaller(app: items[index].installable)
			currentInstaller = installer

			let result = await withCheckedContinuation { (continuation: CheckedContinuation<Result<AppInstaller.Outcome, Error>, Never>) in
				_installContinuation = continuation
				installer.start { [weak self, weak installer] outcome in
					guard let self, let installer, self.currentInstaller === installer,
						self._installContinuation != nil else { return }
					// Record terminal evidence before cancellation can race the resumed task.
					if case .success(.installed) = outcome {
						self._installed.append(installer.app)
						self.items[index].state = .installed
					}
					self._resumeInstall(outcome)
				}
			}

			installer.stop()
			currentInstaller = nil

			guard !_cancelled else { return }

			switch result {
			case .success(.installed):
				items[index].state = .installed
			case .success(.cancelled):
				items[index].state = .skipped
			case .success(.finishedUnverified), .success(.exported):
				items[index].state = .failed(.localized("Installation finished but could not be verified. The signed app has been kept."))
			case .failure(let error):
				items[index].state = .failed(error.localizedDescription)
			}
		}
	}

	private func _resumeInstall(_ result: Result<AppInstaller.Outcome, Error>) {
		guard let continuation = _installContinuation else { return }
		_installContinuation = nil
		continuation.resume(returning: result)
	}
}
