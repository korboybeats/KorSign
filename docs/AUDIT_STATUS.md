# Audit implementation status

## Refreshed 3.0.1 source and Main release (2026-09-09)

Main preserves the original 81 RyukSign commits and one consolidated KorSign
commit, retaining the original KorSign author/commit timestamps. The existing
v3.0.1 release contains the validated Mac-built Main IPA.
App source matches the recorded import-deadline candidate; no rebuild was needed.
Main SHA-256: adf90c4b0f3808b92991294dc0596b37251ea96a9e1cd03b7ee8094799721f55
Main size: 22,324,098 bytes. Dev remains private. The source feed size matches Main.
Version 3.0.1 and the historical embedded build number are unchanged; this is an
intentional replacement, not a new version or a new claim of device validation.
Older commit references below describe pre-consolidation historical checkpoints.
Local rollback history and the previous release asset are retained privately.


## Current completion summary (2026-09-09)

All 18 original findings are addressed in source. The additional slow-import timeout
fix passed the Mac regression check and Release build; the user confirmed ordinary
import on the resulting Dev IPA. These fixes are ready for a source-repository update,
not a claim that every device edge case or optional improvement is complete.

Remaining work is explicitly separate: native Apple Cancel-only panel dismissal is
unresolved; device failure/cancellation/unverified-result cases are not exhaustively
confirmed; optional credential/privacy, accessibility and measured performance reviews
remain. True extraction interruption is not implemented. GitHub-hosted compilation is
not a requirement for the user's Mac-only workflow. See DEVICE_VALIDATION.md for the
confirmed phone checks; dated sections below preserve historical evidence.


## Latest local candidate: import deadline fix (2026-09-09)

Local Release build succeeded on this Mac; log /tmp/korsign-import-deadline-build.log.
Main was packaged first and Dev derived from that exact Main. Both passed ZIP integrity,
entry uniqueness/path checks, Main/Dev and widget identity, bundled-resource matching,
arm64 host/widget checks and source-manifest verification. Existing package copies
were preserved in the checkpoint's previous directory before replacement.

Checkpoint: .codex/ipa-checkpoints/korsign-import-deadline-wi5z9qp2/
Main SHA-256: adf90c4b0f3808b92991294dc0596b37251ea96a9e1cd03b7ee8094799721f55
Dev SHA-256: 659e21842ebfe0aae11bfc124d266026a68f0ea1b513589b4785b2716e31eaf0
Source manifest SHA-256: e6dbbd3b949463ad297198df66cd05751304558bd35caf6c94f750e1852b66f8
Source base: dbca9dd74b1be366e4ae62e1ccd83f31c424183b plus recorded import fix.
Version remains 3.0.1 with historical embedded build 2dbf78cc8947292c963bcef71fbde7ffad2180b4;
use the artifact hashes/source manifest to distinguish this candidate.

Validated files replaced packages outputs atomically. Dev was handed to the existing
automatic sender input; Main stays local. Delivery was not inspected or confirmed.
No GitHub build, push, release or Main send occurred during this local build.
The user subsequently confirmed installing the new Dev, importing a known-working
IPA, and seeing it in Library (2026-09-09). This records user-reported ordinary-import
success for the candidate above; transport was not independently monitored.
Do not repeat this passed check. The confirmation does not establish an extraction
over five minutes; that boundary remains covered by the accelerated local regression
check, not a timed physical-iPhone experiment.


## O01 import deadline corrected (2026-09-09)

AppFileHandler.extract() previously raced a synchronous extraction continuation
against a five-minute task-group timer. The group still waited for the extractor,
then threw the timeout even if extraction succeeded. FR.handlePackageFile consequently
cleaned the temporary result instead of moving/registering it. Original input ownership
is unchanged. Cleanup did not race active extraction; that existing protection remains.

Removed the ineffective timer/task group and retained the continuation that waits
for the real extraction result. Large successful imports no longer fail solely for
exceeding five minutes. Real errors still propagate before caller cleanup. This is
not a hard-hang or cancellation solution: the synchronous extractor must still return.
No iPhone occurrence or speed improvement is claimed.

The production-method fixture test_import_extraction_lifecycle.py passes slow success
and real-error propagation checks. With the previous method and an accelerated
historical deadline, the same check fails as expected. No archive exploits, production
files, app build, IPA transfer, hosted run or remote changes were involved.
Next: include this fix in the next requested local build; no new GitHub task is needed.


## Current direction: Mac-only builds (2026-09-09)

The user clarified that KorSign is built only on this Mac. GitHub-hosted compilation
and publication automation are not required next steps. Earlier recommendations to
run hosted CI are superseded. Do not dispatch another hosted build unless the user
explicitly changes this preference.

The previously authorized checkpoint was committed as
dbca9dd74b1be366e4ae62e1ccd83f31c424183b on ci/audit-release-validation and pushed
to origin. Hosted run 34330464333 is confirmed completed/cancelled. It is not a
successful hosted-build result. That run used publish=false; no release or phone
handoff was requested. The branch and checkpoint remain intact.

Keep the local packaging and TLS refresh protections, offline checks and other
audit fixes. Existing GitHub workflow files remain optional and manually triggered;
no rollback, branch deletion or further push is needed for Mac-only development.
Next work should address local build/application needs, not hosted CI completion.
No local app build or IPA transfer was performed while recording this correction.


