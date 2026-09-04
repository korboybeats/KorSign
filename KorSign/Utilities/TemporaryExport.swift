import Foundation

/// Retain this owner until the share sheet or response has finished reading its file.
final class TemporaryExport: Sendable {
	let directory: URL
	let url: URL

	init(fileName: String) throws {
		guard !fileName.isEmpty, fileName != ".", fileName != "..",
			(fileName as NSString).lastPathComponent == fileName else {
			throw CocoaError(.fileWriteInvalidFileName)
		}
		directory = FileManager.default.uniqueTemporaryDirectory("FeatherExport")
		url = directory.appendingPathComponent(fileName)
		do {
			try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
		} catch {
			try? FileManager.default.removeItem(at: directory)
			throw error
		}
	}

	deinit {
		let directory = directory
		DispatchQueue.global(qos: .utility).async {
			try? FileManager.default.removeItem(at: directory)
		}
	}
}
