# KorSign

[![GitHub License](https://img.shields.io/github/license/korboybeats/KorSign?color=%23C96FAD)](https://github.com/korboybeats/KorSign/blob/main/LICENSE)

KorSign is an on-device app signer and installer for iOS. It is a modified fork of [RyukSign](https://github.com/faroukbmiled/RyukSign) by [Ryuk](https://github.com/faroukbmiled), which is derived from [Feather](https://github.com/claration/Feather) by [claration](https://github.com/claration).

> KorSign is independently maintained and is not affiliated with or endorsed by RyukSign or Feather. Upstream attribution is preserved in [Acknowledgements](#acknowledgements) and [Credits](#credits).

<p align="center"><picture><source media="(prefers-color-scheme: dark)" srcset="Images/Image-dark.png"><source media="(prefers-color-scheme: light)" srcset="Images/Image-light.png"><img alt="KorSign" src="Images/Image-light.png"></picture></p>

## Features

Inherited from Feather:

- User-friendly, clean UI.
- Sign and install applications using a `.p12` / `.mobileprovision` pair (via Zsign).
- Browse [AltStore](https://faq.altstore.io/distribute-your-apps/make-a-source#apps) repositories.
- View detailed information about apps and certificates.
- Configurable signing options (appearance, Files-app support, compatibility patching, Liquid Glass).
- No tracking or analytics.
- Open source and free.

Inherited from RyukSign:

- **Tweak Manager**: import, organize, and inject `.dylib`, `.deb`, `.framework`, `.bundle`, and `.appex` tweaks. Multi-file tweaks, per-file configuration, a file-info/dependency inspector, and ElleKit/CydiaSubstrate detection.
- **Enhanced download manager**: fast background downloads that keep running while you use other apps.
- **Live Activities & Dynamic Island**: watch download progress live from the Lock Screen and Dynamic Island, plus an in-app download overlay.
- **File Transfer server**: upload IPAs and tweaks over HTTP (drag-and-drop browser page) or WebDAV (mount in Finder / the Files app), with optional password protection.
- **App update checker**: flags installed apps that have a newer version available in your sources, with per-app ignore/skip.
- **Community repository collection** maintained by the RyukSign project, plus a fully configurable tab bar.

## KorSign improvements

- **Faster IPA imports:** 45% faster import time than RyukSign in a 1.7 GB IPA benchmark. Results vary by device and file.
- Pause, resume, or stop IPA imports during extraction.
- Tap Library **+** once to open your preferred import option. Hold to see all options.
- Optionally open the IPA picker automatically on launch or reopening.
- Optionally open the IPA picker automatically after installation.
- Optionally close the installation panel automatically after installation.
- Simplify exported IPA filenames to **App Name Version.ipa**.
- Customize haptic feedback for navigation, buttons, and alerts.
- Fix custom theme colors not matching the selected color.
- Access the Activity Logs **Share button** beside the three-dot menu.
- Fix import timeouts, download conflicts, signing errors, and installation cleanup.
- Improve protection against file loss, failed saves, and malformed imports.

## Signing and installation

KorSign uses Zsign to sign an IPA with your `.p12` certificate and `.mobileprovision` profile. You can then install the signed IPA using a local server or a pairing file.

### Server installation

- Use a locally hosted server for the IPA files used for installation (and assets such as icons).
  - On iOS 18, a few entitlements are needed: `Associated Domains`, `Custom Network Protocol`, `MDM Managed Associated Domains`, `Network Extensions`.
- Include valid HTTPS SSL certificates (we use [*.backloop.dev](https://backloop.dev/)).
- Then `itms-services://?action=download-manifest&url=<PLIST_URL>` initiates the install via `UIApplication.open`.

The alternative server method uses [plistserver](https://github.com/nekohaxx/plistserver) to host the installation manifest over HTTPS while the IPA stays on a local HTTP server. A Safari webview redirects to the `itms-services://` URL to start installation.

### Pairing installation

- Establish a heartbeat with a TCP provider, requiring a [pairing file](https://github.com/jkcoxson/idevice_pair) and a VPN.
- Connect to the socket routed to `10.7.0.1`, establish an `AFC` connection, create `/PublicStaging/`, upload the IPA, and install it directly. This works similarly to `ideviceinstaller`, but runs on the device.

This method requires a VPN and a pairing file created with a computer. Use server installation if you do not have a pairing file.

### Installation completion and cleanup

In the ordinary installation queue, the installation panel follows iOS progress
after the IPA transfer. Delete After Installing removes the signed Library copy only when installation is confirmed;
it does not uninstall the app from the device. Cleanup runs before the next IPA
picker opens. Failed or cancelled installations keep the signed copy.

If progress ends but iOS does not expose confirmation, the panel shows
**Finished — check Home Screen** and keeps the signed copy. Automatic dismissal
and next-import settings still apply. Batch jobs report this as unverified.

Auto Sign removes the unsigned input after successful signing. Delete After
Signing is therefore redundant while Auto Sign is enabled; Install After Signing
still applies. Temporary installation IPAs are separate from these library
copies and are cleaned when their last consumer finishes. Free Up Space clears
caches/logs and protects pending or untracked work.

For installation problems, clear **Settings > Activity Logs**, reproduce once,
and share the fresh log. Logs include transfer sizes, completion, and install
state evidence.

## KorSign updates

The main bundle ID is `com.korboy.korsign`.

KorSign keeps the RyukSign base version and numbers its own revisions separately:
**3.0.1 Revision 1** uses app version `3.0.1`, build `1`, and tag `v3.0.1-r1`.
Updates compare the base version first, then the revision. Older builds need a
one-time manual install to recognize this revision scheme. Download **KorSign.ipa**
from [Releases](https://github.com/korboybeats/KorSign/releases), then sign and install
it using the same signing identity to replace KorSign while preserving its data.

Settings > Updates and All Versions use releases from `korboybeats/KorSign`.
Only **KorSign.ipa** is published. Dev builds require a separate
`KorSign-Dev.ipa` release asset and cannot use the main IPA. Ignored updates apply
to the specific version and revision.

Server self-updates use KorSign's own HTTPS signing service. The selected
certificate, password, and provisioning profile are uploaded for that request;
temporary signing material is removed afterward. Signed downloads expire after
30 minutes. After Apple’s prompt closes, KorSign attempts to move to the Home
Screen automatically, without quitting or reopening itself. This also happens
after Cancel because iOS does not expose the selected button. If KorSign stays
open, go to the Home Screen manually. Wait for installation to finish before
reopening KorSign.

The backend signs only published KorSign main/Dev releases. Its source, limits,
and deployment instructions are in [updater-server/README.md](updater-server/README.md).
Oracle Always Free hosts signing; Cloudflare provides the public HTTPS address.
Workers VPC is free during its beta; future pricing and free-tier availability
can change.

## Building from source

Current source requires the iOS 26 SDK supplied with Xcode 26. The project uses synchronized groups, Swift Package Manager and git submodules. See [CONTRIBUTING.md](./CONTRIBUTING.md). In short:

```bash
git clone --recursive https://github.com/korboybeats/KorSign.git KorSign
cd KorSign
make deps          # fetches the backloop.dev SSL pack used by the local install server
open KorSign.xcworkspace
```

Set your own signing team and enable automatic signing in Xcode, or build an unsigned IPA with `make`.

## Contributing

Read the [contribution requirements](./CONTRIBUTING.md) for more information.

## Acknowledgements

- [Ryuk](https://github.com/faroukbmiled): author and maintainer of [RyukSign](https://github.com/faroukbmiled/RyukSign), the direct upstream project for KorSign.
- [claration](https://github.com/claration): author of [Feather](https://github.com/claration/Feather), the original project from which RyukSign is derived.
- [idevice](https://github.com/jkcoxson/idevice): backend used for communication with `installd`.
- [*.backloop.dev](https://backloop.dev/): localhost with a public-CA-signed SSL certificate.
- [Vapor](https://github.com/vapor/vapor): server-side Swift HTTP web framework.
- [Zsign](https://github.com/zhlynn/zsign): on-device signing, reimplemented for iOS.
- [ElleKit](https://github.com/tealbathingsuit/ellekit): tweak injection.
- [LiveContainer](https://github.com/LiveContainer/LiveContainer): fixes / help.
- [Nuke](https://github.com/kean/Nuke): image caching.
- [Asspp](https://github.com/Lakr233/Asspp): HTTP server setup reference.
- [plistserver](https://github.com/nekohaxx/plistserver): hosted on https://api.palera.in.

## License

This project is licensed under the **GPL-3.0** license: see [LICENSE](./LICENSE) for the full text. As a modified fork of RyukSign, itself derived from Feather, KorSign preserves that license. The complete corresponding source for KorSign releases is available in this repository: <https://github.com/korboybeats/KorSign>.

By contributing, you agree to license your code under GPL-3.0 (including agreeing to license exceptions), ensuring your work remains freely accessible and open.

## Disclaimer

KorSign is maintained here on GitHub. Any official KorSign releases will be distributed from this repository; downloads offered elsewhere are not endorsed by the project.

## Credits

- [Korboy](https://github.com/korboybeats): KorSign developer.
- [RyukSign](https://github.com/faroukbmiled/RyukSign): the direct upstream project KorSign is based on.
- [Feather](https://github.com/claration/Feather): the original upstream project RyukSign is based on.