Updated: 2026-09-09. Audit baseline: `e29834c`.
Current branch: `fix/install-prompt-waiting`; HEAD: `0331def`.
The working tree includes uncommitted audit fixes. The latest private candidate is
identified below. No audit-fix IPA has been publicly published.

This is the current status index. The original audit describes the baseline,
not the behavior of every subsequent revision. “Addressed” below means the
reported code path was changed and focused checks passed; it does not mean
release, full integration, or physical-iPhone validation is complete.



## O05 release integration checked locally (2026-09-09)

Found and fixed a workflow connection gap: releases created with GITHUB_TOKEN do
not trigger the existing release-event feed workflow. release.yml now directly
calls update_repo.yml after successful publication. The feed workflow remains
available for human-published releases, checks out the default branch, and serializes
feed writes. No token with broader permissions was introduced.

Manual release dispatch now defaults publish=false. This runs focused checks,
compiles and validates Main on the hosted runner, but skips release creation and
feed writes. Explicit publish=true is required for those actions. Focused checks
run before compilation. No hosted workflow was dispatched in this session.

All six local checks passed: release archive, package replacement, server dependency
refresh, release creation policy, workflow connections/shell syntax, and self-update
release parsing/feed generation. These use isolated fixtures/stubs; they do not prove
hosted compilation or publication. Default branch protection may still block the feed
commit; a feed failure after publication cannot roll back the published release.
No app build, production request, transfer, remote edit or publication occurred.
Next: prepare the reviewed changes for a check-only hosted run; pushing source and
running CI remain separate actions. O05 remains pending hosted validation.

## O05 obsolete XCTest target retired (2026-09-09)

Removed the registered KorSignTests target, its shared scheme, and its single source
file. The old tests imported removed Esign/Repository APIs, fetched a live external
source, and discarded deobfuscation results from test-local code. They were not
current parser coverage. Target ownership, scheme references, build inputs and
workflow references were checked before removal. Production uses AltSourceKit;
no production compatibility identifiers or dependency pins were changed.

The parsed project before/after comparison confirmed only 14 test-owned objects
and their registrations were removed; all remaining app/widget/project settings
were identical. Project plist syntax and remaining scheme XML passed. The existing
test_source_loading.py passed its offline loading/cancellation/cache checks. That
fixture stubs repository parsing and does not replace end-to-end AltSourceKit parser
coverage. No app build, test-host launch, transfer or publication occurred.

O05 source maintenance work is complete; hosted compilation and real release
integration remain unverified. Next: review the complete release workflow for
integration gaps before deciding on a non-publishing CI validation run.

## O05 new-version-only release policy implemented (2026-09-09)

Public release creation now runs tools/create_release.sh. It rejects an existing
remote tag and stops on tag lookup errors; only Git's explicit no-match status
allows creation. GitHub CLI creates a new release with exactly upload/KorSign.ipa
and the built GITHUB_SHA, instead of using a create-or-update action. There is no
asset overwrite or update fallback. Workflow concurrency serializes its release
runs without cancelling a running publication.

Offline stub checks passed for existing tags, lookup failure, new-version creation
arguments and creation failure propagation. Archive validation and shell/YAML syntax
checks passed. No GitHub repository request, workflow dispatch, build or publication
was performed. A failed upload may leave a draft requiring deliberate review; reruns
do not repair or overwrite it automatically. External/manual tag changes are outside
workflow concurrency protection. Use a new marketing version for the next release;
no version number was changed in this work.

Next: assess the stale XCTest target. Hosted CI and real publication remain untested.
O05 remains open for those checks; existing-release policy is now implemented.

## O05 safe server dependency refresh implemented (2026-09-09)

Makefile now downloads into private staging through tools/refresh_server_deps.py.
It requires HTTPS, bounds download time, checks required JSON strings/hostname syntax,
parses leaf and CA PEM separately, and verifies that the unencrypted key matches the
certificate. A failed download, parse, write or directory exchange stops the build
without replacing existing deps. Resource copying now fails instead of being ignored.
On macOS, renamex_np(RENAME_SWAP) atomically exchanges the complete staged directory
with existing deps; first creation uses rename. Unsupported exchanges fail closed.
Normal cleanup removes old/staged files. Forced termination may leave an ignored,
private .korsign-deps-* staging directory; the deps path remains an intact set.
Concurrent builds sharing build stages remain unsupported.

Offline generated-certificate tests passed: failed download, malformed JSON/PEM,
missing fields, mismatched keys, replacement failure, successful exchange and initial
creation. No production request, real deps change, app build, transfer or publication
was performed. Parsing/key matching do not prove certificate expiry, hostname coverage,
public trust, DNS reachability or physical-iPhone install success.
Next: resolve existing-release-tag policy and stale XCTest coverage; hosted CI remains
untested. O05 is still open, with the four original release review fixes implemented.

## O05 safe IPA replacement implemented (2026-09-09)

Makefile now calls tools/package_ipa.py to create Main in a unique temporary
subdirectory beside the destination, reuse the archive validator, and atomically
replace the final file only after validation succeeds. ZIP, validation and replacement
failures preserve the previous IPA. Normal exception paths remove temporary files;
forced process termination can leave a hidden staging directory, but not a partial
final IPA. This does not serialize concurrent builds sharing the existing build stage.
Local packaging checks compare the embedded build with staged metadata; CI separately
requires the current Git commit. Dependency refresh safety is still outstanding.

