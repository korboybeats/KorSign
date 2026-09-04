//
//  TweakManager.swift
//  KorSign
//
//  Library of reusable tweaks (.dylib/.deb/.framework/.bundle) with versions and
//  auto-inject rules. JSON manifests are committed before publishing changes
//  or retiring files; failed loads preserve the existing library for recovery.
//

import Foundation
import NimbleExtensions
import Zip
import OSLog

// MARK: - Models

final class TweakManager: ObservableObject {
	static let shared = TweakManager()

	@Published private(set) var tweaks: [ManagedTweak]
	@Published private(set) var folders: [TweakFolder]

	private let _fm = FileManager.default
	private var _loadError: Error?
	private var _manifestURL: URL { _fm.tweaksLibrary.appendingPathComponent("library.json") }
	private var _foldersURL: URL { _fm.tweaksLibrary.appendingPathComponent("folders.json") }

	private init() {
		self.tweaks = []
		self.folders = []
		_load()
	}

	// MARK: Persistence

	private func _load() {
		do {
			let loadedTweaks = try LibraryPersistence.load(ManagedTweak.self, from: _manifestURL)
			let loadedFolders = try LibraryPersistence.load(TweakFolder.self, from: _foldersURL)
			tweaks = loadedTweaks
			folders = loadedFolders
		} catch {
			_loadError = error
			LibraryPersistence.report(error, loading: true)
		}
	}

	private func _requireWritable() throws {
		if let error = _loadError { throw error }
	}

	@discardableResult
	private func _save(_ next: [ManagedTweak]) -> Bool {
		do {
			try _requireWritable()
			try LibraryPersistence.save(next, to: _manifestURL)
			tweaks = next
			return true
		} catch {
			LibraryPersistence.report(error, loading: _loadError != nil)
			return false
		}
	}

	@discardableResult
	private func _saveFolders(_ next: [TweakFolder]) -> Bool {
		do {
			try _requireWritable()
			try LibraryPersistence.save(next, to: _foldersURL)
			folders = next
			return true
		} catch {
			LibraryPersistence.report(error, loading: _loadError != nil)
			return false
		}
	}

	// MARK: Folders

	/// Tweaks in the given folder (`nil` = uncategorized).
	func tweaks(inFolder folderId: UUID?) -> [ManagedTweak] {
		tweaks.filter { $0.folderId == folderId }
	}

	func tweakCount(inFolder folderId: UUID?) -> Int {
		tweaks.reduce(0) { $0 + ($1.folderId == folderId ? 1 : 0) }
	}

	func folder(_ id: UUID?) -> TweakFolder? {
		guard let id else { return nil }
		return folders.first { $0.id == id }
	}

	@discardableResult
	func addFolder(name: String) -> TweakFolder? {
		let folder = TweakFolder(name: _uniqueFolderName(name))
		return _saveFolders(folders + [folder]) ? folder : nil
	}

	func renameFolder(_ id: UUID, to name: String) {
		guard let index = folders.firstIndex(where: { $0.id == id }) else { return }
		let trimmed = name.trimmingCharacters(in: .whitespacesAndNewlines)
		guard !trimmed.isEmpty else { return }
		var next = folders
		next[index].name = _uniqueFolderName(trimmed, excluding: id)
		_saveFolders(next)
	}

	/// Unique folder name among siblings, appending " 2", " 3"… on collision.
	private func _uniqueFolderName(_ desired: String, excluding id: UUID? = nil) -> String {
		var base = desired.trimmingCharacters(in: .whitespacesAndNewlines)
		if base.isEmpty { base = .localized("New Folder") }
		let taken = Set(folders.filter { $0.id != id }.map { $0.name.lowercased() })
		guard taken.contains(base.lowercased()) else { return base }
		var n = 2
		while taken.contains("\(base) \(n)".lowercased()) { n += 1 }
		return "\(base) \(n)"
	}

