#!/bin/zsh
set -eu
cd "${0:A:h:h}"
# Reuse the dependency checkout produced by make KorSign; add no app dependencies.
export KORSIGN_VAPOR_PATH="${KORSIGN_VAPOR_PATH:-${TMPDIR}KorSign/SourcePackages/checkouts/vapor}"
export KORSIGN_HTTP_TEST_DIR="$(mktemp -d)"
trap 'rm -rf "$KORSIGN_HTTP_TEST_DIR"' EXIT
python3 - <<'PY'
import json, os
from pathlib import Path
root = Path(os.environ['KORSIGN_HTTP_TEST_DIR'])
vapor = Path(os.environ['KORSIGN_VAPOR_PATH'])
assert (vapor / 'Package.swift').is_file(), 'Build KorSign first or set KORSIGN_VAPOR_PATH'
(root / 'Sources/HTTPChecks').mkdir(parents=True)
(root / 'Package.swift').write_text('''// swift-tools-version:5.7
import PackageDescription
let package = Package(name: "HTTPChecks", platforms: [.macOS(.v13)],
    dependencies: [.package(path: ''' + json.dumps(str(vapor)) + ''')],
    targets: [.executableTarget(name: "HTTPChecks", dependencies: [.product(name: "Vapor", package: "vapor")])])
''')
(root / 'Package.resolved').write_bytes(Path('KorSign.xcodeproj/project.xcworkspace/xcshareddata/swiftpm/Package.resolved').read_bytes())
(root / 'Sources/HTTPChecks/ServerInstaller.swift').write_text(Path('KorSign/Backend/Server/ServerInstaller.swift').read_text().replace('import IDeviceSwift\n', ''))
(root / 'Sources/HTTPChecks/InstallationArchive.swift').write_bytes(Path('KorSign/Utilities/Handlers/InstallationArchive.swift').read_bytes())
(root / 'Sources/HTTPChecks/Checks.swift').write_bytes(Path('tests/server_install_http.swift').read_bytes())
PY
swift run --package-path "$KORSIGN_HTTP_TEST_DIR" --scratch-path "${TMPDIR}korsign-http-regression-build" --skip-update HTTPChecks