Tests: test_package_ipa.py passed isolated ZIP/validation/replacement failure and
success-order checks; test_release_ipa.py passed. Success ordering uses an accepted
fixture validator; archive validation is covered separately. No app build, actual
package replacement, transfer, publication or device test occurred.
Next: preserve existing server dependencies when refresh or validation fails.

## O05 release validation implemented (2026-09-09)

The release workflow now selects and checks Xcode 26.2 with an iOS 26+ SDK on
macos-15, runs a local validation regression check, validates the exact Main IPA,
and publishes only upload/KorSign.ipa. The tracked tools/validate_ipa.py checks ZIP
integrity, archive inventory, Main/widget identity, expected build, required resource
bytes, local-only file exclusion, and arm64 host/widget executables. Version metadata
comes from the validated archive. It prints an artifact hash; this is not proof of
runtime behavior, signing validity, TLS validity, or complete source provenance.

Synthetic checks and read-only validation of the existing latest Main IPA passed
(SHA-256 7b5719b34b30b73640020f5a71dd3466a59bbfffb5f7eb74758014dfabee18d1).
No app build, artifact replacement, transfer, hosted CI run or publication occurred.
O05 remains open: next fix Makefile artifact/dependency replacement, then resolve
legacy test coverage and existing-tag policy. Hosted runner compilation is untested.

## Historical O05 review, before release validation changes (2026-09-09)

Read docs/BUILD_RELEASE_REVIEW.md for evidence and smallest fixes. Public release
automation still selects Xcode 16.4 despite iOS 26 SDK types, publishes a wildcard
IPA set without the private validation gate, and relies on Makefile paths that
replace artifacts/dependencies before their replacements are validated. The legacy
XCTest target remains registered but stale. Feed script shell syntax and shared
scheme XML parsing passed; no build, transfer, CI dispatch or publication occurred.
O05 remains open; this review does not add new findings to the original 18 count.
Next: fix the release toolchain and exact Main validation gate, then safe replacement.


## Main updater test confirmed (2026-09-09)

The user explicitly accepted replacing Main with the older public build, followed
the Server updater/Reinstall/Home Screen instructions from the latest Main candidate,
and confirmed KorSign reopened normally. This is user-reported end-to-end evidence
for the latest Main updater's successful handoff/install path. It does not verify
unverified-result, timeout, cancellation or IDevice branches on the phone.

Main now runs the older public build used as the target. Latest Dev remains separate.
Do not repeat this successful test or describe Main as still containing the latest
audit fixes. Restoring latest Main or publishing a release is a separate action.
The user also reports full backup restore works; detailed restore coverage/build
identity was not independently established.

Current status: all 18 original findings addressed in source. Confirmed phone checks
are recorded in docs/DEVICE_VALIDATION.md (DEVICE_VALIDATION.md from docs).
Remaining device gaps include missing-certificate behavior and deterministic failure/
cancellation cases. Seven improvement areas remain separate; native Apple Cancel-only
panel dismissal remains unresolved. Next: review O05 build/release configuration
drift before any public release, without publishing or repeating passed phone tests.


## Corrected Main handoff (2026-09-09)

User reported Main was not received. Investigation showed the sender reads file paths
from command-line arguments; the earlier open -a invocation did not supply those
arguments. That earlier handoff was not a valid transfer submission. Main was
resubmitted using open -n with --args and the exact validated checkpoint IPA.
No post-handoff delivery monitoring occurred; receipt remains unconfirmed.
Automatic sending remains Dev-only. The public updater target is still the older
v3.0.1 artifact; do not instruct Reinstall as if it contains current fixes.


## Main updater-test preparation (2026-09-09)

The user explicitly requested Main KorSign.ipa for updater testing. Both simple-name
checkpoint IPAs were revalidated and the current source manifest still matches.
Main SHA-256: `7b5719b34b30b73640020f5a71dd3466a59bbfffb5f7eb74758014dfabee18d1`.
Main was handed once to Send to iPhone via macOS open. No delivery monitoring or
sender-state inspection occurred. The automatic sender remains Dev-only; no sender
configuration or public service was changed. Main delivery/installation is unconfirmed.

Read-only GitHub release metadata shows only v3.0.1 with public KorSign.ipa digest
`20fdbe23c34cc6ef9e5caad3a3e858ea694692952f6733fa7aaf1da8123929f9`,
updated 2026-09-08. It is not the latest local candidate. Do not direct the user to
tap Reinstall without explaining that it replaces current fixes with that older
artifact. Full latest-to-latest updater testing needs an explicitly authorized
suitable release target. None was published in this step.

User has additionally confirmed certificate selection after relaunch, browser
authentication prompt, wrong-password rejection, correct-password acceptance,
old-password rejection after change, reimporting an exported IPA, encrypted backup
save/open and wrong-backup-password rejection. User separately reports backup
restore works, and Main updater worked on an earlier build. The latest updater
changes remain physically unverified; these reports are not new-version updater proof.


## Latest simple-name Dev candidate (2026-09-09)

Release build passed. Main was packaged first; Dev was derived from that exact IPA.
Both passed archive, bundle/widget identity, resource and arm64 checks. Source inputs
were verified unchanged against the manifest; Zsign remains pinned. The focused
archive, log-export and Web Manager checks passed during implementation.