	/// Deletes a folder; its tweaks fall back to uncategorized (never deleted).
	@discardableResult
	func deleteFolder(_ id: UUID) -> Bool {
		var next = tweaks
		for index in next.indices where next[index].folderId == id { next[index].folderId = nil }
		// Two manifests: a saved uncategorization is safe even if removing the folder fails.
		if next != tweaks, !_save(next) { return false }
		return _saveFolders(folders.filter { $0.id != id })
	}

	/// Moves tweaks into a folder (`nil` = uncategorized).
	@discardableResult
	func moveTweaks(_ ids: Set<UUID>, toFolder folderId: UUID?) -> Bool {
		var next = tweaks
		for index in next.indices where ids.contains(next[index].id) { next[index].folderId = folderId }
		return next == tweaks || _save(next)
	}

	// MARK: Disk layout

	/// `Documents/Tweaks/<tweakID>/<versionID>/`
	func versionDirectory(forTweak tweakId: UUID, version: TweakVersion) -> URL {
		_fm.tweaksLibrary(tweakId.uuidString).appendingPathComponent(version.id.uuidString)
	}

	func fileURL(forTweak tweakId: UUID, version: TweakVersion, component: TweakComponent) -> URL {
		versionDirectory(forTweak: tweakId, version: version)
			.appendingPathComponent(component.fileName)
	}

	func fileURL(forTweak tweak: ManagedTweak, version: TweakVersion, component: TweakComponent) -> URL {
		fileURL(forTweak: tweak.id, version: version, component: component)
	}

	func fileURLs(forTweak tweakId: UUID, version: TweakVersion) -> [URL] {
		version.components.map { fileURL(forTweak: tweakId, version: version, component: $0) }
	}

	// MARK: Mutations

	@discardableResult
	func addTweak(name: String, from fileURL: URL, versionLabel: String = "1.0") -> ManagedTweak? {
		addTweak(name: name, fromFiles: [fileURL], versionLabel: versionLabel)
	}

	/// Imports several picked files as one tweak (a multi-file version).
	@discardableResult
	func addTweak(name: String, fromFiles fileURLs: [URL], versionLabel: String = "1.0") -> ManagedTweak? {
		guard let first = fileURLs.first else { return nil }
		let tweakId = UUID()
		let versionId = UUID()
		let stored = _storeComponents(fileURLs, forTweak: tweakId, versionId: versionId, existing: [])
		guard !stored.isEmpty else { return nil }

		let tweak = ManagedTweak(
			id: tweakId,
			name: name.isEmpty ? first.deletingPathExtension().lastPathComponent : name,
			versions: [TweakVersion(id: versionId, label: versionLabel, components: stored)],
			selectedVersionId: versionId
		)
		guard _save([tweak] + tweaks) else {
			try? _fm.removeItem(at: _fm.tweaksLibrary(tweakId.uuidString))
			return nil
		}
		return tweak
	}

	@discardableResult
	func addVersion(to tweakId: UUID, from fileURL: URL, label: String) -> TweakVersion? {
		addVersion(to: tweakId, fromFiles: [fileURL], label: label)
	}

	/// Adds another version (one or more files) to an existing tweak.
	@discardableResult
	func addVersion(to tweakId: UUID, fromFiles fileURLs: [URL], label: String) -> TweakVersion? {
		guard let index = tweaks.firstIndex(where: { $0.id == tweakId }) else { return nil }
		let versionId = UUID()
		let stored = _storeComponents(fileURLs, forTweak: tweakId, versionId: versionId, existing: [])
		guard !stored.isEmpty else { return nil }

		let version = TweakVersion(id: versionId, label: label, components: stored)
		var next = tweaks
		next[index].versions.append(version)
		next[index].selectedVersionId = versionId
		guard _save(next) else {
			try? _fm.removeItem(at: versionDirectory(forTweak: tweakId, version: version))
			return nil
		}
		return version
	}

