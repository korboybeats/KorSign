# KorSign

[![GitHub License](https://img.shields.io/github/license/korboybeats/KorSign?color=%23C96FAD)](https://github.com/korboybeats/KorSign/blob/main/LICENSE)

KorSign is an on-device app signer and installer for iOS. It is a modified fork of [RyukSign](https://github.com/faroukbmiled/RyukSign) by [Ryuk](https://github.com/faroukbmiled), which is derived from [Feather](https://github.com/claration/Feather) by [claration](https://github.com/claration).

> KorSign is independently maintained and is not affiliated with or endorsed by RyukSign or Feather. Upstream attribution is preserved in [Acknowledgements](#acknowledgements) and [Credits](#credits).

<p align="center"><picture><source media="(prefers-color-scheme: dark)" srcset="Images/Image-dark.png"><source media="(prefers-color-scheme: light)" srcset="Images/Image-light.png"><img alt="KorSign" src="Images/Image-light.png"></picture></p>

## Features

Inherited from Feather:

- User-friendly, clean UI.
- Sign and install applications using a `.p12` / `.mobileprovision` pair (via Zsign).
- Supports [AltStore](https://faq.altstore.io/distribute-your-apps/make-a-source#apps) repositories.
- View detailed information about apps and certificates.
- Configurable signing options (appearance, Files-app support, compatibility patching, Liquid Glass).
- No tracking or analytics.
- Open source and free.

Inherited from RyukSign:

- **Tweak Manager** — import, organize, and inject `.dylib`, `.deb`, `.framework`, `.bundle`, and `.appex` tweaks. Multi-file tweaks, per-file configuration, a file-info/dependency inspector, and ElleKit/CydiaSubstrate detection.
- **Live Activities & Dynamic Island** — watch download progress live from the Lock Screen and Dynamic Island, plus an in-app download overlay.
- **Enhanced download manager** — fast background downloads that keep running while you use other apps.
- **File Transfer server** — upload IPAs and tweaks over HTTP (drag-and-drop browser page) or WebDAV (mount in Finder / the Files app), with optional password protection.
- **App update checker** — flags installed apps that have a newer version available in your sources, with per-app ignore/skip.
- **Community repository collection** maintained by the RyukSign project, plus a fully configurable tab bar.

## KorSign improvements

- **Faster Library importing** — choose whether one tap on the `+` button opens the single-file picker, multi-file picker, or URL import; touch and hold for the other choices.
- **Automatic post-install workflow** — optionally close the install panel immediately when the final installation finishes tracking and automatically open the IPA picker for the next app.
- **Reliable Server installs** — preserves the correct IPA size for iOS checks and avoids treating a return to KorSign as cancellation.
- **Reliable background return** — fixes the empty or stuck install panel that could appear when signing finished while KorSign was backgrounded.
- **Background Server preparation** — Server-mode packaging, local-server startup, manifest creation, and validation can begin while KorSign is backgrounded; the iOS installation prompt still requires KorSign to be active.
- **Fixed custom theme colors** — custom colors now activate and save correctly.
- **Improved UI consistency** — aligns layouts and action buttons across the main tabs.
- **Safer certificate checks** — handles missing or malformed OCSP certificate-status responses safely.
- **Safer Library storage** — keeps your saved apps and certificates safe if the library fails to open or save.

## Current source reliability work

All 18 original audit findings are addressed in the current source, including
certificate selection, source-load ordering, batch cleanup, updater status and
Web Manager configuration. Focused Mac checks and Release compilation pass.
The refreshed 3.0.1 Main download includes the audit fixes and slow-import correction.
Ordinary import passed on the derived Dev build; some device edge cases remain unverified.

See [audit status](docs/AUDIT_STATUS.md) for evidence and remaining improvement
areas, and the [device checklist](docs/DEVICE_VALIDATION.md) for confirmation steps.
Native installation-prompt Cancel-only automatic dismissal remains unresolved.

## How does it work?

How Feather works is a bit complicated, with multiple ways to install, app management, tweaks, etc. The important pieces:

To start, we need a validly signed IPA, achieved with Zsign using a provided IPA plus a `.p12` and `.mobileprovision` pair.

#### Install (Server)

- Use a locally hosted server for the IPA files used for installation (and assets such as icons).
  - On iOS 18, a few entitlements are needed: `Associated Domains`, `Custom Network Protocol`, `MDM Managed Associated Domains`, `Network Extensions`.
- Include valid HTTPS SSL certificates (we use [*.backloop.dev](https://backloop.dev/)).
- Then `itms-services://?action=download-manifest&url=<PLIST_URL>` initiates the install via `UIApplication.open`.

Due to iOS 18 entitlement changes, an alternative is needed: either install fully locally via the local server (above), or use an external HTTPS server as a middle-man for `PLIST_URL` while keeping the files local — for the latter, a plain insecure local server plus [plistserver](https://github.com/nekohaxx/plistserver) for the `PLIST_URL`, and a Safari webview redirect to the `itms-services://` URL.

#### Install completion and cleanup

In the ordinary installation queue, the install panel follows iOS progress
after the IPA transfer. Delete After Installing removes the signed Library copy only when installation is confirmed;
it does not uninstall the app from the device. Cleanup runs before the next IPA
picker opens. Failed or cancelled installs keep the signed copy.

If progress ends but iOS does not expose confirmation, the panel shows
**Finished — check Home Screen** and keeps the signed copy. Automatic dismissal
and next-import settings still apply. Batch jobs report this as unverified.

Auto Sign removes the unsigned input after successful signing. Delete After
Signing is therefore redundant while Auto Sign is enabled; Install After Signing
still applies. Temporary installation IPAs are separate from these library
copies and are cleaned when their last consumer finishes. Free Up Space clears
caches/logs and protects pending or untracked work. Batch signed-copy cleanup
still has an open gap (F15 in the status index).

For installation problems, clear **Settings > Activity Logs**, reproduce once,
and share the fresh log. Logs include transfer sizes, completion, and install
state evidence.

#### Install (Pairing)

- Establish a heartbeat with a TCP provider, requiring a [pairing file](https://github.com/jkcoxson/idevice_pair) and a VPN.
- Connect to the socket routed to `10.7.0.1`, establish an `AFC` connection, create `/PublicStaging/`, upload the IPA, and install it directly — similar to `ideviceinstaller`, but fully on-device.

This path needs both a VPN and a lockdownd pairing file (so a computer for initial setup); otherwise use the server install method.

## KorSign updates

The main bundle ID is `com.korboy.korsign`.

Settings > Updates and All Versions use releases from `korboybeats/KorSign`.
Main builds select `KorSign.ipa`; Dev builds select `KorSign-Dev.ipa`. A missing
matching asset does not fall back to another app or build. Ignored versions are
specific to KorSign. All Versions shows an empty state until releases exist.
Only the main IPA is published. Dev cannot install an update without a matching
`KorSign-Dev.ipa` release asset; it does not fall back to the main app.
Server self-updates use KorSign's own HTTPS signing service. The selected
certificate, password, and provisioning profile are uploaded for that request;
temporary signing material is removed afterward. Signed downloads expire after
30 minutes. After Apple’s prompt closes, KorSign attempts to move to the Home
Screen automatically, without quitting or reopening itself. This also happens
after Cancel because iOS does not expose the selected button. If KorSign stays
open, go to the Home Screen manually. Wait for installation to finish before
reopening KorSign. Use the same signing
identity to replace the installed app and preserve its data.

The backend signs only published KorSign main/Dev releases. Its source, limits,
and deployment instructions are in [updater-server/README.md](updater-server/README.md).
Oracle Always Free hosts signing; Cloudflare provides the public HTTPS address.
Workers VPC is free during its beta; future pricing and free-tier availability
can change. Self-updating and the automatic Home Screen handoff were confirmed
on a physical iPhone. Reopen KorSign manually after installation finishes.

## Building from source

Current source requires the iOS 26 SDK supplied with Xcode 26; local checks used Xcode 26.2. The project uses synchronized groups, Swift Package Manager and git submodules. See [CONTRIBUTING.md](./CONTRIBUTING.md). In short:

```bash
git clone --recursive https://github.com/korboybeats/KorSign.git KorSign
cd KorSign
make deps          # fetches the backloop.dev SSL pack used by the local install server
open KorSign.xcworkspace
```

Signing identity is not committed in a usable form — set your own team / enable automatic signing in Xcode, or build the unsigned CLI path via `make`.

## Contributing

Read the [contribution requirements](./CONTRIBUTING.md) for more information.

## Acknowledgements

- [Ryuk](https://github.com/faroukbmiled) — author and maintainer of [RyukSign](https://github.com/faroukbmiled/RyukSign), the direct upstream project for KorSign.
- [claration](https://github.com/claration) — author of [Feather](https://github.com/claration/Feather), the original project from which RyukSign is derived.
- [idevice](https://github.com/jkcoxson/idevice) — backend used for communication with `installd`.
- [*.backloop.dev](https://backloop.dev/) — localhost with a public-CA-signed SSL certificate.
- [Vapor](https://github.com/vapor/vapor) — server-side Swift HTTP web framework.
- [Zsign](https://github.com/zhlynn/zsign) — on-device signing, reimplemented for iOS.
- [ElleKit](https://github.com/tealbathingsuit/ellekit) — tweak injection.
- [LiveContainer](https://github.com/LiveContainer/LiveContainer) — fixes / help.
- [Nuke](https://github.com/kean/Nuke) — image caching.
- [Asspp](https://github.com/Lakr233/Asspp) — HTTP server setup reference.
- [plistserver](https://github.com/nekohaxx/plistserver) — hosted on https://api.palera.in.

## License

This project is licensed under the **GPL-3.0** license — see [LICENSE](./LICENSE) for the full text. As a modified fork of RyukSign, itself derived from Feather, KorSign preserves that license. The complete corresponding source for KorSign releases is available in this repository: <https://github.com/korboybeats/KorSign>.

By contributing, you agree to license your code under GPL-3.0 (including agreeing to license exceptions), ensuring your work remains freely accessible and open.

## Disclaimer

KorSign is maintained here on GitHub. Any official KorSign releases will be distributed from this repository; downloads offered elsewhere are not endorsed by the project.

## Credits

- [Korboy](https://github.com/korboybeats) — KorSign developer.
- [RyukSign](https://github.com/faroukbmiled/RyukSign) — the direct upstream project KorSign is based on.
- [Feather](https://github.com/claration/Feather) — the original upstream project RyukSign is based on.