- Main, local only: `7b5719b34b30b73640020f5a71dd3466a59bbfffb5f7eb74758014dfabee18d1`
- Dev, automatic sender handoff: `5d13267c8c47f665a9b2e6c531b06af2825f5d25f0d595c2449cd8c5339c6c63`
- Source manifest: `75693e5741caf866bc6b10c314ddf8048e4d68c25cfca017f13556f861ac93e5`
- Checkpoint: `.codex/ipa-checkpoints/korsign-simple-names-75jtpmdy/`

Only Dev was placed in the watched path. No manual resend, sender inspection or
delivery monitoring occurred. Delivery and installation are unconfirmed.
This candidate includes simple App Version.ipa names with numbered duplicates,
KorSign.log export snapshots, and migration of the exact old username ryuk to
korsign while preserving custom usernames. Version/build metadata remain historical.

The previous candidate's user-confirmed checks are recorded in DEVICE_VALIDATION.md.
Next: install this Dev candidate and confirm the three naming/username changes.
Earlier source-only notes and artifact entries below are historical.


## Export and username branding (2026-09-09)

Activity Logs shares a snapshot named KorSign.log, created on the logger queue
after pending writes and retained through the share sheet by TemporaryExport.
The existing internal log/rotation paths remain unchanged so prior history is kept.
Failure reports an export error; share preparation runs off the main thread.

Web Manager defaults to korsign. At manager initialization, the exact old default
ryuk also becomes korsign and is persisted. Other usernames, including explicitly
empty values, are preserved. Passwords and authentication behavior are unchanged.
No running server credentials are changed by migration.

Focused log-export and Web Manager checks pass. Release build log:
`/tmp/korsign-export-branding-build.log`. This follow-up and the simplified IPA
filenames are source-only; no replacement IPA was packaged or sent.

## Export naming follow-up (2026-09-09)

At the user's request, local and web IPA exports use `App 1.0.ipa`, without dates.
Repeated local exports use `App 1.0 (2).ipa` and subsequent available numbers.
Existing names remain unchanged. The archive fixture passes. This source-only change
is newer than the candidate below and has not been packaged or sent.

## Latest audit-complete device candidate (2026-09-09)

All 18 original findings are addressed in source. The latest Release build and 13
focused checks passed. Main was packaged first and Dev derived from that exact IPA.
Both passed ZIP integrity, bundle/widget identity, resource and arm64 checks.
The source manifest covers KorSign, NimbleKit, IDeviceKitten, project/tweak inputs
and bundled dependency resources; Zsign remains pinned to
`df9370f482f7b9f77dab94bbcf80093c24a9c223`.

- Main (local only): `173eb71bfd478501c1c74b8079480592b4147ad1c22bfb489e2ffaf0c38bd584`
- Dev (automatic sender handoff): `05fc4a46972c3951522e10eb2515e432b4d261db995f4888a87efb1a4dcb529f`
- Source manifest: `3cc1a6e2532ce6dfcabb974acb4609f1fc960aa7baba02afc6cb4919c75b65cf`
- Local checkpoint: `.codex/ipa-checkpoints/korsign-audit-complete-41jxx6jr/`
- Version: 3.0.1. Embedded build identifier is historical; use these hashes and the
  Web Manager disabled-controls marker to identify this candidate.

Only Dev was placed in the automatic sender's watched path. No manual resend,
sender inspection or delivery monitoring occurred. Delivery and installation are
unconfirmed. Main remains in the local checkpoint; it was not handed off.

Use the [step-by-step device checklist](DEVICE_VALIDATION.md). Record each check as
passed, failed or not tested. Full updater replacement is deferred until a suitable
matching Dev release asset is deliberately selected; do not replace this candidate
with an older public release just to test. Native Apple Cancel-only panel dismissal
remains unresolved; the seven improvement areas remain separate.


## Latest validated restoration build (2026-09-09)

Normal URL installation is restored in Dev; the failed direct-request bridge is
removed. The original bottom panel and Activity Logs Share button remain. Native
Cancel-only automatic dismissal is still unresolved. Main/Dev prompt lifecycle
checks, Release compilation, both ZIP/identity/resource/arm64 validations and Dev
host/widget signature checks passed. The removed diagnostic strings are absent
from the executable. Existing build warnings remain; phone behavior is not yet
confirmed on this candidate.

Only Dev was placed in the watched package path for automatic handoff. Main was
built first and validated locally, then used to derive this exact Dev. The watched
main IPA was not replaced. No sender execution, delivery monitoring, manual resend,
dependency change, commit or publication occurred.

- `KorSign.ipa` (local build only): `1fbf27e8d16c15836c4c0e6845e0e83196cff29ba47c21fe61173cc7d630069e`
- `KorSign-Dev.ipa` (handed off): `b054e63290be42e8645d13483515c060048e45d9ed63c8f41303e46450df686f`

Source manifest: `4432bc2055ebf8431846f2a6a915e1b7dc7695d56eda4bf99729953a8ab90d69`. Source remains uncommitted
on `0331def`. Checkpoint: `.codex/ipa-checkpoints/korsign-restore-dev-install-s0lucfwz/`.
Source patch matches the previous Share build; embedded version is historical.


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

## Latest Dev external-manifest request build

The authorized Dev-only request-access experiment is built and handed off through
watched package paths. Main retains the ordinary URL handoff; Dev uses the direct
request with native prompts enabled and no duplicate fallback. The existing bottom
panel remains. Rejection/unavailability produces a diagnostic error and preserves
the signed copy; request success does not confirm installation or authorize deletion.
No error is classified as native Cancel yet. Phone access and Cancel behavior remain
unverified; this is not a proven automatic-dismissal fix.

