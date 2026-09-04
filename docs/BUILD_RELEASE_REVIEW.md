# Build and release review — 2026-09-09

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


O05 remains open. The private Main/Dev packaging path has produced validated builds,
and the public release workflow now has the validation gate described below.
Remaining packaging and release-policy gaps keep O05 open.
This was a source review: no build, IPA transfer, workflow dispatch or publication
was performed. Existing edits and dependency pins were preserved.

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

Runner inventory: [GitHub macos-15 documentation](https://github.com/actions/runner-images/blob/main/images/macos/macos-15-Readme.md)
lists /Applications/Xcode_26.2.app. Availability was checked during implementation;
the workflow fails if that explicit toolchain is unavailable.

## Original review findings (1–4 now addressed as described above)

### 1. Release compiler is too old — confirmed

Location: [.github/workflows/release.yml](../.github/workflows/release.yml#L18).
It selects Xcode 16.4. Current app source references iOS 26 SDK declarations,
including BGContinuedProcessingTask in
[KorSignApp.swift](../KorSign/KorSignApp.swift#L472). Availability checks govern
runtime use; they do not supply declarations to an older SDK.

Smallest fix: choose an explicitly verified Xcode 26 toolchain on a compatible
runner and print/check the selected Xcode and iPhoneOS SDK before compiling.
Verify runner availability when implementing; this review did not check hosted
runner inventories. Keep deployment targets and dependency pins unchanged.
Verification: an unsigned compile on the chosen CI runner, without publication.

### 2. Release artifact selection and validation are too broad — confirmed

Location: [release.yml](../.github/workflows/release.yml#L27), lines 27 and 41.
The workflow moves every packages entry and publishes every matching IPA, instead
of selecting the policy-required Main IPA. A fresh checkout may contain only Main,
but the workflow itself does not enforce that condition. It has no IPA integrity,
bundle identity, resource, architecture or provenance gate and runs no focused checks.

Smallest fix: stage exactly KorSign.ipa, validate it using the rules already proven
in private packaging, and fail before publication on a mismatch. Do not publish the
local-only .codex packaging script, AGENTS.md or PROGRESS.md; extract only the reusable
validation logic into a tracked tool when implementing.
Verification: an extra Dev IPA cannot enter the release set; corrupt/wrong-bundle
fixtures fail, and a valid Main artifact passes. Keep publishing a separate step.

### 3. Packaging deletes the last artifact before the replacement is valid — confirmed

Location: [Makefile](../Makefile#L59), lines 59–61.
It removes packages/KorSign.ipa before zip completes, then writes directly to the
watched final name. A failed zip loses the previous artifact; local watchers can
observe an incomplete replacement. The private packaging path already avoids this
by validating in staging before handoff.

Smallest fix: package under a unique temporary path on the destination filesystem,
validate it, then atomically replace the final IPA. Preserve the previous artifact
until replacement is ready. Do not expand this into an unrelated build-system rewrite.
Verification: injected zip/validation failure leaves an existing sentinel artifact
unchanged; success replaces it only after validation.

### 4. Server dependency preparation can silently produce incomplete resources — confirmed path

Location: [Makefile](../Makefile#L19), lines 19–29 and 54.
The target removes existing deps before fetching, falls back to a warning on fetch
failure, does not reject missing JSON fields, and ignores resource-copy errors.
This can package missing or unusable TLS material. Device impact depends on the
selected install mode and whether Documents already contains usable resources;
[ServerInstaller+TLS.swift](../KorSign/Backend/Server/ServerInstaller+TLS.swift#L59)
checks both locations. This is not evidence that every such build cannot install.

Smallest fix: stage and validate fetched fields before replacing deps; make the
release resource policy explicit and reject an incomplete required pack. Preserve
the last validated local files on failed refresh. No endpoint change is proposed.
Verification: offline/malformed-pack/copy-failure fixtures cannot silently replace
valid dependencies or publish an incomplete required-resource artifact.

## Follow-up, not a release gate that currently runs

The legacy test target is still registered in the Xcode project at line 280 and
referenced by KorSignTests.xcscheme. Its source imports Esign and decodes Repository
even though the target has no Esign package dependency and production uses
AltSourceKit. It also fetches an external repository and the deobfuscation test
discards its result. See [KorSignTests.swift](../KorSignTests/KorSignTests.swift#L10).

Do not call it dead code or treat a successful Release build as a passing test suite.
Smallest next action: retain the existing focused fixtures as the release checks;
decide separately whether to repair the XCTest target with local fixtures or retire
it after checking target/scheme references. Do not rebuild an entire test framework.

The release workflow also targets v<marketing-version> without an explicit policy
for an already-existing tag. Current 3.0.1 therefore points at the existing release
name. Before implementation, choose a new-release versus deliberate-replacement
policy; do not silently replace a public artifact just to validate the pipeline.

## Existing protections worth keeping

- Release execution is manual, not triggered by every source edit.
- Submodule checkout is enabled; Zsign's pinned revision is unchanged.
- update-repo.sh uses strict shell handling, exact bundle-to-asset matching and a
  temporary output before replacing the feed. Its shell syntax check passed.
- Both shared scheme XML files parsed successfully. This is only syntax evidence.
- Private packaging validates Main and derived Dev before handoff and records
  hashes, source inputs and rollback artifacts. Reuse those rules.

## Recommended order

1. Fix release toolchain selection, exact Main artifact selection and pre-publication
   validation together.
2. Make Makefile artifact/dependency replacement safe under failure.
3. Resolve legacy XCTest coverage and existing-tag policy before relying on automated
   public releases.

No public release or hosted CI run was authorized or performed by this review.

Release command reference: [GitHub CLI release create](https://cli.github.com/manual/gh_release_create).
`--target` selects the commit for a newly created tag; creation with assets stages
a draft, uploads assets, then publishes. This workflow does not provide automatic
recovery for partial publication.

Integration reference: [GitHub GITHUB_TOKEN event behavior](https://docs.github.com/en/actions/concepts/security/github_token).
Token-created release events do not start another release-event workflow, which is
why the publishing workflow now calls the feed workflow directly.
