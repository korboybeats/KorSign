# Focused regression checks

For scope, implementation status and remaining gaps, see
[audit implementation status](../docs/AUDIT_STATUS.md). Local checks use Xcode
26.2; individual standalone fixtures may need fewer SDK features than the app.

Run source-only checks from a macOS checkout with Xcode command-line tools:

```sh
python3 tests/test_self_update.py
zsh tests/test_ota_install.sh
```

Run `zsh tests/test_server_install_http.sh` separately only when its dependency
and loopback-server requirements are appropriate. It may fetch packages.

- `test_self_update.py` runs the production release parser with main and Dev
  bundle identities, including reversed asset order and missing matching assets.
- `test_ota_install.sh` compiles the production state tracker and progress probe.
  It checks deadlines, late callbacks, stale or missing progress, same-version
  replacements, and retained progress receiving a final install state after
  workspace lookup disappears. Failed, cancelled, placeholder, and unknown
  states cannot confirm success.
- `test_server_install_http.sh` runs production ServerInstaller routes through
  Vapor with platform services stubbed. It checks HEAD size and compression,
  full and ranged GET bytes, repeated manifests, and missing-file errors.

The HTTP check reuses the Vapor checkout from `make KorSign`. Set
`KORSIGN_VAPOR_PATH` to use another checkout. SwiftPM may fetch dependencies;
its build cache lives in the system temporary directory. The shell checks remove
their temporary source/output directories on exit; the HTTP dependency build
cache persists.

Recorded during the audit/fix work on 2026-09-08: signing failure, archive
extraction, backup IDs, native bounds, malformed input, download ownership,
storage cleanup, installation archive ownership, web upload preservation and
OTA/probe checks passed. Storage and source/self-update fixtures also passed in
the earlier audit sessions. The real Vapor integration was not rerun for the
latest ownership/upload changes. The subsequent device-test checkpoint at `46d6642`
passed a full Release build and main/Dev IPA validation; this did not rerun the
focused suites or establish device behavior. Exact artifacts are in [audit status](../docs/AUDIT_STATUS.md).

These checks run on the Mac. They do not prove jailed-iPhone API availability or
end-to-end OTA behavior. On a physical iPhone, check a new install and a
same-version reinstall, foreground/background return, and the combination of
Auto Sign, Install After Signing, Delete After Signing, Delete After Installing,
Dismiss After Installing, and Import Another IPA After Installing. For the ordinary
queue, confirm the app installs, the panel finishes, and the signed Library copy
is deleted before Files reopens. Batch cleanup remains open (F15); do not count
ordinary queue results as batch coverage. Failed or unverified installs must
retain the signed copy.

## Remote updater service