The Release build, native bridge fixture and prompt lifecycle fixture passed.
ZIP integrity, identities, resources, arm64 and Dev host/widget signatures passed.
Main was built first; Dev was derived from that exact main. Existing compiler warnings
remain. No dependency update, manual resend, delivery monitoring or publication occurred.
Source is uncommitted on `0331def`; the local checkpoint includes the tracked patch,
untracked native bridge sources and a manifest of all current application source files.

- `KorSign.ipa`: `b0efcd35cbf6bf012a27d189bb460ed5fcf07858cfc501d942e35c1b0c0cc36b`
- `KorSign-Dev.ipa`: `958c6a5a9fe066d0b950d203b7baf24df4505629985e6717b27b5ca19c85f05e`

Source manifest SHA-256: `f0ab8a51051ec0b379900ae8bd853c2e81264264477d4f9dd5a6024fb9442968`.
Local checkpoint: `.codex/ipa-checkpoints/korsign-manifest-request-fi0u143e/`.
Embedded build version is historical; use these hashes to identify this candidate.


## Findings

All **18 original findings are addressed in code**; none remains partly addressed
or open. Physical validation of recent source-only fixes remains outstanding. The
7 improvement areas below are separate from that count.

| ID | Finding | Current status | Evidence or remaining work |
|---|---|---|---|
| F01 | Early signing failure ignored | Addressed — `38f072b` | Synchronous failure throws before output registration; `test_signing_failure.py`. |
| F02 | Unsafe archive extraction paths | Addressed — `2fae197` | Shared extraction validation; `test_archive_extraction.py`. |
| F03 | Unvalidated backup certificate IDs | Addressed — `3acafdf` | Validate all IDs and duplicates before restore writes; `test_backup_restore.py`. |
| F04 | Unchecked native binary patching | Addressed — `d145733` | Bounds checked before mutation; errors propagated; `test_macho_patching.py`. |
| F05 | Malformed DEB/plist crashes | Addressed — `c37f0f8` | Invalid input produces errors; `test_malformed_inputs.py`. |
| F06 | Download file/task ownership races | Addressed — `a829192` | Per-download staging and task identity guards; `test_download_ownership.py`. Background-session reconstruction remains unverified. |
| F07 | Core Data reads on the wrong queue | Addressed — `46d6642` | Main-queue snapshots for update comparisons, packaging and installer manifests; queue-confined source lookup. Stale/cancelled publication checks; `test_storage.py`, `test_installation_archive.py`. |
| F08 | General cleanup deletes active work | Addressed — `31d6ef0` | General cleanup clears caches/logs; protects working and pending files; `test_storage_cleanup.py`. Explicit app deletion/reset remain separate actions. |
| F09 | Tweak/entitlement saves report false success | Addressed — `e592d56` | Checked writes precede published state and file deletion; damaged loads block mutation; import/restore failures propagate. `test_library_persistence.py`; limits below. |
| F10 | Temporary staging outlives its consumer | Addressed — `a829192`, `31d6ef0` plus `dbca9dd` follow-ups | Download/install archives, tweak work, certificate/tweak/backup/web IPA exports and shared/web import copies have consumer-bound cleanup. Successful web imports retire their owned parent; failed/partial web inputs remain intentionally retained. Focused lifetime/upload/import checks and Release build pass; See DEVICE_VALIDATION.md for confirmed phone scope and remaining gaps. |
| F11 | Export returns a false destination | Addressed — `31d6ef0` plus `dbca9dd` follow-up | Local and web IPA exports share bounded metadata-safe filenames, including Unicode normalization limits. Local moves retry occupied names without replacing them; other errors propagate. `test_installation_archive.py` checks collisions, missing/unsafe/long metadata and failure preservation. Failed export keeps the signed library source; its disposable archive is cleaned. |
| F12 | Failed web replacement loses the old file | Addressed — `8321aa5` | Staging, atomic replacement, terminal error handling, success-only routing and MOVE/COPY overwrite checks; `test_web_uploads.py`. Retention and client limits below. |
| F13 | Displayed Web Manager auth differs from server | Addressed — `dbca9dd` | Port/login controls require a stopped server. Required authentication with missing credentials refuses startup; active protection and URLs use the server snapshot. Removed submit-triggered restarts. `test_web_manager_settings.py` covers validation, active state, stop/edit/start and retry with fake listeners; See DEVICE_VALIDATION.md for confirmed phone scope and remaining gaps. |
| F14 | Certificate selection uses a changing index | Addressed — `dbca9dd` | General, manual, batch, Auto Sign and updater selection use certificate UUIDs. Startup maps legacy indices once after a successful store fetch. Deleted selections do not fall back; picker recovery, backup settings and reset paths use the new keys. Real Core Data checks cover migration, list changes, actual Auto Sign/updater resolution and backup-key policy; See DEVICE_VALIDATION.md for confirmed phone scope and remaining gaps. |
| F15 | Batch installs bypass signed-copy cleanup | Addressed — `dbca9dd` | Batch retirement calls the existing InstallCleanup only for confirmed installs, after the results screen disappears and the runner stops. Typed outcomes preserve failed/unverified/skipped copies; accepted confirmations survive cancellation races. `test_batch_cleanup.py` covers retirement, late callbacks, cancellation, settings and signed-output identity. See DEVICE_VALIDATION.md for confirmed phone scope and remaining gaps. |
| F16 | Source addition ignores database save failure | Addressed — `46d6642` | Source callbacks propagate save errors and always complete on main; failure/retry/duplicate/network cases in `test_storage.py`. |
| F17 | Cancelled source load can overwrite a newer load | Addressed — `dbca9dd` | Existing generation now guards fetch entry, batches, results, completed-key publication and background/loading cleanup. Cancelled or superseded waiters cannot restart stale work; source snapshots are read after waiting. Empty current lists clear old results. `test_source_loading.py` uses delayed callbacks in both completion orders; See DEVICE_VALIDATION.md for confirmed phone scope and remaining gaps. |
| F18 | Self-update tracking implies unverified success | Addressed — `dbca9dd` | Server tracking ends as unverified, never inferred success/cancellation from progress loss or deadlines. Flow generations guard stale results and post-await side effects; native per-attempt downloads replace shared continuations. Terminal UI stops spinning and asks for a Home Screen/version check. Handoff, flow and download fixtures plus Release build pass; See DEVICE_VALIDATION.md for confirmed phone scope and remaining gaps. |

