import Foundation

/// Empty general selection means no certificate; empty updater selection follows it.
enum CertificateSelection {
    static let selectedKey = "feather.selectedCertUUID"
    static let updaterKey = "Feather.selfUpdateCertUUID"

    // Run once after a successful store fetch, before imports can reorder the list.
    static func migrate(ids: [String?], defaults: UserDefaults) {
        if defaults.object(forKey: selectedKey) == nil {
            let index = defaults.integer(forKey: "feather.selectedCert")
            defaults.set(ids.indices.contains(index) ? ids[index] ?? "" : "", forKey: selectedKey)
        }
        if defaults.object(forKey: updaterKey) == nil {
            let index = (defaults.object(forKey: "Feather.selfUpdateCertIndex") as? Int) ?? -1
            // A missing explicit choice must not silently become "follow selected".
            let id = index < 0 ? "" : (ids.indices.contains(index) ? ids[index] ?? "missing" : "missing")
            defaults.set(id, forKey: updaterKey)
        }
    }
}
