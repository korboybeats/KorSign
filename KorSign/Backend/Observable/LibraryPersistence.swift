import Foundation
import NimbleExtensions

/// Shared disk contract for the JSON-backed libraries. Model decoders retain legacy formats.
enum LibraryPersistence {
	static func load<T: Decodable>(_ type: T.Type, from url: URL) throws -> [T] {
		let data: Data
		do { data = try Data(contentsOf: url) }
		catch let error as CocoaError where error.code == .fileReadNoSuchFile { return [] }
		// Reject a damaged array instead of saving a silently reduced library over it.
		return try JSONDecoder().decode([T].self, from: data)
	}

	static func save<T: Encodable>(_ values: [T], to url: URL) throws {
		let encoder = JSONEncoder()
		encoder.outputFormatting = [.prettyPrinted]
		let data = try encoder.encode(values)
		try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
		try data.write(to: url, options: .atomic)
	}

	static func report(_ error: Error, loading: Bool = false) {
		let message = loading
			? String.localized("The library could not be loaded. Existing files were kept. Restore access or repair the file, then reopen KorSign.")
			: String.localized("The change could not be saved. Check available storage and try again.")
		Toast.error(message + "\n" + error.localizedDescription, duration: .sticky)
	}
}