	@discardableResult
	func addComponents(to tweakId: UUID, versionId: UUID, fromFiles fileURLs: [URL]) -> [TweakComponent] {
		guard
			let tIndex = tweaks.firstIndex(where: { $0.id == tweakId }),
			let vIndex = tweaks[tIndex].versions.firstIndex(where: { $0.id == versionId })
		else { return [] }

		let existing = tweaks[tIndex].versions[vIndex].components
		let stored = _storeComponents(fileURLs, forTweak: tweakId, versionId: versionId, existing: existing)
		guard !stored.isEmpty else { return [] }

		var next = tweaks
		next[tIndex].versions[vIndex].components.append(contentsOf: stored)
		guard _save(next) else {
			for component in stored {
				try? _fm.removeItem(at: fileURL(forTweak: tweakId, version: next[tIndex].versions[vIndex], component: component))
			}
			return []
		}
		return stored
	}

	/// Removes a component (and its file); removing the last one deletes the version.
	func deleteComponent(_ componentId: UUID, versionId: UUID, from tweakId: UUID) {
		guard
			let tIndex = tweaks.firstIndex(where: { $0.id == tweakId }),
			let vIndex = tweaks[tIndex].versions.firstIndex(where: { $0.id == versionId }),
			let component = tweaks[tIndex].versions[vIndex].components.first(where: { $0.id == componentId })
		else { return }
		let version = tweaks[tIndex].versions[vIndex]
		if version.components.count == 1 { deleteVersion(versionId, from: tweakId); return }
		var next = tweaks
		next[tIndex].versions[vIndex].components.removeAll { $0.id == componentId }
		guard _save(next) else { return }
		try? _fm.removeItem(at: fileURL(forTweak: tweakId, version: version, component: component))
	}

	func mutateComponent(_ componentId: UUID, versionId: UUID, in tweakId: UUID, _ change: (inout TweakComponent) -> Void) {
		guard
			let tIndex = tweaks.firstIndex(where: { $0.id == tweakId }),
			let vIndex = tweaks[tIndex].versions.firstIndex(where: { $0.id == versionId }),
			let cIndex = tweaks[tIndex].versions[vIndex].components.firstIndex(where: { $0.id == componentId })
		else { return }
		var next = tweaks
		change(&next[tIndex].versions[vIndex].components[cIndex])
		_save(next)
	}

	@discardableResult
	func deleteTweak(_ id: UUID) -> Bool { deleteTweaks([id]) }

	/// Commit one batched update before deleting files or changing the visible list.
	@discardableResult
	func deleteTweaks(_ ids: Set<UUID>) -> Bool {
		let removed = tweaks.filter { ids.contains($0.id) }
		guard !removed.isEmpty else { return true }
		guard _save(tweaks.filter { !ids.contains($0.id) }) else { return false }
		for tweak in removed { try? _fm.removeItem(at: _fm.tweaksLibrary(tweak.id.uuidString)) }
		return true
	}

	/// Adds only tweaks/folders whose id isn't already present; existing ones are untouched.
	@discardableResult
	func mergeFromBackup(tweaksDir: URL) throws -> Int {
		try _requireWritable()
		// Decode both before copying; a damaged backup cannot become a reduced library.
		let incoming = try LibraryPersistence.load(ManagedTweak.self, from: tweaksDir.appendingPathComponent("library.json"))
		let incomingFolders = try LibraryPersistence.load(TweakFolder.self, from: tweaksDir.appendingPathComponent("folders.json"))
		var nextFolders = folders
		for folder in incomingFolders where !nextFolders.contains(where: { $0.id == folder.id }) { nextFolders.append(folder) }
		try LibraryPersistence.save(nextFolders, to: _foldersURL)
		folders = nextFolders

		var next = tweaks
		var copied: [URL] = []
		do {
			for tweak in incoming where !next.contains(where: { $0.id == tweak.id }) {
				let source = tweaksDir.appendingPathComponent(tweak.id.uuidString)
				let destination = _fm.tweaksLibrary(tweak.id.uuidString)
				// An unregistered directory is not proof of a complete previous import.
				guard !_fm.fileExists(atPath: destination.path) else { throw CocoaError(.fileWriteFileExists) }
				copied.append(destination)
				try _fm.copyItem(at: source, to: destination)
				next.append(tweak)
			}
			try LibraryPersistence.save(next, to: _manifestURL)
		} catch {
			for url in copied { try? _fm.removeItem(at: url) }
			throw error
		}
		let added = next.count - tweaks.count
		tweaks = next
		return added
	}

