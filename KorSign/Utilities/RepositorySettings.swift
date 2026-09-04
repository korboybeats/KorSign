//
//  RepositorySettings.swift
//  KorSign
//

import Foundation

enum RepositorySettings {
	/// Community repository collection maintained by the RyukSign project.
	static let communityListURL = URL(string: "https://raw.githubusercontent.com/faroukbmiled/Ryuk%53ign/refs/heads/main/repos.json")!

	private static let excludedSourcesKey = "KorSign.excludedSourceIdentifiers"

	/// Set of source identifiers excluded from "All Repositories".
	static var excludedSourceIdentifiers: Set<String> {
		get {
			let array = UserDefaults.standard.stringArray(forKey: excludedSourcesKey) ?? []
			return Set(array)
		}
		set {
			UserDefaults.standard.set(Array(newValue), forKey: excludedSourcesKey)
		}
	}

	static func isSourceExcluded(_ identifier: String) -> Bool {
		excludedSourceIdentifiers.contains(identifier)
	}

	static func setSourceExcluded(_ identifier: String, excluded: Bool) {
		var ids = excludedSourceIdentifiers
		if excluded {
			ids.insert(identifier)
		} else {
			ids.remove(identifier)
		}
		excludedSourceIdentifiers = ids
	}
}
