//
//  Storage+Signed.swift
//  KorSign
//
//  Created by samara on 17.04.2025.
//

import CoreData
import UIKit.UIImpactFeedbackGenerator

// MARK: - Class extension: Signed Apps
extension Storage {
    func addSigned(
        uuid: String,
        source: URL? = nil,
        certificate: CertificatePair? = nil,

        appName: String? = nil,
        appIdentifier: String? = nil,
        originalAppIdentifier: String? = nil,
        appVersion: String? = nil,
        appIcon: String? = nil,
        appDescription: String? = nil,

        completion: @escaping (Result<Signed, Error>) -> Void
    ) {
        context.performAndWait {
            let generator = UIImpactFeedbackGenerator(style: .light)

            let new = Signed(context: context)

            new.uuid = uuid
            new.source = source
            new.date = Date()
            new.certificate = certificate
            new.sortIndex = nextSignedSortIndex()

            // Identifier before PPQ protection / modifications
            new.originalIdentifier = originalAppIdentifier ?? appIdentifier
            new.identifier = appIdentifier
            new.name = appName
            new.icon = appIcon
            new.version = appVersion
            new.appDescription = appDescription

            switch saveContext() {
            case .success:
                generator.impactOccurred()
                completion(.success(new))
            case .failure(let error):
                completion(.failure(error))
            }
        }
    }

    // Below the current lowest so new apps land at the top
    func nextSignedSortIndex() -> Int32 {
        let request: NSFetchRequest<Signed> = Signed.fetchRequest()
        request.sortDescriptors = [NSSortDescriptor(key: "sortIndex", ascending: true)]
        request.fetchLimit = 1

        let lowest = (try? context.fetch(request))?.first?.sortIndex ?? 1
        return lowest - 1
    }
}