	/// Explicit reset still commits metadata before retiring files. Unknown files are kept.
	func resetLibrary() {
		guard deleteTweaks(Set(tweaks.map(\.id))) else { return }
		_saveFolders([])
	}

	func deleteVersion(_ versionId: UUID, from tweakId: UUID) {
		guard let index = tweaks.firstIndex(where: { $0.id == tweakId }),
		      let version = tweaks[index].versions.first(where: { $0.id == versionId }) else { return }
		var next = tweaks
		next[index].versions.removeAll { $0.id == versionId }
		if next[index].selectedVersionId == versionId { next[index].selectedVersionId = next[index].versions.last?.id }
		guard _save(next) else { return }
		try? _fm.removeItem(at: versionDirectory(forTweak: tweakId, version: version))
	}

	func setSelectedVersion(_ versionId: UUID, for tweakId: UUID) {
		mutate(tweakId) { $0.selectedVersionId = versionId }
	}

	/// Replaces a tweak's metadata; versions are managed separately.
	func update(_ tweak: ManagedTweak) {
		mutate(tweak.id) { $0 = tweak }
	}

	func mutate(_ id: UUID, _ change: (inout ManagedTweak) -> Void) {
		guard let index = tweaks.firstIndex(where: { $0.id == id }) else { return }
		var next = tweaks
		change(&next[index])
		_save(next)
	}

	func tweak(_ id: UUID) -> ManagedTweak? {
		tweaks.first { $0.id == id }
	}

	// MARK: Queries

	var injectableTweaks: [ManagedTweak] {
		tweaks.filter { $0.isEnabled && $0.activeVersion != nil }
	}

	/// Tweaks that should auto-inject when signing the given bundle id.
	func resolveAutoInject(forBundleId bundleId: String?) -> [ManagedTweak] {
		injectableTweaks.filter { $0.autoInjects(into: bundleId) }
	}

	/// Tweaks set to inject into every sign (drives the tab badge).
	var defaultInjectCount: Int {
		injectableTweaks.filter { $0.injectByDefault }.count
	}

	/// Sign-time spec from a tweak's active version: one file per component with its
	/// effective config (component override else tweak default); "selected" targeting
	/// is constrained to the app's real extensions.
	func injectionSpec(for tweak: ManagedTweak, availableAppex: [String]) -> TweakInjectionSpec? {
		guard tweak.isEnabled, let version = tweak.activeVersion else { return nil }
		let files: [TweakInjectionFile] = version.components.map { component in
			var config = component.config ?? tweak.config
			if case .selected(let names) = config.targeting {
				config.targeting = .selected(names.filter { availableAppex.contains($0) })
			}
			return TweakInjectionFile(
				fileURL: fileURL(forTweak: tweak.id, version: version, component: component),
				fileName: component.fileName,
				fileType: component.fileType,
				enabled: component.isEnabled,
				config: config
			)
		}
		guard !files.isEmpty else { return nil }
		return TweakInjectionSpec(id: tweak.id, displayName: tweak.name, isManaged: true, files: files)
	}

	// MARK: Internal

