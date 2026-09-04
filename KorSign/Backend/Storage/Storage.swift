//
//  Persistence.swift
//  KorSign
//
//  Created by samara on 10.04.2025.
//

import CoreData
import Foundation
import OSLog

// MARK: - Storage
final class Storage: ObservableObject {
	static let shared = Storage()
	let container: NSPersistentContainer
	@Published private(set) var isReady = false
	@Published private(set) var loadError: String?
	@Published var saveError: String?

	private let _name: String = "Feather"

	init(inMemory: Bool = false) {
		container = NSPersistentContainer(name: _name)

		if inMemory {
			container.persistentStoreDescriptions.first?.url =
				URL(fileURLWithPath: "/dev/null")
		}

		container.persistentStoreDescriptions.forEach { $0.shouldAddStoreAsynchronously = false }
		container.viewContext.automaticallyMergesChangesFromParent = true
		container.viewContext.mergePolicy = NSMergeByPropertyObjectTrumpMergePolicy
		retryLoad()
	}
	
	var context: NSManagedObjectContext {
		container.viewContext
	}
	
	/// Completes on the context queue before callers may retire source files.
	@discardableResult
	func saveContext() -> Result<Void, Error> {
		context.performAndWait {
			do {
				try requireReady()
				if context.hasChanges { try context.save() }
				return .success(())
			} catch {
				context.rollback()
				saveError = error.localizedDescription
				Logger.misc.error("CoreData save failed: \(error.localizedDescription)")
				return .failure(error)
			}
		}
	}

	func requireReady() throws {
		guard isReady else {
			throw NSError(domain: "KorSign.Storage", code: 1, userInfo: [
				NSLocalizedDescriptionKey: "The library could not be opened. Your files have been kept. Please retry opening the library."
			])
		}
	}
	
	func clearContext<T: NSManagedObject>(request: NSFetchRequest<T>) {
		let deleteRequest = NSBatchDeleteRequest(fetchRequest: (request as? NSFetchRequest<NSFetchRequestResult>)!)
		_ = try? context.execute(deleteRequest)
	}
	
	func countContent<T: NSManagedObject>(for type: T.Type) -> String {
		let request = T.fetchRequest()
		return "\((try? context.count(for: request)) ?? 0)"
	}

	func retryLoad() {
		guard !isReady else { return }
		loadError = nil
		if container.persistentStoreCoordinator.persistentStores.isEmpty {
			container.loadPersistentStores { _, error in
				self.loadError = error?.localizedDescription
			}
		}
		guard loadError == nil else { return }
		do {
			try context.performAndWait {
				try _migrateSortIndexIfNeeded()
				let request: NSFetchRequest<CertificatePair> = CertificatePair.fetchRequest()
				request.sortDescriptors = [NSSortDescriptor(keyPath: \CertificatePair.date, ascending: false)]
				CertificateSelection.migrate(ids: try context.fetch(request).map(\.uuid), defaults: UserDefaults.standard)
			}
			isReady = true
		} catch {
			context.rollback()
			loadError = error.localizedDescription
		}
	}

	// Backfills sortIndex from the old date-desc order so manual reordering starts stable
	private func _migrateSortIndexIfNeeded() throws {
		let key = "feather.sortIndexMigrated"
		guard !UserDefaults.standard.bool(forKey: key) else { return }

		let signedRequest: NSFetchRequest<Signed> = Signed.fetchRequest()
		signedRequest.sortDescriptors = [NSSortDescriptor(keyPath: \Signed.date, ascending: false)]
		do {
			let apps = try context.fetch(signedRequest)
			for (index, app) in apps.enumerated() { app.sortIndex = Int32(index) }
		}

		let importedRequest: NSFetchRequest<Imported> = Imported.fetchRequest()
		importedRequest.sortDescriptors = [NSSortDescriptor(keyPath: \Imported.date, ascending: false)]
		do {
			let apps = try context.fetch(importedRequest)
			for (index, app) in apps.enumerated() { app.sortIndex = Int32(index) }
		}

		if context.hasChanges { try context.save() }
		UserDefaults.standard.set(true, forKey: key)
	}
}
