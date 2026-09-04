//
//  CertificateExporter.swift
//  KorSign
//
//  Bundles a certificate's p12 + mobileprovision + password into one zip, for the
//  in-app share sheet and the Web Manager download. Call on the main actor (reads CoreData).
//

import Foundation
import Zip

enum CertificateExporter {
	static func makeZip(for cert: CertificatePair) -> TemporaryExport? {
		guard
			let p12 = Storage.shared.getFile(.certificate, from: cert),
			let provision = Storage.shared.getFile(.provision, from: cert)
		else { return nil }

		let name = cert.nickname ?? Storage.shared.getProvisionFileDecoded(for: cert)?.Name ?? "Certificate"
		let safe = (name as NSString).lastPathComponent.replacingOccurrences(of: "/", with: "_")
		let fm = FileManager.default

		do {
			let export = try TemporaryExport(fileName: "\(safe).zip")
			let dir = export.directory
			try fm.copyItem(at: p12, to: dir.appendingPathComponent("\(safe).p12"))
			try fm.copyItem(at: provision, to: dir.appendingPathComponent("\(safe).mobileprovision"))
			try Data((cert.password ?? "").utf8).write(to: dir.appendingPathComponent("password.txt"))
			try Zip.zipFiles(
				paths: [
					dir.appendingPathComponent("\(safe).p12"),
					dir.appendingPathComponent("\(safe).mobileprovision"),
					dir.appendingPathComponent("password.txt")
				],
				zipFilePath: export.url,
				password: nil,
				progress: nil
			)
			return export
		} catch {
			return nil
		}
	}
}