	/// Copies source files into a version directory, returning components. File names
	/// are kept (importers derive the name from them); collisions are de-duped (`Name 2.dylib`).
	private func _storeComponents(
		_ sources: [URL],
		forTweak tweakId: UUID,
		versionId: UUID,
		existing: [TweakComponent]
	) -> [TweakComponent] {
		let destDir = _fm.tweaksLibrary(tweakId.uuidString).appendingPathComponent(versionId.uuidString)
		let createdDirectory = !_fm.fileExists(atPath: destDir.path)
		do {
			try _requireWritable()
			try _fm.createDirectoryIfNeeded(at: destDir)
		} catch {
			LibraryPersistence.report(error, loading: _loadError != nil)
			return []
		}

		var taken = Set(existing.map { $0.fileName.lowercased() })
		do { taken.formUnion(try _fm.contentsOfDirectory(atPath: destDir.path).map { $0.lowercased() }) }
		catch { LibraryPersistence.report(error); return [] }
		var result: [TweakComponent] = []

		for source in sources {
			let needsScope = source.startAccessingSecurityScopedResource()
			defer { if needsScope { source.stopAccessingSecurityScopedResource() } }

			let fileName = _uniqueFileName(source.lastPathComponent, taken: taken)
			let dest = destDir.appendingPathComponent(fileName)
			do {
				try _fm.copyItem(at: source, to: dest)
			} catch {
				try? _fm.removeItem(at: dest)
				for component in result { try? _fm.removeItem(at: destDir.appendingPathComponent(component.fileName)) }
				if createdDirectory { try? _fm.removeItem(at: destDir) }
				LibraryPersistence.report(error)
				return []
			}
			taken.insert(fileName.lowercased())
			result.append(TweakComponent(
				fileName: fileName,
				fileType: TweakFileType(fileExtension: source.pathExtension),
				// Handles files and directory bundles (.framework/.bundle/.appex).
				fileSize: TweakExtractor.directorySize(at: dest)
			))
		}

		if result.isEmpty, createdDirectory {
			try? _fm.removeFileIfNeeded(at: destDir)
		}
		return result
	}

	/// Appends " 2", " 3"… before the extension on collision (keeps the suffix intact).
	private func _uniqueFileName(_ desired: String, taken: Set<String>) -> String {
		guard taken.contains(desired.lowercased()) else { return desired }
		let url = URL(fileURLWithPath: desired)
		let ext = url.pathExtension
		let base = url.deletingPathExtension().lastPathComponent
		var n = 2
		while true {
			let candidate = ext.isEmpty ? "\(base) \(n)" : "\(base) \(n).\(ext)"
			if !taken.contains(candidate.lowercased()) { return candidate }
			n += 1
		}
	}

	// MARK: - Export

	/// Retain the export owner through sharing or saving; library files remain untouched.
	func exportableURL(for tweak: ManagedTweak, version: TweakVersion) -> TemporaryExport? {
		let sources = fileURLs(forTweak: tweak.id, version: version)
			.filter { _fm.fileExists(atPath: $0.path) }
		guard !sources.isEmpty else { return nil }

		do {
			let singleFile = sources.count == 1
				&& (try? sources[0].resourceValues(forKeys: [.isDirectoryKey]))?.isDirectory != true
			let safeName = tweak.name.replacingOccurrences(of: "/", with: "_")
			let name = singleFile ? sources[0].lastPathComponent : "\(safeName.isEmpty ? "Tweak" : safeName).zip"
			let export = try TemporaryExport(fileName: name)
			if singleFile {
				try _fm.copyItem(at: sources[0], to: export.url)
			} else {
				try Zip.zipFiles(paths: sources, zipFilePath: export.url, password: nil, progress: nil)
			}
			return export
		} catch {
			Logger.misc.error("TweakManager export failed: \(error.localizedDescription)")
			return nil
		}
	}

	/// Shareable URLs for a set of tweaks (each active version).
	func exportableURLs(forTweakIds ids: Set<UUID>) -> [TemporaryExport] {
		tweaks
			.filter { ids.contains($0.id) }
			.compactMap { tweak in
				guard let version = tweak.activeVersion else { return nil }
				return exportableURL(for: tweak, version: version)
			}
	}

	/// Zips a folder's active-version files into one archive.
	func exportFolder(_ folderId: UUID) -> TemporaryExport? {
		let items = tweaks(inFolder: folderId).flatMap { tweak -> [URL] in
			guard let version = tweak.activeVersion else { return [] }
			return fileURLs(forTweak: tweak.id, version: version).filter { _fm.fileExists(atPath: $0.path) }
		}
		guard !items.isEmpty else { return nil }

		let name = folder(folderId)?.name ?? "Tweaks"
		let safeName = name.replacingOccurrences(of: "/", with: "_")
		do {
			let export = try TemporaryExport(fileName: "\(safeName).zip")
			try Zip.zipFiles(paths: items, zipFilePath: export.url, password: nil, progress: nil)
			return export
		} catch {
			Logger.misc.error("TweakManager folder export failed: \(error.localizedDescription)")
			return nil
		}
	}
}
