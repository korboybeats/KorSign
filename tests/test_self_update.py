#!/usr/bin/env python3
"""Run the production release parser with main/Dev bundle identities on macOS."""
from pathlib import Path
import subprocess
import tempfile

source = Path('KorSign/Backend/Observable/SelfUpdateManager.swift').read_text()
parser = source[source.index('\tprivate static func parse('):source.index('\n\t// MARK: - Version compare')]
model = source[source.index('struct SelfUpdateRelease:'):source.index('\nenum SelfUpdatePhase:')]
model = model.replace('var isInstalled: Bool { SelfUpdateManager.compare(version, Bundle.main.version) == .orderedSame }', '')
assert 'private let _repo = "korboybeats/KorSign"' in source
assert '"KorSign.selfUpdateIgnored"' in source
program = '''import Foundation
struct Bundle {
    static var main = Bundle()
    var bundleIdentifier: String? = "com.korboy.korsign"
}
''' + model + '\nstruct Parser {\n' + parser.replace('private static func parse', 'static func parse') + '''
}
let main = "https://github.com/korboybeats/KorSign/releases/download/v3.0.1/KorSign.ipa"
let dev = "https://github.com/korboybeats/KorSign/releases/download/v3.0.1/KorSign-Dev.ipa"
var release: [String: Any] = ["id": 1, "tag_name": "v3.0.1", "assets": [
    ["name": "Other.ipa", "browser_download_url": "https://example.com/Other.ipa"],
    ["name": "KorSign-Dev.ipa", "browser_download_url": dev],
    ["name": "KorSign.ipa", "browser_download_url": main]
]]
assert(Parser.parse(release)?.downloadURL?.absoluteString == main)
Bundle.main.bundleIdentifier = "com.korboy.korsign.dev"
assert(Parser.parse(release)?.downloadURL?.absoluteString == dev)
release["assets"] = [["name": "KorSign.ipa", "browser_download_url": main]]
assert(Parser.parse(release)?.downloadURL == nil)
release["assets"] = []
assert(Parser.parse(release)?.downloadURL == nil)
assert(Parser.parse([:]) == nil)
print("Self-update release checks passed")
'''
with tempfile.TemporaryDirectory() as directory:
    swift = Path(directory) / 'main.swift'
    swift.write_text(program)
    subprocess.run(['swift', str(swift)], check=True)

# The published source feed must use the same exact asset match as the app.
import json
import os
import shutil
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    shutil.copyfile('update-repo.sh', root/'update-repo.sh')
    shutil.copyfile('app-repo.json', root/'app-repo.json')
    (root/'curl').write_text('#!/bin/sh\ncat release.json\n')
    (root/'curl').chmod(0o755)
    release = {'tag_name': 'v3.0.1', 'draft': False, 'published_at': '2026-09-08', 'assets': [
        {'name': 'KorSign-Dev.ipa', 'size': 10, 'browser_download_url': 'https://example.test/dev'},
        {'name': 'KorSign.ipa', 'size': 20, 'browser_download_url': 'https://example.test/main'}]}
    env = dict(os.environ, PATH=str(root)+os.pathsep+os.environ['PATH'])
    (root/'release.json').write_text(json.dumps(release))
    subprocess.run(['sh', 'update-repo.sh'], cwd=root, env=env, check=True)
    feed = (root/'app-repo.json').read_bytes()
    assert json.loads(feed)['apps'][0]['downloadURL'] == 'https://example.test/main'
    release['assets'].pop()
    (root/'release.json').write_text(json.dumps(release))
    result = subprocess.run(['sh', 'update-repo.sh'], cwd=root, env=env, capture_output=True)
    assert result.returncode != 0 and (root/'app-repo.json').read_bytes() == feed
print('Source-feed exact matching and missing-asset preservation passed')
