#!/bin/zsh
set -eu
cd "${0:A:h:h}"
test_dir=$(mktemp -d)
trap 'rm -rf "$test_dir"' EXIT
swiftc KorSign/Backend/Observable/OTAInstallState.swift tests/ota_install_state.swift -o "$test_dir/ota-checks"
"$test_dir/ota-checks"
swiftc KorSign/Backend/Observable/OTAInstallState.swift KorSign/Backend/Observable/InstalledAppProbe.swift tests/installed_app_probe.swift -o "$test_dir/probe-checks"
"$test_dir/probe-checks"
