# Contributing

KorSign is a modified fork of [RyukSign](https://github.com/faroukbmiled/RyukSign), which is derived from [Feather](https://github.com/claration/Feather). It is a sideloading app meant to run on stock iOS. To keep compatibility, we rely on stock features.

Any contributions should follow the [Code of Conduct](./CODE_OF_CONDUCT.md).

## Rules

- **No usage of any exploits of any kind.**
- **No contributions related to retrieving any signing certificates owned by companies.**
- **Modifying any hardcoded links should be discussed before changing.**
- **If you're planning on making a large contribution, please [make an issue](https://github.com/korboybeats/KorSign/issues) beforehand.**
- **Your contributions should be licensed appropriately.**
  - KorSign / RyukSign / Feather: GPLv3
  - AltSourceKit / NimbleKit / Zsign / IDeviceKitten: MIT
  - ElleKit: BSD-3-Clause
- **Typo contributions are okay**, just make sure they are appropriate.
  - This includes localizations.
- **Code cleaning contributions are okay.**

## Building from source

#### Requirements

- Xcode 26 with the iOS 26 SDK; local checks used Xcode 26.2. Current source
  references newer SDK types such as `BGContinuedProcessingTask`. Runtime
  availability guards do not make those declarations available to Xcode 16.
- Use the Swift compiler bundled with Xcode. Project targets currently select
  Swift 5 language mode; compiler version and language mode are different.
- Host deployment target: iOS 16.0. Widget configurations currently target iOS
  26.0. These runtime targets are separate from the SDK needed to compile.
- The release workflow selects Xcode 26.2, checks the SDK, and validates only Main
  before publication. Local archive checks passed; hosted compilation has not run.
  Packaging validates a temporary IPA before replacing the previous file. Dependency
  refresh now validates and atomically swaps complete TLS resource sets on macOS.
  Releases require a new version/tag and stop on lookup errors or existing tags.
  Failed publication needs deliberate review; the workflow never overwrites assets.
  See the [build/release review](docs/BUILD_RELEASE_REVIEW.md), O05.

1. Clone the repository with submodules:
    ```sh
    git clone https://github.com/korboybeats/KorSign --recursive
    ```
    - `Zsign` and `IDeviceKitten` are submodules — `--recursive` is required.

2. Fetch the local-server SSL pack (used by the on-device install server):
    ```sh
    cd KorSign && make deps
    ```

3. Open with Xcode:
    ```sh
    open KorSign.xcworkspace
    ```

#### Signing for development

The committed Xcode project carries the maintainer's signing identity. To build on your own machine, set your own team / enable automatic signing in Xcode's target settings, or use the unsigned CLI path (`make`, which builds with `CODE_SIGNING_ALLOWED=NO`).

#### Focused checks and build boundaries

Use [tests/README.md](tests/README.md) to select checks appropriate to a change.
The signing, storage, ownership and malformed-input fixtures use temporary files;
they do not require an app build. Existing checks and their limitations are
listed in [audit status](docs/AUDIT_STATUS.md).

The Vapor HTTP fixture requires cached dependencies and may fetch missing ones.
Do not use `make KorSign` merely to run a source-only audit: building creates a
real IPA, and some development workspaces automatically transfer changed IPAs.
Inspect unfamiliar scripts before running them. The legacy XCTest target still
has stale references and is not a substitute for the focused fixtures.

When a build is separately intended, validate the generated main IPA. If producing
Dev, derive it from that exact main build and validate both artifacts; Dev has no
separate scheme. Mac checks and successful builds do not establish iPhone
installation, cleanup, backgrounding, or accessibility behavior. Keep those
runtime checks explicit. Main-only public release policy remains unchanged.

#### Localizations

- Localizations live in `KorSign/Resources/Localizable.xcstrings` (a String Catalog). You need Xcode 15+ or another tool that can edit `.xcstrings`.
- **Do NOT edit the catalog by hand** — use Xcode's String Catalog editor.
- Some localizations were imported from upstream Feather / its V1; if they don't make sense, feel free to correct them.
- After localizing, please have another native speaker review your work. We want high-quality, in-context translations — they will not be merged otherwise (unless you were personally asked to translate).

#### Making a pull request

- Keep contributions in their own branch, not `main`.
- Don't be afraid of reviewers requesting changes — it keeps the project clean and tidy.

## Contributing to Zsign

KorSign pins `Zsign` to `df9370f482f7b9f77dab94bbcf80093c24a9c223` in
[korboybeats/Zsign-Package](https://github.com/korboybeats/Zsign-Package),
including OCSP validation, SwiftPM, safe Mach-O parsing, and mapping-lifecycle
fixes. Preserve this pin unless intentionally updating the dependency.

Zsign is maintained upstream at [claration/Zsign-Package](https://github.com/claration/Zsign-Package/tree/package). Make Zsign changes there.

## Upstream Projects

KorSign's direct upstream is [RyukSign](https://github.com/faroukbmiled/RyukSign), which is derived from [Feather](https://github.com/claration/Feather). Fixes that are not KorSign-specific may also be appropriate for the relevant upstream project.

## Remote updater

The app bundles its public HTTPS endpoint in
`KorSign/Resources/SelfUpdateConfig.plist`; it contains no credentials. See
[updater-server/README.md](updater-server/README.md) for deployment, request
limits, and checks. Publish the main IPA in the fork's matching version
release; keep Dev builds private unless explicitly requested. Never place certificates, passwords, tunnel tokens, or SSH keys in Git.

## Reliability validation

Consult [audit status](docs/AUDIT_STATUS.md) and the [focused checks](tests/README.md)
before changing import, signing, installation or storage ownership. Source-level
checks do not establish physical-iPhone behavior. Use the [device validation
checklist](docs/DEVICE_VALIDATION.md) for the latest audit-fix candidate.

The obsolete `KorSignTests` target and scheme have been retired. Run the focused
checks in [tests/README.md](tests/README.md); a successful app build is not a test run.

Release workflow dispatch defaults to `publish=false`: hosted compilation and IPA
validation run, with no release, asset upload or feed commit. `publish=true` creates
a new-version Main release and then directly calls the source-feed workflow. The
feed commit targets the default branch and remains subject to branch permissions.
Hosted execution of this revised workflow has not yet been validated.

### Current build workflow

KorSign is built on the maintainer's Mac. GitHub-hosted builds and automated
publication are optional and are not required for this workflow. The earlier
hosted validation run was cancelled. Retain local packaging/dependency checks;
do not treat unfinished hosted CI as a blocker for Mac-only development.
