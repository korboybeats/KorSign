import Foundation
import ZIPFoundation

/// Archive writes are confined to caller-owned working directories.
enum ArchiveExtraction {
	static func validatePath(_ path: String) throws {
		let components = path.split(separator: "/")
		guard !path.isEmpty, !path.hasPrefix("/"), !path.contains("\\"),
			!path.contains("\0"), !components.contains(".."),
			components.first?.contains(":") != true else {
			throw CocoaError(.fileReadInvalidFileName)
		}
	}

	static func destination(for path: String, in directory: URL) throws -> URL {
		try validatePath(path)
		let root = directory.resolvingSymlinksInPath().standardizedFileURL
		let destination = root.appendingPathComponent(path).standardizedFileURL
		let resolved = destination.resolvingSymlinksInPath().standardizedFileURL
		guard resolved.path == root.path || resolved.path.hasPrefix(root.path + "/") else {
			throw CocoaError(.fileReadInvalidFileName)
		}
		return destination
	}

	static func unzip(_ source: URL, to directory: URL, progress: ((Double) -> Void)? = nil) throws {
		let archive = try Archive(url: source, accessMode: .read)
		// Reject invalid names before writing any entry. Recheck containment at each
		// write because preceding entries can introduce symbolic links.
		for entry in archive {
			_ = try destination(for: entry.path, in: directory)
		}

		let tracker = Progress(totalUnitCount: archive.reduce(0) { $0 + archive.totalUnitCountForReading($1) })
		var lastReported = 0.0
		let observation = progress.map { report in
			tracker.observe(\.fractionCompleted, options: [.new]) { tracker, _ in
				let fraction = tracker.fractionCompleted
				if fraction >= lastReported + 0.01, fraction < 1 {
					lastReported = fraction
					report(fraction)
				}
			}
		}
		defer { observation?.invalidate() }
		progress?(0)
		for entry in archive {
			let target = try destination(for: entry.path, in: directory)
			let entryProgress = Progress(totalUnitCount: archive.totalUnitCountForReading(entry))
			tracker.addChild(entryProgress, withPendingUnitCount: entryProgress.totalUnitCount)
			// Keep ZIPFoundation's symlink confinement and no-overwrite protections.
			let checksum = try archive.extract(entry, to: target, progress: entryProgress)
			guard checksum == entry.checksum else { throw Archive.ArchiveError.invalidCRC32 }
		}
		progress?(1)
	}
}
