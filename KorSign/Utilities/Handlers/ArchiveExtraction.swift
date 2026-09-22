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
		try destination(for: path, resolvedRoot: directory.resolvingSymlinksInPath().standardizedFileURL)
	}

	private static func destination(for path: String, resolvedRoot root: URL) throws -> URL {
		try validatePath(path)
		let destination = root.appendingPathComponent(path).standardizedFileURL
		let resolved = destination.resolvingSymlinksInPath().standardizedFileURL
		guard resolved.path == root.path || resolved.path.hasPrefix(root.path + "/") else {
			throw CocoaError(.fileReadInvalidFileName)
		}
		return destination
	}

	static func unzip(_ source: URL, to directory: URL, bufferSize: Int = 16 * 1024, useZlib: Bool = false, profile: ((String) -> Void)? = nil, checkpoint: (() throws -> Void)? = nil, progress: ((Double) -> Void)? = nil) throws {
		let started = ProcessInfo.processInfo.systemUptime
		var entries = 0
		var completed = false
		defer {
			profile?("decoder=\(useZlib ? "zlib" : "apple") buffer=\(bufferSize) entries=\(entries) completed=\(completed) total=\(ProcessInfo.processInfo.systemUptime - started)")
		}
		try checkpoint?()
		let archive = try Archive(url: source, accessMode: .read)
		// The caller owns this working directory. Resolve its fixed root once,
		// and resolve every destination before writing to catch existing or new symlinks.
		let root = directory.resolvingSymlinksInPath().standardizedFileURL
		// Reject invalid names before writing any entry. Filesystem containment is
		// checked immediately before each write, when preceding entries may have
		// introduced symlinks; resolving destinations here would duplicate that work.
		var totalUnits: Int64 = 0
		for entry in archive {
			try checkpoint?()
			try validatePath(entry.path)
			guard entry.uncompressedSize <= UInt64(Int64.max), entry.compressedSize <= UInt64(Int64.max) else {
				throw Archive.ArchiveError.invalidEntrySize
			}
			let (total, overflow) = totalUnits.addingReportingOverflow(archive.totalUnitCountForReading(entry))
			guard !overflow else { throw Archive.ArchiveError.invalidEntrySize }
			totalUnits = total
		}

		let tracker = Progress(totalUnitCount: totalUnits)
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
			try checkpoint?()
			let target = try destination(for: entry.path, resolvedRoot: root)
			let entryProgress = Progress(totalUnitCount: archive.totalUnitCountForReading(entry))
			tracker.addChild(entryProgress, withPendingUnitCount: entryProgress.totalUnitCount)
			// Keep native symlink confinement, no-overwrite and attribute handling.
			let checksum = try archive.extract(entry, to: target, bufferSize: bufferSize, useZlib: useZlib, progress: entryProgress, checkpoint: checkpoint)
			guard checksum == entry.checksum else { throw Archive.ArchiveError.invalidCRC32 }
			entries += 1
		}
		completed = true
		progress?(1)
	}
}
