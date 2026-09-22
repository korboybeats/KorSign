// swift-tools-version:5.3
import PackageDescription

let package = Package(
    name: "ZIPFoundation",
    platforms: [.macOS(.v10_11), .iOS(.v9), .tvOS(.v9), .watchOS(.v2)],
    products: [.library(name: "ZIPFoundation", targets: ["ZIPFoundation"])],
    targets: [.target(name: "ZIPFoundation", resources: [.copy("Resources/PrivacyInfo.xcprivacy")])],
    swiftLanguageVersions: [.v5]
)