Test names refer to [the focused-check guide](../tests/README.md), which explains
fixtures, prerequisites, and limitations. Existing test results are recorded
from implementation work. Storage and installation archive checks passed during the F07/F16 follow-up.
The subsequent authorized Release build passed with Xcode 26.2; main and derived
Dev IPAs passed archive/identity checks. Initial device checks 1–6 passed on that build; further checks remain below.

## Current cleanup behavior

- Auto Sign signs imported/downloaded apps and removes the unsigned library
  copy after successful signing. Delete After Signing overlaps with that
  behavior; Install After Signing still applies.
- Delete After Installing controls the signed library copy after confirmed
  installation in the ordinary installation queue. F15 now applies the same policy
  to retired batches in source; phone batch behavior remains unverified.
- An installation archive is a separate temporary delivery file. Its owner
  keeps it alive through pairing reads, HTTP response lifetimes and server
  shutdown, then schedules cleanup off the main thread. Permanent exports are
  outside that cleanup boundary. Interrupted cleanup can wait until startup.
- Free Up Space clears caches and logs. Unknown temporary/managed files and
  pending uploads/downloads remain protected; they are not automatically
  classified as abandoned.
- Web Manager browser uploads now keep the committed file in the inbox and
  import an independent copy, as mounted-drive uploads already did. Users can
  delete the inbox copy explicitly. This costs extra disk space. Failed upload
  or import-copy preparation preserves the old destination.
- WebDAV replacement of a nonempty directory fails safely instead of deleting
  its contents. Abrupt termination can leave hidden upload staging. Neither
  transactional directory merging nor broad inbox recovery cleanup was added.

## Library persistence limits

Failed writes retain the previous saved state and report an error. Failed new
imports remove only their new copies. Damaged manifests block writes until repaired
and reopened; automatic repair was not added. Legacy model formats remain supported.
Folder operations span two manifests: a first saved step can remain if the second
fails. Backup restore is likewise not one transaction across all categories. Errors
propagate and existing tweak files are preserved. A partly successful ZIP import
keeps its archive; retrying can duplicate entries already imported successfully.
The entitlement editor retains failed edits for Retry while it remains open.

## Database read ownership limits

Update comparisons run on copied values; managed-object reads and publication stay
on main. Changed library snapshots are recomputed, while superseded/cancelled work
cannot publish. Cancellation does not interrupt an already-running comparison.
Archive preparation and local installer manifests capture metadata before worker
execution; remote-manifest URLs are composed on main before asynchronous probes.
Copying and compression remain off main. Explicitly deleting the source bundle
before it is copied can still fail packaging; a metadata snapshot is not a file lock.

The storage fixture uses real Core Data with concurrency assertions and a dynamic
results wrapper, not a hosted SwiftUI FetchedResults view. Archive/manifest checks
use main-actor read assertions and fake HTTP/probes. Real HTTP transport, UI refresh
and physical-iPhone integration remain unverified for these changes.

## Improvement areas

These are 7 optional or follow-up areas, not 7 additional confirmed bugs. No
speed, memory, battery or thermal gain has been measured.

| ID | Area | Status |
|---|---|---|
| O01 | Extraction timeout/cancellation contract | False timeout fixed; slow-success/error regression checks pass. True interruption remains optional follow-up; cleanup still waits for extraction. |
| O02 | Bound expensive concurrent operations | Unmeasured candidate; measure real multi-IPA demand first. |
| O03 | Move blocking preparation off the main actor | Unmeasured candidate; capture queue-safe values before moving work. |
| O04 | Credential storage/export and log privacy | Open; preserve sandbox protections and explicit export consent. F10 cleanup is addressed in source; credential storage/privacy review remains separate. |
| O05 | Toolchain, test and packaging maintenance | Local changes implemented and checked; Mac Release build passed. Obsolete XCTest retired. Optional hosted validation was cancelled and is not a Mac-workflow requirement; public release execution remains untested. |
| O06 | Accessibility | Source concerns need targeted VoiceOver/Dynamic Type checks. |
| O07 | Compatibility and small cleanup opportunities | No deletion campaign planned. Preserve functional compatibility identifiers and shared helpers. |

## Next implementation sequence

1. Keep the restored ordinary installer; do not repeat the failed native Cancel experiments.
2. Preserve the confirmed results in DEVICE_VALIDATION.md. Main updater success
   is confirmed; Main now runs the older public target and Dev remains latest.
