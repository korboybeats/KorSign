# Native installation prompt cancellation

Status: unresolved. The original bottom panel remains. Neither a timer-based
cancellation inference nor the proposed hide-and-reopen behavior is implemented.
The user requested further investigation rather than accepting that workaround.




## Audit-complete candidate (2026-09-09)

The latest candidate includes the subsequent reliability fixes without adding a new
native Cancel workaround. Do not repeat the rejected hide/reopen or cancellation
inference experiments. See [device validation](DEVICE_VALIDATION.md) for the new
checks and [audit status](AUDIT_STATUS.md) for exact artifact identity.

## Restoring ordinary Dev installation (2026-09-09)

The direct external-manifest request experiment is removed from application source,
including its native bridge and bridge-only fixture. Both Main and Dev use the
ordinary URL handoff again. The existing bottom panel, Share button, confirmation-
gated cleanup and passive Dev observer logging remain. This restoration addresses
the experiment's immediate request failure, not native Cancel-only dismissal.

The prompt lifecycle fixture now runs both Main and Dev variants and both server
modes, checking exactly one URL handoff plus close/retry/background/fallback paths.
Historical experimental source and artifacts remain in the local IPA checkpoint;
previous investigation entries describe past builds, not the restored implementation.
Only Dev is eligible for automatic sending. No additional Cancel experiment is
requested; next phone validation is one ordinary installation from updated Dev.

## Current phone result and Dev-only sending (2026-09-09)

The user explicitly stopped main IPA sending. The local sender hook now scans only
Dev; main hash history is retained unchanged. Existing WatchPaths may wake the hook
for either package, but only Dev is eligible for sending. No sender was executed,
no delivery state/log was inspected, and no transfer was requested for this change.
Continue building main first and deriving/validating Dev, but send only Dev until
explicitly instructed otherwise. This supersedes historical dual-send instructions.

`/Users/tgm/Downloads/ryuksign 5.log` confirms the direct request diagnostic ran twice
at 06:02:38 and 06:02:49 UTC (lines 55–62 and 118–125). Both completed immediately
with success=false, results=0, NSCocoaErrorDomain 4099. The server stopped on each
failure; neither attempt reached a manifest/payload request. This is not native
Cancel evidence. The exact reason for the service connection failure is not present
in the limited error log; do not assert a specific missing entitlement as proven.
No unchanged retry is warranted. The experiment is unsuitable as the active Dev
installation path on this phone; restore ordinary URL initiation before further
installation tests. Automatic Cancel-only dismissal remains unresolved.

## Latest phone log: diagnostic not exercised

`/Users/tgm/Downloads/ryuksign 4.log` (2026-09-09 05:58:22–05:58:38 UTC)
shows signing KorSign (Dev), then ordinary `itms-services` URL handoff (lines 8–51).
It contains no `install-request` diagnostic marker. The recorded attempt targets
KorSign Dev itself, not an existing test app from within the updated Dev application.
No payload GET or installation confirmation appears in this log. This does not test
the new request API or establish its access/cancellation result. The active host
identity is not logged, so do not assert which host/version produced the log.

Next phone action: finish installing the Dev update by accepting its installation,
then open KorSign (Dev), tap Install on an existing signed test app, Cancel that
prompt if shown, and share Activity Logs from Dev. No new signing or build is needed.

## Evidence collected

- Phone log `ryuksign 1.log`: observer registration was requested; no callback
  arrived after declining the prompt before the user closed the panel.
- Phone log `ryuksign 2.log`: the IPA was downloaded and installation reached
  the native final progress state; no observer callback arrived during the
  observation window. The existing progress probe confirmed installation.
- Phone log `ryuksign 3.log`, lines 42–63: observer count changed from 0 to 1,
  and service observation changed from false to true before opening the URL.
  No callback arrived before removal six seconds later. Count returned to 0.
  These values establish local registration evidence, not remote delivery.
- `tests/test_install_observer_dispatch.py`: the real Mac local LaunchServices
  dispatcher delivers synthetic cancel/install events to the production Swift
  listener. Removal prevents further delivery. It uses a fresh process-local
  observer and benign proxy fixtures, with no real install or daemon subscription.
  This rules out basic callback wiring on the Mac only. The first disposable
  experiment supplied strings instead of proxies and crashed that test process;
  the corrected fixture passes. This was not an application crash.

The observation windows are finite. Delayed delivery, daemon filtering, modern
platform restrictions and differences between cancelling a prompt and cancelling
an already-started install have not been resolved. No single explanation is
established by these logs.

## Additional paths examined

