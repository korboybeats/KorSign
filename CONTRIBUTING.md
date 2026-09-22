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
  - AltSourceKit / NimbleKit / Zsign / IDeviceKitten / ZIPFoundation: MIT
  - ElleKit: BSD-3-Clause
- **Typo contributions are okay**, just make sure they are appropriate.
  - This includes localizations.
- **Code cleaning contributions are okay.**

## Building from source

#### Requirements

- Xcode 26 with the iOS 26 SDK. Current source
  references newer SDK types such as `BGContinuedProcessingTask`. Runtime
  availability guards do not make those declarations available to Xcode 16.
- Use the Swift compiler bundled with Xcode. Project targets currently select
  Swift 5 language mode; compiler version and language mode are different.
- Host deployment target: iOS 16.0. Widget configurations currently target iOS
  26.0. These runtime targets are separate from the SDK needed to compile.
- Maintainer releases are built locally on macOS. The optional GitHub workflow
  is not a required build or release check.
- Packaging validates a temporary IPA before replacing the previous file. TLS
  resource refresh validates and atomically swaps the complete resource set.

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
they do not require an app build. The test guide describes each fixture's scope
and limitations.

The Vapor HTTP fixture requires cached dependencies and may fetch missing ones.
The app scheme has no XCTest target; use the focused fixtures.

Validate the generated main IPA. If producing
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

## Release workflow

Build releases locally on macOS. Keep the three-part marketing version aligned
with the adopted RyukSign base. Use a positive integer build number shared by the
app and widget, increasing it for each KorSign revision. For example:

| Field | Revision 1 |
| --- | --- |
| App version | `3.0.1` |
| Build number | `1` |
| Git tag | `v3.0.1-r1` |
| Release title | `KorSign 3.0.1 Revision 1` |

Revision tags identify stable KorSign releases, not SemVer prereleases. The updater
compares the base version first, then the revision. Legacy builds without revision
support require a one-time manual install.

1. Update the app and widget version/build together and run the affected checks.
2. Build Main locally, derive Dev from that exact Main, and validate both IPAs.
3. Stage only Main as `upload/KorSign.ipa`. Create a draft with
   `tools/create_release.sh`, setting `VERSION`, `REVISION`, `GITHUB_REPOSITORY`,
   and `GITHUB_SHA` to the validated artifact's version, build, repository, and
   source commit. Set `DRAFT=true`, `NOTES_FILE` to reviewed release notes, and
   `RELEASE_TITLE` to the display title. Without `DRAFT=true`, the script publishes.
4. Confirm the signing service supports the release tag and review the draft.
   Publish only Main; keep Dev private.
5. Run `sh update-repo.sh` after publication. Review and commit the updated source
   feed, including its `version`, `buildVersion`, and exact Main download URL.

Keep published release tags and assets stable.

The optional GitHub workflow defaults to `publish=false`. It is not used for the
maintainer's local release process. Its publication path invokes the source-feed
workflow, which must be enabled for automatic feed updates; otherwise update the
feed locally. Do not assume a published release automatically updated the feed.