3. Keep builds on the Mac. Include the O01 slow-import fix in the next requested
   local build; pursue other optional areas only for a concrete user need.

This order is a review guide, not authorization to build, publish, or change
remote services. No broad rewrite or dependency update is proposed.

## Device feedback: installation prompt

On the Dev artifact built from `46d6642`, the user confirmed launch, manual import,
signing, installation with retained signed copy, confirmed-install deletion, and
combined Auto Sign/Install After Signing/Delete After Installing cleanup.

After cancelling the iOS install prompt, the signed file remained, but the card
still displayed Sending Manifest. The user could close it with ×. The screenshot
and report establish misleading status; they do not establish an infinite wait.
The existing not-started deadline is 120 seconds.

Follow-up `47bd7f3` uses the existing OTA waiting phase for a shared single/batch
Waiting for iOS view and an explicit I Cancelled Installation action. Cancellation
finishes through the existing cancelled outcome and preserves the signed copy.
No cancellation is inferred from focus, missing progress or a timeout. The new
prompt lifecycle fixture and existing OTA/probe checks pass. Device validation
of the new view/action/retry is pending; this follow-up is separate from the
original 18 finding count.

## Private device-test checkpoint

Source: `47bd7f3c10b6baf5bf996171141e5732e43668cd`. Release build: Xcode 26.2,
arm64, iOS SDK, signing disabled for subsequent signing on the phone. Existing
bundled server resources were reused; no certificate refresh or dependency update.
Dev was extracted from that exact main IPA, with host/widget identities changed.
Both archives passed ZIP integrity, bundle/widget identity, resource and arm64 checks;
Dev's ad-hoc host/widget signatures verified. Existing compiler warnings remain,
including Swift 6 concurrency warnings; this is a Swift 5 build, not a warning-free
or whole-codebase concurrency certification.

| Artifact | SHA-256 |
|---|---|
| `KorSign.ipa` | `97b4ec1abbb902e33bb5d44e882ac9b8a1771cadf13a3313fc8dc84c3cbfd05b` |
| `KorSign-Dev.ipa` | `c267b3617df8197a87c94ab9012faf240a702c665402c09a68569f833c05ed01` |

Both artifacts are version 3.0.1. The embedded build string remains the existing
`2dbf78cc8947292c963bcef71fbde7ffad2180b4`; use the SHA-256 values above to identify
this test build. The validated files were placed in the automatic sender's watched
paths. Delivery and installation were not checked. Public release assets are unchanged.

Next, update the existing **KorSign (Dev)** through RyukSign on the user's iPhone
in the US. Repeat cancellation: decline the iOS prompt, tap I Cancelled Installation
in KorSign, confirm the panel closes and the signed copy remains, then retry that
copy. Initial tests 1–6 already passed on the previous `46d6642` artifact; do not
repeat them without a reason. Continue persistence, source and disposable-input
cleanup tests one at a time afterward. Do not fill the phone's disk or corrupt a
live library; temporary Mac fixtures cover save failures.

## Outstanding validation

On the Mac, focused filesystem/state fixtures passed during implementation.
The real Vapor HTTP integration fixture has not been rerun; its SwiftPM workflow
may fetch dependencies. Web upload checks use fake HTTP events with real temporary
filesystem operations. Updater Python checks were blocked by missing Flask during
the audit; no new environment or live service was checked here. The legacy XCTest
target is not established coverage. Source-only checks do not establish packaged
app compatibility.

After the first smoke test, a broader device session should cover large-file import/sign/install,
failed and cancelled operations, new archive cleanup, browser/WebDAV replacement,
and background download relaunch. Finder/Windows client sequences and directory
replacement behavior also need integration checks. Previously reported physical
confirmation of the ordinary OTA workflow and self-update Home Screen handoff
predates these audit fixes; it does not validate the new changes.

Zsign remains pinned to `df9370f482f7b9f77dab94bbcf80093c24a9c223` and
IDeviceKitten to `837cf1e14d4875771dd5ee1b754a4c86215c5db3`.

## Superseding cancellation investigation

The user rejected the manual cancellation view from `47bd7f3`. The working tree
restores the original bottom panel and adds temporary **Dev-only** LaunchServices
observer logging before OTA handoff. It logs event names and target-match counts,
not other apps' identifiers or raw metadata. Finish/stop removes the observer.
Notifications do not change install state, dismiss the panel or authorize deletion.
The old manual-button validation instructions above are superseded.

The uploaded phone log contains no progress cancellation signal for prompt
cancellation. One request reached the existing 120-second timeout. A private
`applicationInstallsDidCancel:` declaration is a lead, not proof that declining
an OTA prompt emits that callback on a jailed phone. Test Cancel and an accepted
install as separate controls; missing events without a positive control remain
inconclusive. Source fixtures cover lifecycle and matching only.

## Current cancellation diagnostic build

The original panel is restored; the rejected manual waiting view/action is removed.
Dev-only observer logging is diagnostic and does not dismiss the panel or change
cleanup. Source is uncommitted work on `0331def`; exact source patch is saved locally
with SHA-256 `18ee6e4aba4d8256f4ececb5337a5a30bec7b9b45a6a2a3745320795f47cc25b`.
Release build and both IPA validations passed. Dev is derived from that exact main.
Both were handed off through the watched package paths; no delivery monitoring,
manual resend, remote publication or dependency update was performed.

