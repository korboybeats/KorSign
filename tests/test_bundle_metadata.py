"""File metadata must ignore localized executable and icon names."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
source = (root / 'NimbleKit/Sources/NimbleExtensions/Bundle/Bundle+keys.swift').read_text()
fixture = r'''
let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
defer { try? FileManager.default.removeItem(at: directory) }
let app = directory.appendingPathComponent("Fixture.bundle")
try FileManager.default.createDirectory(at: app, withIntermediateDirectories: true)
let localized = app.appendingPathComponent("en.lproj")
try FileManager.default.createDirectory(at: localized, withIntermediateDirectories: true)
let info: [String: Any] = ["CFBundleIdentifier": "test.metadata.fixture", "CFBundleExecutable": "RealExecutable", "CFBundleIconFile": "RealIcon", "CFBundleDevelopmentRegion": "en", "CFBundleName": "Fixture"]
try PropertyListSerialization.data(fromPropertyList: info, format: .xml, options: 0).write(to: app.appendingPathComponent("Info.plist"))
try Data().write(to: app.appendingPathComponent("RealExecutable"))
try PropertyListSerialization.data(fromPropertyList: ["CFBundleExecutable": "TranslatedExecutable", "CFBundleIconFile": "TranslatedIcon"], format: .xml, options: 0).write(to: localized.appendingPathComponent("InfoPlist.strings"))
let bundle = Bundle(url: app)!
assert(bundle.object(forInfoDictionaryKey: "CFBundleExecutable") as? String == "TranslatedExecutable")
assert(bundle.exec == "RealExecutable")
assert(bundle.iconFileName == "RealIcon")
print("Bundle metadata localization checks passed")
'''
with tempfile.TemporaryDirectory(prefix='korsign-metadata-') as directory:
    script = Path(directory) / 'main.swift'
    script.write_text('import Foundation\n' + source + '\n' + fixture)
    subprocess.run(['swift', str(script)], check=True)