See [the service checks](../updater-server/README.md#checks) for multipart limits,
main/Dev routing, credential cleanup, expiry, and HTTP HEAD/GET/range coverage.
Disposable signing checks do not prove installation on an iPhone.

`python3 tests/test_self_update_handoff.py` exercises the production Server
handoff against simulated prompt, background, rejected-URL and cancellation
events. The user also confirmed the private suspension operation on a physical iPhone.

## Storage reliability

Run `python3 tests/test_storage.py` on macOS. It compiles the production storage
methods with the real app Core Data model, using temporary SQLite files and
isolated preferences. UIKit feedback and certificate revocation are stubbed.
The check covers damaged-store preservation and retry, failed signed/imported/
certificate/source saves, rollback before file deletion, persistence after
reopening, and background insertion/source lookup with Core Data concurrency
checking enabled. It also compiles AppUpdateChecker and FR.handleSource: dynamic
results wrap real managed rows, comparison gates allow a version change, overlapping
refresh and cancellation, and fake background fetch callbacks exercise failed save,
retry, duplicate and network-error results on main. Original identifiers, name fallback,
highest signed/imported version and ignored updates are checked. No network is used.
The results wrapper does not host a real SwiftUI FetchedResults view.
Expected Core Data error logs come from deliberately invalid fixtures.

These checks do not prove physical-iPhone recovery UI behavior. Failed store
opening preserves the existing database and files; it does not repair corruption.

## Signing failure propagation

Run `python3 tests/test_signing_failure.py` on macOS. It compiles the production
Zsign adapter and the final signing/commit section of SigningHandler with a
harmless native-signing stub. It checks failure before the callback, later
failure, success, ad-hoc signing, missing certificates, modify-only behavior,
and stdout cleanup. Failed signing must not move or register output. The test
uses temporary files only; it does not sign an IPA or prove device installation.

## Archive extraction boundaries

Run `python3 tests/test_archive_extraction.py` on macOS. It compiles the production
extractor and TAR/DEB integration against the already cached, pinned ZIPFoundation,
SWCompression, and BitByteData sources. Pass `--checkouts /path/to/checkouts` if
needed. Missing or modified dependencies fail the check; nothing is downloaded.

Disposable fixtures cover valid ZIP/IPA/TIPA, backup/tweak layouts, relative links,
TAR and compressed TAR, DEB names, path traversal, existing external links, file
collisions, CRC failures, progress, and input preservation. No IPA is signed or
distributed. These tests do not establish large-file performance or iPhone behavior.

## Backup certificate identifiers

Run `python3 tests/test_backup_restore.py` on macOS. It compiles the production
backup models and restore method with isolated storage/preferences stubs and
temporary certificate files. It checks that a bad ID anywhere in the manifest
prevents all restore writes, rejects duplicate UUIDs including case variants,
accepts legacy manifests, restores valid certificates, and preserves existing
certificates across UUID case variants. No real credentials or app data are used.

## Native binary patching

Run `python3 tests/test_macho_patching.py` on macOS with Xcode command-line tools.
It compiles the production Objective-C patchers with AddressSanitizer and
UndefinedBehaviorSanitizer, then exercises small disposable thin/universal Mach-O
fixtures. Checks cover truncated headers/tables/commands, invalid slice extents,
overlap, slice-local command bounds, no writes on validation failure, expected
SDK/ARM64e changes, both FAT byte orders, idempotence, and executable permissions.
A separate production-Swift-caller fixture verifies error propagation and the SDK
executable path. No real IPA, credentials, dependency updates, or network is used.
These checks do not prove installation or Liquid Glass behavior on an iPhone.

## Malformed DEB and app metadata

Run `python3 tests/test_malformed_inputs.py` on macOS. It compiles the production
AR parser, archive-name validator and signing plist guard. Temporary fixtures
cover truncated headers/payloads, invalid numeric/date fields, missing padding,
non-ASCII headers, empty/odd/even members, missing or malformed Info.plist,
non-dictionary plists, and valid XML/binary dictionaries. Inputs remain unchanged.
No application data, native signing, or device operation is involved.

## Download task and file ownership

Run `python3 tests/test_download_ownership.py` on macOS. It compiles the production
Download model, start/pause/resume/cancel/import-completion methods, and session
completion delegates with fake tasks/services and temporary files. It checks
registration before callbacks, duplicate starts/resumes, rapid pause/resume/cancel,
stale callbacks/references, retry without resume data, import ownership, matching
filenames, collision rejection, and cleanup without deleting local source files.
The fixture bypasses OS main-thread detection because Swift's async main executor
on macOS can use a different thread; it does not test real URLSession scheduling,
background transfer, process relaunch, or physical-iPhone behavior. No network.

## Safe general storage cleanup

Run `python3 tests/test_storage_cleanup.py` on macOS. It compiles production
cleanup categories, reports, scanner, protection checks, deletion guard and
startup cleanup, redirecting platform directories into one temporary fixture.
Cache/log services and Core Data are isolated stubs. It checks disposable cleanup,
working-file and pending-upload retention, stale unlocked rows, parent/descendant
and symlink protection, accurate reclaimable totals, and startup download retention.
Explicit registered-app deletion and full app reset are separate user actions.
No application data, builds, network or device operations are used.

## Installation archive ownership

Run `python3 tests/test_installation_archive.py` on macOS. It compiles the
production archive owner, ArchiveHandler, installation pipeline, and ServerInstaller
with fake zip, pairing and HTTP services. Optimized temporary fixtures check
producer handoff, packaging failure, delayed pairing reads, stopped packaging,
HEAD/GET reader retention, repeated stop, delayed shutdown, and export preservation
and errors. Repeated exports exercise filename collisions; existing files,
directories and links are preserved. Missing, unsafe and long Unicode metadata
(including decomposed Korean names) stays within the export directory and filename
budget. Non-collision move failure preserves prepared input. Main-actor assertions guard app metadata reads; the production installer
manifest runs through a fake HTTP worker and remote-manifest URL construction uses
a stubbed probe. No external endpoint is contacted. ZIP output is dummy data; no IPA
is built or installed. This checks
ownership, not Vapor transport or iPhone behavior. The separate HTTP integration
check is updated for the owner type but may fetch dependencies when run.

## Web upload preservation

Run `python3 tests/test_web_uploads.py` on macOS. It compiles the production
upload writer, staging workspace, PUT completion and MOVE/COPY handlers with
fake HTTP events and injected write/sync/close failures. File operations and
atomic replacement use the real filesystem in temporary fixtures. Checks cover
setup/copy/disconnect/write/sync/close/commit failures, late callbacks, zero-byte
then full PUT, same-name imports, overwrite refusal, and staging cleanup.
No server, network request, app build, or real IPA is involved. Actual browser,
Finder/Windows/WebDAV and iPhone behavior still require integration validation.

Completed browser uploads remain in the inbox while importers use independent
copies, matching mounted-drive retention. Import-copy failure leaves the previous
file intact. Replacing a nonempty directory fails safely rather than deleting
its previous contents; this check does not implement transactional tree merging.

## Tweak and entitlement persistence

Run `python3 tests/test_library_persistence.py` on macOS. It compiles the production
library helper, managers, models and web import router with temporary directories
and stubbed external services. Real filesystem failures check add/edit/delete,
component-copy rollback, source retention, restore failure, retry/reopen durability,
corrupt-array blocking and legacy single-file decoding. Unknown recovery files
survive failed component imports; partial ZIP imports retain their source archive.

Each manifest write is atomic; folder changes and whole backups are not a single
transaction. Earlier saved steps may remain after a later failure. Damaged manifests
require repair/reopen, and retrying a partly imported ZIP may duplicate successful
entries. No application data, network, IPA or device is involved. SwiftUI retry and
presentation behavior were source-parsed, not tested on an iPhone.

## iOS install-prompt lifecycle and cancellation diagnostics

Run `python3 tests/test_install_prompt.py` on macOS. It compiles production
AppInstaller prompt/status/finish logic with fake UIKit, HTTP and probes. Checks
cover background deferral, manifest retries, fixed waiting deadline, explicit
panel close, teardown, late callbacks, retry and rejected-open fallback.
Temporary preferences isolate settings; no network or IPA is involved.

`zsh tests/test_ota_install.sh` also exercises observer registration, callback
matching, privacy and idempotent removal against a process-local workspace fake.
Registration diagnostics also check scalar count/service-state reads before and
after add/remove, and safe handling of an unavailable remote observer. Counts
are aggregate evidence, not proof of callback delivery.
Neither fixture proves native notification delivery on a jailed iPhone.

The original bottom panel is retained. Temporary Dev-only workspace logging
records start/cancel/install/failure callbacks; it never drives dismissal,
success or deletion. Registration is requested before opening the install URL
and removed on finish/stop/deinitialization. No callback means no conclusion
unless a successful-install control establishes that notifications work.
The 120-second waiting deadline remains; focus changes and missing progress
are not cancellation evidence.

### Real Mac local observer dispatch

Run `python3 tests/test_install_observer_dispatch.py`. This separate check uses
macOS LaunchServices' real local dispatcher, a new process-local observer instance,
and benign proxy fixtures. Only the disposable process's workspace lookup is
replaced. It verifies delivery to production cancel/install callbacks and removal.
No IPA, real installation or daemon subscription is involved. This private API
check targets the current Mac runtime; unavailable APIs may require adapting the
fixture. A passing result does not establish jailed-iPhone notification delivery.


### Main and Dev URL handoff

`test_install_prompt.py` runs the prompt lifecycle cases for both host variants
and server modes. It verifies exactly one ordinary URL handoff, background deferral,
explicit close, late events, retry and rejected-open fallback. The failed direct
manifest request experiment and its bridge-only fixture have been removed; historical
results remain in `docs/CANCELLATION_INVESTIGATION.md`.

## Signing tweak staging lifetime

Run `python3 tests/test_tweak_staging.py` on macOS. It compiles the production
`TweakHandler.getInputFiles()` owner method with fake injection/decompression jobs
and real isolated file operations. It checks staging lifetime across a suspended
consumer and targeting, success, copy/job failure, handled managed failure and
cancellation. Original/unrelated files and placed output survive cleanup. Native
injection correctness and abrupt process termination are outside this fixture.

## Certificate and directory-share export lifetime

Run `python3 tests/test_temporary_exports.py` on macOS. It compiles the production
TemporaryExport owner, certificate/FileExporter producers, NimbleKit share helper
and Web Manager download helper against fake ZIP/UIKit/HTTP interfaces. Real isolated
files verify copied certificate/password/partial ZIP cleanup, sheet success/cancel/
missing presenter, retained/discarded HTTP responses and preservation of borrowed
plain files. The pinned Vapor stream implementation was inspected for callback
ownership, including early header-only/error returns. Real UIKit/HTTP lifetimes,
third-party share destinations and process termination are not reproduced here.

The same export fixture also checks the production Save to Files coordinator with
multiple owners, success/cancel teardown, preservation of a separately saved copy,
and the backup output-writing stage. It does not exercise backup encryption or real
file providers. `test_library_persistence.py` additionally checks real TweakManager
single/selection/folder/bundle/multiple-file export paths and cleanup after fake ZIP
failures, while confirming the stored library files remain unchanged.

## Shared import and web staging cleanup

Run `python3 tests/test_shared_import_cleanup.py`. It compiles the actual shared-IPA
and URL-certificate preparation/completion branches and decoder helper with delayed
fake importers, simulated coordination outcomes and real temporary files. It checks
failed preparation, absent accessor, import success/failure, invalid credentials,
failed writes and original preservation. The shared-tweak portion covers only its
changed preparation guard; later tweak import work is stubbed out.

`test_web_uploads.py` verifies independently allocated staging cleanup callbacks;
`test_library_persistence.py` checks that routing invokes them only after successful
IPA/tweak/full-ZIP import and preserves failed/partial inputs. Neither starts a real
server or invokes production certificate parsing, a file provider, or an iPhone.

## Stable certificate selection

`python3 tests/test_storage.py` also checks the production UUID migration and
lookup against isolated SQLite stores. It verifies that failed store loads leave
migration untouched, existing choices survive list changes/reopen, deleted choices
stay missing, and the actual Auto Sign/updater resolvers respect explicit versus
follow-selected choices. Backup policy rejects legacy indices. No real certificates,
signing, updater network requests or application settings are used. SwiftUI picker
and full backup/restore interaction still need device validation.

## Source-load ordering

Run `python3 tests/test_source_loading.py` on macOS. It compiles the production
SourcesViewModel with held callbacks and fake live source results/background tasks.
Both stale completion orders preserve the current load's results, loading flag,
completed-source key and background lifetime. It also checks stopped cancelled
batches, same-set coalescing, forced refresh, cancelled waiters, source changes while
waiting and empty lists. No network, Core Data store or application state is used.
Transport cancellation and physical foreground behavior are outside this check.

## Batch post-install cleanup

Run `python3 tests/test_batch_cleanup.py` on macOS. The production batch runner
and InstallCleanup run against manually completed installer callbacks and fake
signing/storage/cache services, with isolated defaults. Checks cover confirmed-only
cleanup after screen retirement, errors/unverified/skipped outcomes, stale callbacks,
cancellation races, repeated retirement, disabled/delete-only settings, sign-only,
and the identity of signed outputs. No real signing, IPA, network or application
data is involved. Physical SwiftUI dismissal and device installation remain separate.

## Updater flow ownership

`python3 tests/test_self_update_flow.py` runs the production flow and polling
methods with held results and accelerated sleeps. It checks stale completion/error
rejection, server outcomes remaining unverified, proxy completion, vanished/stalled
progress and cancellation. `python3 tests/test_self_update_download.py` checks the
production download helper/delegate with fake transport and isolated files: overlapping
attempts, stale progress, unique names and HTTP-error cleanup. The existing
`test_self_update_handoff.py` preserves simulated Home Screen handoff coverage.
These do not contact the updater, sign an IPA or prove physical self-update behavior.

## Web Manager configuration

Run `python3 tests/test_web_manager_settings.py` on macOS. Production manager
settings/lifecycle run with fake listeners and isolated defaults. Required credentials
and port validation must block invalid startup; active authentication/URLs reflect
the listener snapshot. Stop/edit/start, repeated start, failure and retry are covered.
No sockets, requests or application settings are used. Real browser/WebDAV login and
SwiftUI disabled controls require device/client validation.

## Audit-complete candidate check run (2026-09-09)

The latest candidate passed 13 focused scripts: installation_archive,
temporary_exports, shared_import_cleanup, library_persistence, web_uploads,
storage, source_loading, batch_cleanup, self_update, self_update_handoff,
self_update_flow, self_update_download and web_manager_settings (each prefixed
`test_` and suffixed `.py`). Release compilation and both IPA validations passed.
This is a focused regression run. The obsolete XCTest target was retired. See
[artifact status](../docs/AUDIT_STATUS.md) and [phone checks](../docs/DEVICE_VALIDATION.md).

## Log export naming and ownership

Run `python3 tests/test_log_export.py` for the production logger and temporary
export owner with synthetic, isolated logs. It checks KorSign.log naming,
queued-write snapshots, independent exports, preserved original logs, export
failure and owner cleanup. Web Manager's existing settings fixture also checks
the korsign default, migration from ryuk and preservation of custom usernames.

### Release archive gate

Run `python3 tests/test_release_ipa.py` on macOS with Xcode command-line tools.
It compiles one temporary object file and tests synthetic ZIPs against
`tools/validate_ipa.py`: valid Main, wrong bundle/build, missing or mismatched resources,
local-only files, invalid executable and invalid ZIP. It also checks exact release
asset selection and gate ordering. No IPA app build, network or delivery occurs.
The gate checks structure and identity; it does not prove device installability,
certificate validity, or source provenance beyond the embedded expected build.

Run `python3 tests/test_package_ipa.py` for packaging replacement checks. It uses
small temporary non-app ZIPs, injects ZIP/replacement failures, exercises real
validation rejection, and checks that success replaces the old file only after
validation. It also checks temporary cleanup. No real packages or app data are touched.

Run `python3 tests/test_server_deps.py` on macOS for offline dependency refresh
checks. Disposable certificates exercise real PEM/key validation and directory
exchange; download and exchange failures are injected. Existing files must survive
all failures. No production endpoint or real deps directory is used. This does not
verify public trust, expiry, hostname coverage or iPhone behavior.

Run `python3 tests/test_create_release.py` for new-version-only publication policy.
It executes the real shell script with fake git/gh commands: existing tags and
lookup failures must prevent creation; new versions use Main and the exact commit;
creation errors propagate without an update fallback. No GitHub access occurs.

### Retired XCTest target

KorSignTests and its scheme were removed on 2026-09-09. They depended on removed
Esign/Repository APIs, live external JSON, and test-local deobfuscation with no result
assertions. Use the focused checks documented here. `test_source_loading.py` verifies
current loading state with a stub parser; end-to-end AltSourceKit parsing is not
covered by that fixture. The Main scheme has no XCTest testables.

Run `ruby tests/test_release_workflow.rb` to check publication defaults, validation
ordering, the direct reusable feed-workflow dependency, default-branch selection
and embedded shell syntax. It parses local YAML; it does not execute GitHub Actions.
All six release-related checks passed together on 2026-09-09, including
`test_self_update.py` for actual feed-script fixture behavior.

Run `python3 tests/test_import_extraction_lifecycle.py` to check the actual import
extraction method with slow-success and failure stubs. The old five-minute deadline
is accelerated if reintroduced; it must not reject successful extraction. This
checks orchestration, not ZIP internals or physical-iPhone performance.
