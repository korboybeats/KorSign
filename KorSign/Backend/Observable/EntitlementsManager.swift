//
//  EntitlementsManager.swift
//  KorSign
//
//  Library of reusable custom entitlements files. Persisted as a JSON manifest,
//  same layout as TweakManager, one plist per entry under Documents/Entitlements/<id>/.
//

import Foundation
import OSLog

// MARK: - Model

struct EntitlementsFile: Codable, Identifiable, Equatable {
	let id: UUID
	var name: String
	let createdAt: Date

	init(id: UUID = UUID(), name: String, createdAt: Date = Date()) {
		self.id = id
		self.name = name
		self.createdAt = createdAt
	}
}

// MARK: - Manager

final class EntitlementsManager: ObservableObject {
	static let shared = EntitlementsManager()

	@Published private(set) var files: [EntitlementsFile]

	private let _fm = FileManager.default
	private var _loadError: Error?
	private var _manifestURL: URL { _fm.entitlementsLibrary.appendingPathComponent("library.json") }

	private init() {
		self.files = []
		_load()
	}

	// MARK: Persistence

	private func _load() {
		do { files = try LibraryPersistence.load(EntitlementsFile.self, from: _manifestURL) }
		catch {
			_loadError = error
			LibraryPersistence.report(error, loading: true)
		}
	}

	private func _requireWritable() throws {
		if let error = _loadError { throw error }
	}

	@discardableResult
	private func _save(_ next: [EntitlementsFile]) -> Bool {
		do {
			try _requireWritable()
			try LibraryPersistence.save(next, to: _manifestURL)
			files = next
			return true
		} catch {
			LibraryPersistence.report(error, loading: _loadError != nil)
			return false
		}
	}

	// MARK: Disk layout

	func fileURL(for entry: EntitlementsFile) -> URL {
		_fm.entitlementsLibrary(entry.id.uuidString).appendingPathComponent("entitlements.plist")
	}

	func entry(for url: URL) -> EntitlementsFile? {
		files.first { fileURL(for: $0) == url }
	}

	// MARK: Content

	func load(_ entry: EntitlementsFile, reportFailure: Bool = true) -> [String: Any]? {
		do {
			let data = try Data(contentsOf: fileURL(for: entry))
			guard let dict = try PropertyListSerialization.propertyList(from: data, format: nil) as? [String: Any] else {
				throw CocoaError(.fileReadCorruptFile)
			}
			return dict
		} catch {
			if reportFailure { LibraryPersistence.report(error, loading: true) }
			return nil
		}
	}

	@discardableResult
	func save(_ entry: EntitlementsFile, dict: [String: Any]) -> Bool {
		do {
			try _requireWritable()
			guard files.contains(where: { $0.id == entry.id }), load(entry, reportFailure: false) != nil else {
				throw CocoaError(.fileReadCorruptFile)
			}
			try _write(dict, for: entry)
			return true
		} catch {
			LibraryPersistence.report(error, loading: _loadError != nil)
			return false
		}
	}

	// MARK: Mutations

	@discardableResult
	func addBlank(name: String) -> EntitlementsFile? { add(name: name, dict: [:]) }

	@discardableResult
	func add(name: String, dict: [String: Any]) -> EntitlementsFile? {
		let entry = EntitlementsFile(name: name)
		do {
			try _requireWritable()
			try _write(dict, for: entry)
			try LibraryPersistence.save([entry] + files, to: _manifestURL)
			files.insert(entry, at: 0)
			return entry
		} catch {
			try? _fm.removeItem(at: _fm.entitlementsLibrary(entry.id.uuidString))
			LibraryPersistence.report(error, loading: _loadError != nil)
			return nil
		}
	}

	/// Reads a picked file and stores its entitlements as a new library entry (never the source file itself).
	@discardableResult
	func addImported(name: String, from sourceURL: URL) -> EntitlementsFile? {
		guard let dict = EntitlementsManager.parseEntitlements(from: sourceURL) else { return nil }
		return add(name: name, dict: dict)
	}

	/// Reads entitlements from a plist/`.entitlements` file, any `.mobileprovision`, or a JSON export.
	static func parseEntitlements(from url: URL) -> [String: Any]? {
		let needsScope = url.startAccessingSecurityScopedResource()
		defer { if needsScope { url.stopAccessingSecurityScopedResource() } }

		if let dict = NSDictionary(contentsOf: url) as? [String: Any] {
			return dict
		}
		if url.pathExtension.lowercased() == "mobileprovision" {
			return CertificateReader(url).decoded?.Entitlements.map { $0.mapValues { $0.value } }
		}
		if let data = try? Data(contentsOf: url) {
			return try? JSONSerialization.jsonObject(with: data) as? [String: Any]
		}
		return nil
	}

	func rename(_ id: UUID, to name: String) {
		guard let index = files.firstIndex(where: { $0.id == id }) else { return }
		let trimmed = name.trimmingCharacters(in: .whitespacesAndNewlines)
		guard !trimmed.isEmpty else { return }
		var next = files
		next[index].name = trimmed
		_save(next)
	}

	@discardableResult
	func delete(_ id: UUID) -> Bool {
		guard files.contains(where: { $0.id == id }) else { return true }
		guard _save(files.filter { $0.id != id }) else { return false }
		try? _fm.removeItem(at: _fm.entitlementsLibrary(id.uuidString))
		return true
	}

	private func _write(_ dict: [String: Any], for entry: EntitlementsFile) throws {
		let data = try PropertyListSerialization.data(fromPropertyList: dict, format: .xml, options: 0)
		try _fm.createDirectoryIfNeeded(at: _fm.entitlementsLibrary(entry.id.uuidString))
		try data.write(to: fileURL(for: entry), options: .atomic)
	}
}