- `KorSign.ipa`: `67cf3d653b9831991088c9ed63d2ccd308983a42a0f3dbb07e5017eeebc588ba`
- `KorSign-Dev.ipa`: `f3145c784889798333eec8e9eab883f90388e5e34ec675bd9602cea9b825ae9b`

The build string is unchanged; identify these artifacts by their hashes.
`test_ota_install.sh`, `test_install_prompt.py`, ZIP/identity/resource/arm64 checks
and Dev signature verification passed. Native observer delivery and automatic
Cancel dismissal remain unproven. Existing compiler warnings remain.

First phone step: update existing KorSign (Dev) through RyukSign. Then test only
Cancel with a disposable signed app and export the Activity Log. The existing ×
can close the panel; this diagnostic intentionally does not infer cancellation.
Follow with an accepted-install control after reviewing the first log.

## Registration diagnostic follow-up

The first diagnostic produced no callbacks for either native Cancel
(`ryuksign 1.log`) or an installation confirmed by the progress probe
(`ryuksign 2.log`). Registration was requested, not verified. This does not prove
that the platform cannot expose prompt cancellation.

The new diagnostic reads aggregate observer count and service-observation state
before/after add/remove when those selectors exist. Missing data is explicitly
unavailable. It retains the existing panel and never drives cleanup or dismissal.
Process-local fixtures cover scalar reads, registration lifecycle and unavailable
remote-observer data. Device results are pending; do not repeat the first tests
without installing this changed diagnostic.

## Latest registration diagnostic artifacts

Release build, focused OTA/probe/prompt checks, ZIP/identity/resource/arm64
validation and Dev signature verification passed. Main was built first and Dev
derived from that exact main archive. Existing compiler warnings remain.
Both were handed off through watched package paths without delivery monitoring,
manual resend or publication. Source remains uncommitted on `0331def`.
Source patch SHA-256: `ef3e0a856dc58032cf7ca5cf74c39d66029e32e8786004389a36cd00ebc20122`.

- `KorSign.ipa`: `d23994ac0bcad3e08ad5c5430be1e03536f3410b996d672f06c589a5513c9050`
- `KorSign-Dev.ipa`: `31e632890741368b15ea9b36a1173b7f6661784bd79c4f8d81e1e762fa14f7ec`

Local validation and exact source patch: `.codex/ipa-checkpoints/korsign-observer-registration-n4icg6vy/`.
Build identity remains historical; use artifact hashes. Registration evidence
and automatic cancellation dismissal remain unproven on the phone.

## Cancellation investigation: registration and dispatch results

The third phone log shows local observer count increasing from 0 to 1 and service
observation reported active. No event arrived before the user closed the panel six
seconds after registration. This supports successful local registration, not a
remote delivery guarantee. Earlier Cancel and accepted-install controls likewise
produced no events during their observation windows.

`test_install_observer_dispatch.py` uses the real Mac local dispatcher with a fresh
process-local observer, benign proxy fixtures and the production Swift listener.
Cancel/install callbacks are delivered; removal prevents later delivery. There is no
real installation, system database change or remote service subscription. This
checks Mac local dispatch only, not native iPhone cancellation or delayed events.

No supported Cancel-only dismissal fix is established. A presentation-only design
could hide the panel when the prompt ends and re-present on payload activity while
retaining the backend request. It would also hide briefly for an accepted delayed
install. That behavior change is awaiting the user's choice and is not implemented.
No additional diagnostic IPA was built for this local-dispatch investigation.

Further cancellation investigation and the requested direct log-sharing button
are documented in [CANCELLATION_INVESTIGATION.md](CANCELLATION_INVESTIGATION.md).
The hide-and-reopen alternative remains unapproved and unimplemented.

## Previous Activity Logs Share build

The direct Share button beside the ellipsis is compiled into both IPAs. Release
compilation, ZIP/identity/resource/arm64 checks and Dev signature verification
passed. Main was built first and Dev derived from the exact main archive.
Both were handed off through watched package paths; no delivery monitoring,
manual resend or remote publication occurred. Existing compiler warnings remain.
Source is uncommitted on `0331def`; source patch SHA-256:
`bf60f2d66890b34e5b8de96ed9bed795dcb081f85317d8e3c9eda1cd77c1ad07`.

- `KorSign.ipa`: `53d0cfa5d92e8e3866a3870c4db66c7cf5684f562fb66a30e3d1ab3ffa803512`
- `KorSign-Dev.ipa`: `8c833ccdcde2027e7bf3861eb367eeb24a01d86bdb98c983db516fdb5e2746df`

Exact validation and source patch are saved locally under `.codex/ipa-checkpoints/korsign-log-share-e6jymwx_/`.
No further Cancel test is requested for this UI-only update. Cancellation behavior
is unchanged; no hide-and-reopen workaround was added. Share presentation and
button placement require physical observation. Dependency pins are unchanged.

The further [cancellation investigation](CANCELLATION_INVESTIGATION.md) now identifies
an iOS 26 request-specific completion candidate (`ASDExternalManifestRequest`).
Its block signature, normal-app access and prompt-Cancel semantics remain unverified.
No installation path or artifacts changed during this research.

Read-only iOS 26.3 simulator binary inspection now verifies the external-manifest
callback's three arguments and background completion queue. Phone access and
Cancel semantics remain unverified; no additional IPA was built. See the
[cancellation investigation](CANCELLATION_INVESTIGATION.md) for evidence and limits.
