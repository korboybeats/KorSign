//
//  InstallCleanup.swift
//  KorSign
//
//  Created by Ryuk
//

import Foundation

@MainActor
enum InstallCleanup {
	static let deleteKey = "Feather.deleteAppAfterInstall"
	static let clearCacheKey = "Feather.clearCacheAfterInstall"

	/// Only safe once the queue has retired
	static func run(for apps: [AppInfoPresentable]) {
		guard !apps.isEmpty else { return }
		let defaults = UserDefaults.standard

		if defaults.bool(forKey: deleteKey) {
			FileLogger.log("post-install cleanup deleting \(apps.count) Library app(s) after confirmed installation", category: "install")
			Storage.shared.deleteApps(apps)
		}

		if defaults.bool(forKey: clearCacheKey) {
			StorageManager.purgeCaches()
		}
	}
}
