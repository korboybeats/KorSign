//
//  Storage+Certificate.swift
//  KorSign
//
//  Created by samara on 16.04.2025.
//

import CoreData
import UIKit.UIImpactFeedbackGenerator
import Zsign

// MARK: - Class extension: certificate
extension Storage {
	func addCertificate(
		uuid: String,
		password: String? = nil,
		nickname: String? = nil,
		ppq: Bool = false,
		expiration: Date,
		isDefault: Bool = false,
		completion: @escaping (Error?) -> Void
	) {
		context.performAndWait {
			let generator = UIImpactFeedbackGenerator(style: .light)
		
			let new = CertificatePair(context: context)
			new.uuid = uuid
			new.date = Date()
			new.password = password
			new.ppQCheck = ppq
			new.expiration = expiration
			new.nickname = nickname
			new.isDefault = isDefault

			switch saveContext() {
			case .success:
				generator.impactOccurred()
				revokagedCertificate(for: new)
				completion(nil)
			case .failure(let error):
				completion(error)
			}
		}
	}
	
	func deleteCertificate(for cert: CertificatePair) {
		context.performAndWait {
			guard isReady else { return }
			let url = getUuidDirectory(for: cert)
			context.delete(cert)
			guard case .success = saveContext() else { return }
			if let url { try? FileManager.default.removeItem(at: url) }
		}
	}
	
	func getCertificate(uuid: String) -> CertificatePair? {
		guard !uuid.isEmpty else { return nil }
		return context.performAndWait {
			guard isReady else { return nil }
			let request: NSFetchRequest<CertificatePair> = CertificatePair.fetchRequest()
			request.predicate = NSPredicate(format: "uuid == %@", uuid)
			request.fetchLimit = 1
			return try? context.fetch(request).first
		}
	}
	
	func revokagedCertificate(for cert: CertificatePair) {
		guard !cert.revoked else { return }
		
		Zsign.checkRevokage(
			provisionPath: Storage.shared.getFile(.provision, from: cert)?.path ?? "",
			p12Path: Storage.shared.getFile(.certificate, from: cert)?.path ?? "",
			p12Password: cert.password ?? ""
		) { (status, _, _) in
			if status == 1 {
				DispatchQueue.main.async {
					cert.revoked = true
					self.saveContext()
				}
			}
		}
	}
	
	enum FileRequest: String {
		case certificate = "p12"
		case provision = "mobileprovision"
	}
	
	func getFile(_ type: FileRequest, from cert: CertificatePair) -> URL? {
		guard let url = getUuidDirectory(for: cert) else {
			return nil
		}
		
		return FileManager.default.getPath(in: url, for: type.rawValue)
	}
	
	func getProvisionFileDecoded(for cert: CertificatePair) -> Certificate? {
		guard let url = getFile(.provision, from: cert) else {
			return nil
		}
		
		let read = CertificateReader(url)
		return read.decoded
	}
	
	func getUuidDirectory(for cert: CertificatePair) -> URL? {
		guard let uuid = cert.uuid else {
			return nil
		}
		
		return FileManager.default.certificates(uuid)
	}
	
	func getAllCertificates() -> [CertificatePair] {
		let fetchRequest: NSFetchRequest<CertificatePair> = CertificatePair.fetchRequest()
		fetchRequest.sortDescriptors = [NSSortDescriptor(keyPath: \CertificatePair.date, ascending: false)]
		return (try? context.fetch(fetchRequest)) ?? []
	}
}
