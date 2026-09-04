import Foundation
import Darwin

/// Request-owned staging on the destination volume; never exposes a partial replacement.
final class UploadWorkspace: Sendable {
	static let prefix = ".korsign-upload-"
	let directory: URL
	let file: URL

	init(destination: URL) throws {
		let parent = destination.deletingLastPathComponent()
		let directory = parent.appendingPathComponent(Self.prefix + UUID().uuidString, isDirectory: true)
		try FileManager.default.createDirectory(at: parent, withIntermediateDirectories: true)
		try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: false)
		self.directory = directory
		self.file = directory.appendingPathComponent(destination.lastPathComponent)
	}

	deinit { try? FileManager.default.removeItem(at: directory) }

	/// Atomic within a volume. A failed rename leaves the existing destination intact.
	static func commit(_ source: URL, to destination: URL, overwrite: Bool = true) throws {
		let result = source.withUnsafeFileSystemRepresentation { sourcePath in
			destination.withUnsafeFileSystemRepresentation { destinationPath in
				renamex_np(sourcePath!, destinationPath!, overwrite ? 0 : UInt32(RENAME_EXCL))
			}
		}
		guard result == 0 else { throw NSError(domain: NSPOSIXErrorDomain, code: Int(errno)) }
	}
}
