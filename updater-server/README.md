# KorSign updater service

A small signing service for published `korboybeats/KorSign` releases. It reuses
the app's multipart `/ryuksign/sign` contract; that compatibility route does not
contact RyukSign. The main bundle ID is `com.korboy.korsign`; Dev uses
`com.korboy.korsign.dev`. Each must have its exact matching release asset.

## Deployment

Use an Ubuntu ARM VM within Oracle Always Free allowances. Install `make`,
`g++`, `pkg-config`, `libssl-dev`, `python3-venv`, and `ca-certificates`.
Build the repository's Zsign submodule at
`df9370f482f7b9f77dab94bbcf80093c24a9c223` with
`git -C Zsign apply --unidiff-zero ../updater-server/zsign-cms-failure.patch` in a separate
server build checkout, then `make -C Zsign/build/linux VERSION=df9370f-cms-guard`.
The small server-only patch propagates CMS signing failures instead of returning
an IPA without a signature. It does not change the app's pinned submodule.
Install `Zsign/bin/zsign` as
`/usr/local/bin/zsign`.

1. Create a system user/group `korsign` with no login shell. Copy this directory
   to `/opt/korsign-updater`, owned by root and readable by the service user.
2. Create `/opt/korsign-updater/venv` with `python3 -m venv`; install
   `requirements.txt` into it. Keep source and the venv writable only by root.
3. Set `KORSIGN_PUBLIC_URL=https://YOUR-WORKER.YOUR-SUBDOMAIN.workers.dev`
   in `/etc/korsign-updater.env`.
4. Install the supplied systemd service and cleanup units into
   `/etc/systemd/system`. Run `systemctl daemon-reload`, then enable/start
   `korsign-updater.service` and `korsign-updater-cleanup.timer`.
5. Install Cloudflare's official `cloudflared` package. Create a dedicated
   tunnel and install its connector as a service. Keep its token private; make
   a systemd unit containing the token readable only by root (`chmod 600`).
6. Create an HTTP Workers VPC Service through that tunnel, targeting
   `127.0.0.1` port `8080`. Bind it as `UPDATER` to a dedicated Worker running
   `worker.js`. Disable Worker invocation logs and traces so download tokens
   are not stored there. No public inbound HTTP port is needed on the VM.
7. Verify public `/health`, signing, and IPA HEAD/GET/range responses. Set the
   verified HTTPS address in `KorSign/Resources/SelfUpdateConfig.plist` before
   building and publishing the matching IPAs.

The shipped address is `https://korsign-updater.korboybeats.workers.dev`.
Cloudflare encrypts traffic through the tunnel; HTTP is used only on VM loopback.
[Workers VPC](https://developers.cloudflare.com/workers-vpc/configuration/vpc-services/)
is currently beta and [free during beta](https://developers.cloudflare.com/workers-vpc/reference/pricing/).
Oracle capacity, idle-instance reclamation, and future pricing remain external
limits. Keep the VM and dependencies updated; do not enable paid upgrades merely
to provision this service.

## Data handling and limits

- Accepts only version, allowed bundle ID, password, P12, and provisioning profile.
- Uploads: 2 MiB; release IPA: 100 MiB compressed / 1 GiB unpacked.
- One signing job at a time, at most 10 attempts per five minutes and 10 retained
  signed downloads. These limits are per process; run exactly one Gunicorn worker.
- Zsign has a 120-second deadline and a private working directory. Credentials
  and extracted input are removed when the request completes or fails.
- Downloads use random 192-bit tokens and become unavailable after 30 minutes;
  a five-minute timer removes expired output. A forced process/VM crash can leave
  temporary files until the service's private temporary area is removed.
- No request bodies, passwords, signing output, or download tokens are logged by
  the service. The signed IPA necessarily includes its provisioning profile,
  which can contain device identifiers; treat its URL as private.
- iOS decides whether the profile/signature allows installation. A valid server
  response alone does not prove a successful self-update or certificate validity.

## Checks

```sh
python3 -m venv /tmp/korsign-updater-test
/tmp/korsign-updater-test/bin/pip install -r updater-server/requirements.txt
/tmp/korsign-updater-test/bin/python updater-server/test_server.py
node updater-server/test_worker.mjs
# Optional real CLI regression, using only generated disposable keys:
python3 updater-server/test_signer.py /path/to/zsign packages/KorSign.ipa
```

Installing requirements may contact package services. The optional CLI check
creates disposable signing artifacts.

The Python check replaces release downloads/signing with disposable fixtures.
It covers request rejection, main/Dev identity, revision/build mismatch rejection,
cleanup on timeout, concurrency, rate limits, expiry, and binary HTTP HEAD/GET/ranges. The Worker check validates
public route/upload limits and private forwarding. A separate deployment smoke
check must exercise real Zsign using a disposable certificate, then verify the
public manifest and binary responses. Do not use a real user's private key for
routine server tests.

Publish the validated main IPA under the matching `v<version>-r<build>` GitHub release.
Keep Dev builds private unless their publication is explicitly requested.
Without its matching release asset, Dev cannot install an update. The main IPA
cannot replace Dev because their bundle identifiers differ.
`update-repo.sh` refreshes the source feed with exact asset matching. Review that
change with the release. Automatic feed updates require the repository workflow
to be enabled.

Revision releases use `v<version>-r<build>`. The service checks both the IPA's
three-part version and numeric build against this tag, before and after signing.
Legacy `v<version>` releases remain supported. Draft releases are not downloadable
through the signing service. Verify revision support before publishing; after
publication, verify the public asset identity and test signing and installation
separately. A successful asset download is not proof of signing or installation.