| Path | Evidence and disposition |
|---|---|
| URL-open completion | The existing bool callback acknowledges opening the URL. It does not contain an Install/Cancel result. [Apple API](https://developer.apple.com/documentation/uikit/uiapplication/open(_:options:completionhandler:)). |
| Manifest HTTP response | `ServerInstaller._configureRoutes` returns the manifest before the prompt decision. Its response and connection lifetime do not identify the button tapped. |
| Progress cancellation | `AppInstaller._startProgressPolling` logs evidence before its phase guard. The cancelled-prompt logs contain nil progress, so merely removing the guard would not solve these attempts. Previously retained progress must not be mistaken for a new attempt. |
| Local workspace observer | Callback signatures and local registration have been checked. Mac dispatch works. Jailed-iPhone delivery remains unproven; changing protocol declarations or subclassing without evidence is not a confirmed fix. |
| Legacy StoreServices request completion | `SSDownloadManifestRequest` declares completion/response blocks, and `SSRequestDelegate` declares failure/completion callbacks. This is a separate initiation API, not an observer of KorSign's existing URL request. Header declarations do not prove current availability, access, or cancellation semantics. No request was started and no prompt-suppression setting was used. [Request header](https://raw.githubusercontent.com/nst/iOS-Runtime-Headers/master/PrivateFrameworks/StoreServices.framework/SSDownloadManifestRequest.h), [delegate header](https://raw.githubusercontent.com/nst/iOS-Runtime-Headers/master/protocols/SSRequestDelegate.h). |
| Legacy download-manager observer | `SSDownloadManagerObserver` declares download state/list changes, not an explicit confirmation-prompt choice. No evidence establishes that a download exists when the user declines the prompt. [Observer header](https://raw.githubusercontent.com/nst/iOS-Runtime-Headers/master/protocols/SSDownloadManagerObserver.h). |
| MarketplaceKit | Present in the local SDK, but installation requires Apple's marketplace-installation entitlement. It is not a drop-in observer for the existing IPA/itms-services flow. No entitlement changes were made. [Apple requirement](https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.developer.marketplace.app-installation). |
| Foreground/no-download heuristic | Previously rejected because a slow accepted install can look identical. It must not terminate the server, advance the queue or authorize deletion. |

The legacy headers are historical evidence, not verified iOS 26 contracts.
Attempts to retrieve matching iOS 18 headers at guessed repository paths returned
404; this is not evidence that the classes are absent from iOS. Public SDK absence
likewise does not establish runtime absence of a private class.

## Modern request-specific completion candidate

Further investigation located `qingralf/iOS18-Runtime-Headers` and
`qingralf/iOS26-Runtime-Headers`. Unlike the earlier guessed paths, both repositories
actually contain the following AppStoreDaemon declarations:

- [`ASDExternalManifestRequest`](https://github.com/qingralf/iOS26-Runtime-Headers/blob/master/PrivateFrameworks/AppStoreDaemon.framework/ASDExternalManifestRequest.h)
  accepts options and exposes `startWithCompletionBlock:`.
- [`ASDExternalManifestRequestOptions`](https://github.com/qingralf/iOS26-Runtime-Headers/blob/master/PrivateFrameworks/AppStoreDaemon.framework/ASDExternalManifestRequestOptions.h)
  accepts a manifest URL. Its prompt-suppression option must not be used.
- [`ASDExternalManifestResponse`](https://github.com/qingralf/iOS26-Runtime-Headers/blob/master/PrivateFrameworks/AppStoreDaemon.framework/ASDExternalManifestResponse.h)
  carries results and inherits an error/success response contract from
  [`ASDRequestResponse`](https://github.com/qingralf/iOS26-Runtime-Headers/blob/master/PrivateFrameworks/AppStoreDaemon.framework/ASDRequestResponse.h).
- `ASDRequestBroker` submits requests over an XPC connection. This is a different
  initiation path, not a way to attach a completion block to the existing
  `UIApplication.open` handoff.

These repositories identify themselves as runtime-generated iOS headers, but do
not establish the exact user's OS build or access from a normally signed app.
The legacy `SSDownloadManifestRequest` declaration is also present in the iOS 18
collection, so the old repository's age alone was not a reason to dismiss it.

A read-only Mac runtime check loaded AppStoreDaemon and inspected method metadata,
without constructing or submitting an installation request. The class names exist,
but the local Mac runtime does not expose `startWithCompletionBlock:` on
`ASDExternalManifestRequest`, `initWithURL:` on its options, or
`_startWithErrorHandler:` on `ASDRequest` (including superclass lookup). Therefore
a Mac request test would not represent the iPhone interface.

## What would advance the investigation

The strongest remaining candidate is request-specific completion through
`ASDExternalManifestRequest`. The simulator verification below establishes its callback arguments for iOS 26.3.
Before invoking it on the phone, check available selectors and normal-app access
on the target iOS build. Then a bounded separate
Dev experiment would need to preserve the native prompt and distinguish Cancel,
accepted request, request failure and actual installation confirmation. Request
success must never become permission to delete the signed copy.

No direct request was started, no entitlement was added, no identity was spoofed,
and no prompt-suppression setting was used. Public log examples show request-broker
entitlement checks for other App Store requests; those are not proof of this
request type's precise requirements. Normal signed-app access remains unknown.
A denied request must be treated as a boundary, not bypassed. No new IPA was built
for this further research, and no repeat of the existing observer test is requested.

This is a concrete newer alternative, not a proven Cancel callback. No existing
evidence proves automatic Cancel-only dismissal impossible, and none yet establishes
that this request path will work. The presentation-only hide/reopen alternative
remains unapproved and unimplemented.

## Activity Logs Share button

`LogsHistoryView` now places the existing Share action in a trailing toolbar item
beside the ellipsis menu. It retains the native labelled button, icon-only visual,
empty-state disable behavior and existing file-sharing helper. Refresh/Clear remain
in the menu. It still shares the current log file; rotated-history export was not
changed. Release compilation verifies the toolbar code; device appearance and
share-sheet presentation remain to be observed.

## iOS 26.3 simulator binary verification

The installed iOS 26.3 simulator runtime (`iOS_23D8133`) contains standalone
AppStoreDaemon and appstored binaries. Read-only static inspection was performed;
no simulator was booted, request submitted, installation attempted or service patched.

The external-manifest completion wrapper invokes the client block with three
values: the response's success boolean, its results object and the error object.
Its parent completion path explicitly obtains the error from the response. The
corresponding inferred Objective-C contract is `void (^)(BOOL, NSArray *, NSError *)`;
nullability is not established. This resolves the earlier opaque-block question
for this simulator build, not an ABI guarantee for every device build. It also
shows why a single-response-object block would be incorrect.

`ASDEphemeralRequest.receiveResponse:` schedules completion on a global queue and
clears its stored completion handler. A future integration must marshal UI/state
updates to the main actor and ignore callbacks after that attempt has ended.
Request completion remains separate from successful IPA installation.

The simulator daemon's `RequestBroker.listener:shouldAcceptNewConnection:` has a
connection-denied path and returns false in the implementation examined. This
prevents treating a simulator request experiment as a useful normal-iPhone-access
control. It does not establish the phone daemon's entitlement policy. The exact
normal signed-app access requirement and prompt-Cancel result remain unresolved.

Reproducibility: binaries are below the installed runtime's
`RuntimeRoot/System/Library/PrivateFrameworks/AppStoreDaemon.framework`.

- Framework SHA-256: `3d0e33b96b3c79d4bbb334deff78d3f2b53252bb7ae5450990894baab6aa0287`.
- `Support/appstored` SHA-256: `cdab64aae107678c7643b4f7f45b94eee94026b2ee2505b4de1fdb2ce6b07b86`.
- Focused tools: `nm -nm` for framework symbols, `otool -tvV` for the callback
  wrapper and completion path, and `otool -ov` plus read-only Mach-O address
  mapping for the broker method. No binary edits or entitlement modifications.

The next distinct validation is a normally signed Dev request-access experiment
on the phone, preserving the native prompt and accepting any service rejection.
It must not run the old URL handoff concurrently, suppress prompts, or infer
installation from request success. The Dev-only experiment is now implemented; phone behavior remains unverified.


## Dev request-access experiment

Dev OTA initiation now uses the runtime-guarded external-manifest request bridge
instead of the URL handoff. Main retains the URL handoff. The original bottom
panel remains. Native prompts are explicitly enabled, with no new entitlements,
caller identity override or fallback request. Pairing/export paths are unchanged.

The three-argument callback logs only success, result count and error domain/code
(including one underlying error). Failed or unavailable requests end with a
diagnostic error and preserve the signed library copy. Success leaves the existing
installation probe running; it cannot authorize cleanup. No error code is yet
classified as user cancellation. Late callbacks cannot change a finished attempt.
The existing waiting deadline and manual close remain available.

`test_manifest_request.py` passes against the actual Objective-C bridge with local
fake API classes: prompt visibility, callback arguments, initialization and exception
failures. `test_install_prompt.py` passes both normal URL behavior and diagnostic
success/failure/late-callback cases. These checks establish integration logic, not
private API availability, access permission or native prompt behavior on the phone.

Phone sequence: update Dev, tap Install on an existing signed Library entry, tap
Cancel if a native prompt appears, or dismiss a diagnostic error if access is denied.
Share Activity Logs using its Share button. Do not repeat signing. Preserve the
signed entry; do not claim automatic cancellation detection until the log establishes
what the API actually returns.
