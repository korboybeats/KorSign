"""Package staged Main, validate it, then atomically replace the destination."""
import argparse
import json
import plistlib
import subprocess
import tempfile
from pathlib import Path

from validate_ipa import validate


def package(stage, destination, deps):
    destination = destination.absolute()
    destination.parent.mkdir(parents=True, exist_ok=True)
    info = plistlib.loads((stage / 'Payload/KorSign.app/Info.plist').read_bytes())
    # Same filesystem as the destination: replacement exposes only the finished ZIP.
    with tempfile.TemporaryDirectory(prefix='.korsign-package-', dir=destination.parent) as directory:
        candidate = Path(directory) / destination.name
        subprocess.run(['zip', '-qr9', str(candidate), 'Payload'], cwd=stage, check=True)
        result = validate(candidate, deps, info['CFBundleVersion'])
        candidate.replace(destination)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--deps', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(package(args.stage, args.output, args.deps), indent=2))
