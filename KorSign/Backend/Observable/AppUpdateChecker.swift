//
//  AppUpdateChecker.swift
//  KorSign
//

import SwiftUI
import Combine
import AltSourceKit
import NimbleViews
import UIKit
import CoreData
import OSLog

// MARK: - Shared Update Checker
final class AppUpdateChecker: ObservableObject {
    static let shared = AppUpdateChecker()
    
    @Published private(set) var appsWithUpdates: Set<String> = []
    @Published private(set) var updateCount: Int = 0
    
    private var updateCache: [String: Bool] = [:]
    private let cacheQueue = DispatchQueue(label: "com.feather.updatechecker", attributes: .concurrent)
    
    private init() {}
    
    func checkForUpdates(
        app: ASRepository.App,
        signedApps: FetchedResults<Signed>,
        importedApps: FetchedResults<Imported>
    ) -> Bool {
        let cacheKey = app.currentUniqueId
        // Cached only — never compute during scroll.
        return cacheQueue.sync(execute: { updateCache[cacheKey] }) ?? false
    }

    // FetchedResults and managed properties stay on the view context's main queue.
    private struct InstalledApp: Equatable, Sendable {
        let identifier: String?
        let originalIdentifier: String?
        let name: String?
        let version: String?
        let uuid: String?
    }

    @MainActor private var generation = 0

    @MainActor
    private func snapshot(
        signedApps: FetchedResults<Signed>,
        importedApps: FetchedResults<Imported>
    ) -> [InstalledApp] {
        func value(_ app: AppInfoPresentable) -> InstalledApp {
            InstalledApp(identifier: app.identifier, originalIdentifier: app.originalIdentifier,
                         name: app.name, version: app.version, uuid: app.uuid)
        }
        return signedApps.map { value($0) } + importedApps.map { value($0) }
    }

    @MainActor
    func precomputeAllUpdates(
        sources: [ASRepository],
        signedApps: FetchedResults<Signed>,
        importedApps: FetchedResults<Imported>
    ) async {
        generation += 1
        let request = generation
        while !Task.isCancelled {
            let installedApps = snapshot(signedApps: signedApps, importedApps: importedApps)
            let ignored = SkippedUpdatesManager.persisted
            let result = await Task.detached(priority: .userInitiated) {
                var cache: [String: Bool] = [:]
                var updates = Set<String>()
                var uniqueApps = Set<String>()
                for source in sources {
                    for app in source.apps {
                        let installed = self.findInstalledApp(for: app, installedApps: installedApps)
                        let hasUpdate = self.hasUpdate(installedVersion: installed?.version,
                                                       sourceVersion: app.currentVersion)
                            && !ignored.contains(app.id ?? "")
                        cache[app.currentUniqueId] = hasUpdate
                        if hasUpdate, let installed {
                            updates.insert(app.currentUniqueId)
                            uniqueApps.insert(installed.uuid)
                        }
                    }
                }
                return (cache, updates, uniqueApps.count)
            }.value

            guard request == generation, !Task.isCancelled else { return }
            // Recompute if the library changed during the background comparison.
            guard installedApps == snapshot(signedApps: signedApps, importedApps: importedApps),
                  ignored == SkippedUpdatesManager.persisted else { continue }
            cacheQueue.sync(flags: .barrier) { updateCache = result.0 }
            appsWithUpdates = result.1
            updateCount = result.2
            return
        }
    }

    @MainActor
    func clearCache() {
        generation += 1
        cacheQueue.sync(flags: .barrier) { updateCache.removeAll() }
    }
    
    @MainActor
    func findInstalledApp(
        for app: ASRepository.App,
        signedApps: FetchedResults<Signed>,
        importedApps: FetchedResults<Imported>
    ) -> (version: String?, uuid: String)? {
        findInstalledApp(for: app, installedApps: snapshot(signedApps: signedApps, importedApps: importedApps))
    }

    private func findInstalledApp(
        for app: ASRepository.App,
        installedApps: [InstalledApp]
    ) -> (version: String?, uuid: String)? {
        let appBundleId = app.id ?? ""
        let appNameLower = app.currentName.lowercased()
        
        guard !appBundleId.isEmpty || !appNameLower.isEmpty else { return nil }

        func identifiersMatch(_ sourceId: String, _ storedId: String?, _ originalId: String?) -> Bool {
            if let originalId = originalId, sourceId == originalId { return true }
            if let storedId = storedId, sourceId == storedId { return true }
            return false
        }
        
        var allMatchingVersions: [String] = []
        var matchingUUID: String = ""

        for s in installedApps {
            let identifierMatch = !appBundleId.isEmpty &&
                identifiersMatch(appBundleId, s.identifier, s.originalIdentifier)
            let nameMatch = (s.name ?? "").lowercased() == appNameLower
            
            if identifierMatch || nameMatch {
                if let version = s.version {
                    allMatchingVersions.append(version)
                }
                if matchingUUID.isEmpty {
                    matchingUUID = s.uuid ?? ""
                }
            }
        }
        
        guard !allMatchingVersions.isEmpty else { return nil }

        let highestVersion = allMatchingVersions.max { v1, v2 in
            return !isNewerVersion(v1, than: v2)
        }
        
        return (highestVersion, matchingUUID)
    }
    
    func hasUpdate(installedVersion: String?, sourceVersion: String?) -> Bool {
        guard let currentVersion = installedVersion,
              let newVersion = sourceVersion else { return false }
        
        return isNewerVersion(newVersion, than: currentVersion)
    }
    
    private func isNewerVersion(_ new: String, than old: String) -> Bool {
        let newComponents = new.split(separator: ".").compactMap { Int($0) }
        let oldComponents = old.split(separator: ".").compactMap { Int($0) }
        
        let maxCount = max(newComponents.count, oldComponents.count)
        
        for i in 0..<maxCount {
            let newValue = i < newComponents.count ? newComponents[i] : 0
            let oldValue = i < oldComponents.count ? oldComponents[i] : 0
            
            if newValue > oldValue {
                return true
            } else if newValue < oldValue {
                return false
            }
        }
        
        return false
    }
    
    @MainActor
    func refreshUpdateCount(
        sources: [ASRepository],
        signedApps: FetchedResults<Signed>,
        importedApps: FetchedResults<Imported>
    ) {
        Task {
            await performUpdateCheck(sources: sources, signedApps: signedApps, importedApps: importedApps)
        }
    }
    
    @MainActor
    private func performUpdateCheck(
        sources: [ASRepository],
        signedApps: FetchedResults<Signed>,
        importedApps: FetchedResults<Imported>
    ) async {
        var updatesSet = Set<String>()
        var uniqueApps = Set<String>()

        let ignored = SkippedUpdatesManager.shared.bundleIDs

        for source in sources {
            for app in source.apps {
                if checkForUpdates(
                    app: app,
                    signedApps: signedApps,
                    importedApps: importedApps
                ), !ignored.contains(app.id ?? "") {
                    updatesSet.insert(app.currentUniqueId)

                    if let installedApp = findInstalledApp(
                        for: app,
                        signedApps: signedApps,
                        importedApps: importedApps
                    ) {
                        uniqueApps.insert(installedApp.uuid)
                    }
                }
            }
        }
        
        self.appsWithUpdates = updatesSet
        self.updateCount = uniqueApps.count
    }
}
