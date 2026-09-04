import Foundation

/// Keep this owner, not just its URL, until the last archive reader has finished.
final class InstallationArchive: Sendable {
	let directory = FileManager.default.temporaryDirectory
		.appendingPathComponent("FeatherInstall_\(UUID().uuidString)", isDirectory: true)
	var url: URL { directory.appendingPathComponent("Archive.ipa") }

	deinit {
		let directory = directory
		// Large extracted bundles can take time to remove. Never block the UI on teardown.
		// Startup cleanup retries anything left by interruption or a removal failure.
		DispatchQueue.global(qos: .utility).async {
			try? FileManager.default.removeItem(at: directory)
		}
	}
}
