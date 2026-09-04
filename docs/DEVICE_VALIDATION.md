# Audit-fix device validation

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


Status: user-confirmed Dev workflow/naming checks and Main updater success recorded
on 2026-09-09. Untested cases are identified separately below.
All 18 original findings are addressed in source. This is a validation plan, not a
claim that the latest changes work on the phone. Artifact hashes and handoff status
are recorded in AUDIT_STATUS.md.

The Mac is in Korea. Perform phone actions on the iPhone in the United States.
A laptop/browser check requires a network route to the phone's displayed address;
do not assume the Korea Mac can reach it. No USB or on-device shell is needed.

## User-confirmed results on the audit-complete candidate

The user confirmed Web Manager controls lock while running and missing credentials
block startup; ordinary automatic install cleanup; batch cleanup; partial batch
cleanup keeping the skipped app; retaining Signed with deletion disabled; Developer
staying selected after Standard was imported; two distinct Archives exports; source
refresh settling after leaving/returning; and Activity Logs sharing.

The user subsequently confirmed all three simple-name checks, certificate selection
after restart, browser login enforcement and password change, exported IPA reimport,
encrypted backup preview and incorrect-password rejection. The user also reports
backup restore works. The latest Main updater was then tested against the older
public release with explicit user agreement; KorSign reopened normally. Deleted-
certificate handling and direct temporary-file inspection remain untested.

Main now runs the older public target installed by the successful updater test.
Latest Dev remains separate. Updater timeout/unverified/cancellation branches and
IDevice behavior have not been physically verified.

## Simple-name candidate: three confirmed checks

After installing the new Dev update, open KorSign (Dev).

1. Press and hold a Signed app → Export. Repeat. In Archives, confirm names look
   like `App 1.0.ipa` and `App 1.0 (2).ipa`, without timestamps.
   Older exports keep their old names.
2. Settings → Activity Logs → Share. Confirm the attached file is `KorSign.log`.
3. Settings → Web Manager. If the old username was `ryuk`, confirm it is now
   `korsign`. A custom username should stay unchanged.

## 1. Confirm the candidate

1. Install the newly received **KorSign-Dev.ipa** using the existing phone workflow.
   Keep the current installation and its data; do not uninstall first.
2. Open **KorSign (Dev)**, not Main KorSign.
3. Open Settings → Web Manager and start the server with your existing valid settings.
4. Confirm the port and login fields are disabled while it runs. Stop the server.
   This is a visible marker of this candidate; version 3.0.1 alone cannot identify it.

Expected: existing Library/settings remain and Web Manager controls behave as above.
Stop testing and report an import/store error or missing existing data.

## 2. Verify Web Manager configuration

1. With the server stopped, enable Require Password. Leave its password empty.
2. Try starting. It must stay off and explain that credentials are required.
3. Enter a test username/password and start. Port/login fields must lock.
4. If your local laptop can reach the displayed address, open a fresh private browser
   window. Login must be required; valid credentials must work.
5. Stop, change the password, then restart. In a new private window, the old password
   must fail and the new password must work. Do not put passwords in screenshots/logs.
6. Stop the server when finished.

Expected: no silent unauthenticated startup or mismatch between displayed address
and active port. HTTP remains unencrypted; use a trusted network. Without laptop
connectivity, mark the browser checks untested rather than passed.

## 3. Verify certificate selection

1. Note the selected certificate in Settings and Updates.
2. If you have a second certificate pair you own and can safely import, import it.
3. Reopen manual signing, batch signing and Updates. The original choice must remain.
4. Select a disposable test certificate, then delete that test certificate only.
5. Signing must ask for a replacement. An explicit updater certificate must show
   unavailable, rather than switch to another identity.
6. Restore the intended selection.

Expected: adding/deleting another certificate never changes the selected identity.
Skip deletion if you have no disposable test certificate. Do not delete your only
working certificate to perform this check.

## 4. Verify ordinary import and install

1. Use a small test IPA that you own. Keep its original in Files.
2. Enable Auto Sign, Install After Signing and Delete After Installing.
3. Import it and accept installation.
4. Open the installed app from the Home Screen to check it launches.
5. Return to Dev and close its completed installation panel.

Expected: Auto Sign removes the unsigned Library copy after successful signing;
confirmed installation removes its signed Library copy. The original in Files
remains. If KorSign says installation is unverified, keeping the signed copy is
correct. An empty entire Library is expected only if it had no other apps.

## 5. Verify batch cleanup and partial completion

1. Prepare two small disposable test apps. Enable Delete After Installing.
2. Batch-install them. Finish both installations, then close the results screen.
3. Confirm only those confirmed installed Library copies are removed.
4. Repeat with two test apps: finish the first, skip/cancel the second, then close
   the results screen.
5. Confirm the first confirmed copy is removed and the skipped/cancelled copy stays.
6. With Delete After Installing off, repeat one successful test; its copy must stay.

Expected: result rows remain readable until dismissal. Failed/unverified apps stay.
Use KorSign's explicit Skip/Cancel controls; do not repeat the unresolved Apple
prompt automatic-dismissal experiment.

## 6. Verify exports and temporary-file consumers

1. Export the same signed test app twice to Files. Both saved copies must remain.
2. Share/save a disposable tweak or certificate export; cancel one share and complete
   another. The saved copy and original must remain usable.
3. If using Web Manager, download a disposable app/tweak and confirm the resulting
   file is readable after the download completes.
4. If using backups, create an encrypted backup and save it. Confirm it can be opened
   for preview. Do not restore over the working Library solely for this check.

Expected: no missing-file/share error or overwritten export. Odd/long metadata and
same-time collisions have focused Mac tests; no need to manufacture malformed IPAs.
The jailed phone cannot directly prove every temporary directory was removed.
UI success/file preservation and source-level ownership checks are separate evidence.

## 7. Verify source refresh

1. Open Sources and refresh.
2. While loading, leave KorSign briefly, return and refresh again.
3. Confirm the loading indicator settles and the newest list stays visible.
4. If you have a disposable repository entry, remove it and verify it does not return
   in the list when an older request finishes.

Expected: no stuck loading state or visibly stale replacement. Deterministic request
ordering is covered by the Mac fixture; a normal phone run cannot force every race.

## 8. Updater: successful Main path confirmed

The user knowingly chose the older public target, ran the latest Main candidate's
Server updater, accepted installation, waited on the Home Screen, and confirmed
KorSign reopened normally. No repeat is needed. Main now contains the older public
code; Dev still contains the latest candidate.

This confirms the successful path, not timeout/unverified/cancellation or IDevice
branches. Full backup restore is separately user-reported as working; the specific
restore contents and build were not captured in this test sequence.

## Reporting each result

Report the step number and **passed**, **failed**, or **not tested**. For a failure,
include what you tapped, what you expected and what appeared. Use the Activity Logs
Share button if logs help; do not include certificate passwords or private keys.

Native Apple Cancel-only automatic panel dismissal remains unresolved and is tracked
in CANCELLATION_INVESTIGATION.md. Seven improvement areas remain separate from the
18 source fixes. Do not label either group physically verified from compilation.
