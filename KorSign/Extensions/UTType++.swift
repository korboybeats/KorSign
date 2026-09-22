//
//  UTType+ipa.swift
//  KorSign
//
//  Created by samara on 11.04.2025.
//

import UniformTypeIdentifiers

extension UTType {
	// Resolved on every use: installing another app can change which type owns an extension,
	// and a cached result makes the document picker grey out matching files.
	static var dylib: UTType { .init(filenameExtension: "dylib")! }
	static var deb: UTType { .init(filenameExtension: "deb")! }
	static var ipa: UTType { .init(filenameExtension: "ipa")! }
	static var tipa: UTType { .init(filenameExtension: "tipa")! }
	static let appleIPA: UTType = .init(importedAs: "com.apple.itunes.ipa")
	static var entitlements: UTType { .init(filenameExtension: "entitlements", conformingTo: .data)! }
	static var p12: UTType { .init(filenameExtension: "p12", conformingTo: .data)! }
	static var mobileProvision: UTType { .init(filenameExtension: "mobileprovision", conformingTo: .data)! }
	static var ryukBackup: UTType { .init(filenameExtension: "ryukbackup", conformingTo: .data)! }
}
