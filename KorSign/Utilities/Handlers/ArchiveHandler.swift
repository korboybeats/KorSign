//
//  ArchiveHandler.swift
//  KorSign
//
//  Created by samara on 22.04.2025.
//

import Foundation
import UIKit.UIApplication
import Zip
import SwiftUI
import IDeviceSwift

final class ArchiveHandler: NSObject {
	let viewModel: InstallerStatusViewModel

	private let _fileManager = FileManager.default
	private let _archive = InstallationArchive()
	private var _payloadUrl: URL?

	private let _appURL: URL?
	private let _appName: String?
	private let _appVersion: String?
	private var _uniqueWorkDir: URL { _archive.directory }
	private var backgroundTaskManager: BackgroundTaskManager?
	
	@MainActor
	init(app: AppInfoPresentable, viewModel: InstallerStatusViewModel) {
		self.viewModel = viewModel
		self._appURL = Storage.shared.getAppDirectory(for: app)
		self._appName = app.name
		self._appVersion = app.version
		
		super.init()
	}
	
	func move() async throws {
		guard let appUrl = _appURL else {
			throw SigningFileHandlerError.appNotFound
		}
		
		let payloadUrl = _uniqueWorkDir.appendingPathComponent("Payload")
		let movedAppURL = payloadUrl.appendingPathComponent(appUrl.lastPathComponent)

		try _fileManager.createDirectoryIfNeeded(at: payloadUrl)
		
		try _fileManager.copyItem(at: appUrl, to: movedAppURL)
		_payloadUrl = payloadUrl
	}
	
	func archive() async throws -> InstallationArchive {
		// Keep archiving alive in the background.
		await MainActor.run {
			if self.backgroundTaskManager == nil {
				self.backgroundTaskManager = BackgroundTaskManager(
					taskName: "ArchiveHandler",
					expirationTitle: "Archiving continuing",
					expirationBody: "The archiving will continue when you reopen the app"
				)
				self.backgroundTaskManager?.start()
			}
		}

		return try await Task.detached(priority: .background) { [self] in
			defer {
				Task { @MainActor in
					self.backgroundTaskManager?.stop()
					self.backgroundTaskManager = nil
				}
			}

			guard let payloadUrl = self._payloadUrl else {
				throw SigningFileHandlerError.appNotFound
			}

			let ipaUrl = self._archive.url
			let gate = ProgressGate()

			try AppArchiver.zip(
				payload: payloadUrl,
				to: ipaUrl,
				compression: ZipCompression.allCases[ArchiveHandler.getCompressionLevel()],
				progress: { progress in
					guard gate.admit(progress) else { return }
					Task { @MainActor in
						self.viewModel.packageProgress = progress
					}
				})

			return self._archive
		}.value
	}
	
	func moveToArchive(_ package: URL, shouldOpen: Bool = false) async throws -> URL? {
		let base = Self.exportStem(name: _appName, version: _appVersion)
		try _fileManager.createDirectoryIfNeeded(at: _fileManager.archives)
		var number = 1
		while true {
			let suffix = number == 1 ? "" : " (\(number))"
			let dest = _fileManager.archives.appendingPathComponent("\(base)\(suffix).ipa")
			do {
				// moveItem refuses an existing destination; retry only that error, never overwrite.
				try _fileManager.moveItem(at: package, to: dest)
			} catch let error as NSError where error.domain == NSCocoaErrorDomain && error.code == NSFileWriteFileExistsError {
				number += 1
				continue
			}
			if shouldOpen {
				await MainActor.run {
					if let url = FileManager.default.archives.toSharedDocumentsURL() { UIApplication.open(url) }
				}
			}
			return dest
		}
	}

	/// One bounded filename component for both local and web IPA exports.
	static func exportStem(name: String?, version: String?) -> String {
		let parts = [name, version].compactMap { value -> String? in
			guard let value = value?.trimmingCharacters(in: .whitespacesAndNewlines), !value.isEmpty else { return nil }
			return value
		}
		let unsafe = CharacterSet.controlCharacters.union(CharacterSet(charactersIn: "/\\:*?\"<>|"))
		var stem = ""
		// Budget decomposed bytes too: filesystem normalization can expand characters.
		// Leave room for the collision suffix and extension; keep characters whole.
		for character in parts.joined(separator: " ") {
			let text = character.unicodeScalars.contains(where: unsafe.contains) ? "_" : String(character)
			guard (stem + text).decomposedStringWithCanonicalMapping.utf8.count <= 180 else { break }
			stem += text
		}
		stem = stem.trimmingCharacters(in: CharacterSet(charactersIn: ". "))
		return stem.isEmpty ? "App" : stem
	}

	static func getCompressionLevel() -> Int {
		UserDefaults.standard.integer(forKey: "Feather.compressionLevel")
	}
}

// MARK: - Coalescing
/// Zip reports once per entry and an app bundle holds thousands of them; hopping to the main
/// actor for every one of them stalls SwiftUI for the whole archive.
final class ProgressGate {
	private let _lock = NSLock()
	private var _last = -1.0
	private let _step: Double

	init(step: Double = 0.01) {
		self._step = step
	}

	func admit(_ value: Double) -> Bool {
		_lock.lock()
		defer { _lock.unlock() }
		guard value >= 1 || value - _last >= _step else { return false }
		_last = value
		return true
	}
}
