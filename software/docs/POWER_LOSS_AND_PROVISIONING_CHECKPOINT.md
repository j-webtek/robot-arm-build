# Power-loss observation and next configuration stage

## Observed event — 2026-09-18

User reports that unplugging main motor power caused the arm to fall/drop.
User reports no damage; no independent mechanical inspection was performed.
USB remained connected. This is a reported physical event, not a firmware fault
diagnosis or evidence that the previously observed pose remains valid.

## Standing procedure correction

- Mechanically support the moving links BEFORE removing motor power, switching
  off, disabling torque, or any operation that could release holding torque.
  Securing the base alone does not support the articulated links.
- Do not rely on USB power, software stop, or servo holding torque as a support.
- Keep hands away from joints/pinch points. Use stable supports; do not force
  joints against resistance. Do not restore power merely to lift a fallen arm.
- After a drop, inspect the mount, links, fasteners, cables and connectors before
  powered movement. A report of no visible damage is not a mechanical clearance.
- Treat all earlier pose/clearance assumptions as stale. Acquire fresh joint
  feedback before selecting any later motion target; do not replay old targets.

For now, keep motor power disconnected and the arm resting securely. Software
preparation can continue without hardware access or further physical changes.

## Configuration work that can proceed offline

The reviewed application is already installed. Its startup was validated as
IDLE / NOT_CONFIGURED. The following work does not require motor power:

1. Review the policy parser and key loader against the installed source/build.
   Do not convert example/test-fixture joint bounds into live authorization.
2. Prepare a filesystem-preserving provisioning tool using a private copy of the
   verified LittleFS image. Never use a mount path that formats on failure.
3. Require an explicit reviewed policy and a new cryptographically random 32-byte
   secret key, with private host storage. Do not place key bytes or Wi-Fi data in
   reports, source control, console output or shared exports.
4. On the offline image, add only `/rocell-diagnostics.json` and
   `/rocell-diagnostics.key`; compare every existing file's path and contents
   before/after, remount and validate the two new files. Keep source backup intact.
5. Test failure cases: malformed policy, wrong key length, existing destination
   files, filesystem corruption, changed source identity, full filesystem and
   output failure. No implicit overwrite or destructive recovery.
6. Before proposing a device write, obtain a fresh filesystem read and compare
   with the reviewed baseline; do not overwrite any intervening changes. Review
   exact image hash, partition range, preservation checks and recovery artifact.
7. Request separate explicit authorization for provisioning and its startup.
   Existing application-installation approval does not authorize this stage.

## Important distinction for the next test

### Offline implementation checkpoint

`src/rocell/application/diagnostic_provisioning_image.py` now stages a candidate
entirely in memory with pinned LittleFS 0.19.0. It verifies the source hash,
requires a policy-validator callback, rejects invalid keys/existing destinations,
preserves existing files/directories, remounts and checks exact new-file content.
It has no hardware interface, automatic formatting, persistent output or key
generation. Returned image bytes contain secrets and must remain private.

Synthetic-filesystem tests cover preservation/remount, invalid input, policy
rejection, existing destination, corrupt filesystem and injected write failure.
The permissive validator in those filesystem tests is a test double only.
Before real staging, integrate the actual installed native parser as validator,
private output publication, and reviewed post-drop joint windows. No live policy
or key has been generated, staged or provisioned by this checkpoint.

Native-validator follow-up: `firmware/diagnostics/validate_provisioning_policy.cpp`
now wraps `ControllerDiagnosticConfigParser` directly, using the installed
conversion identifier. `NativeProvisioningValidator` checks the executable hash,
pipes exact policy bytes with a five-second timeout and rejects unexpected output
or failures without retry. Windows input/output use binary mode to prevent CR/LF
translation and control-Z truncation. Tests exercise actual compiled parser
acceptance/rejection, identity mismatch and control-Z suffix rejection. This is
host tooling only, not a replacement firmware image. Before live staging, still
bind its source/dependency hashes to the approved build evidence and implement
private publication; syntax acceptance alone does not approve physical bounds.

Build-evidence follow-up: `scripts/build_bound_policy_validator.py` verified all
current diagnostic headers against both the recorded source hashes and the
copied sketch headers used by the approved app. It compiled a host validator and
published a verified nonsecret build export:
`wizard-20260918T141334371391Z-2d979520b96d43bab957497217a37340`.
Executable SHA-256:
`d51189345162218dec48ecdcf5033d18fa11848713e79d95c8a42297b164e610`.
The script checks source stability before/after compilation and records current
ArduinoJson file hashes. Historical library hashes were not recorded by the
original build, so full historical dependency-byte equivalence remains unproven.
The original build's ArduinoJson version record is weaker evidence, not a hash
match. No firmware compilation/upload or device access occurred in this step.

The current challenge GET initializes diagnostic ownership/configuration and is
not a passive status request. Do not call it merely to check network health.
Status GET is the passive diagnostic check. No challenge, start POST, serial
connection, reset, provisioning or servo command is needed for offline preparation.

Before live testing, establish a supported starting arrangement and fresh actual
joint positions. The existing policy requires all seven servo positions/targets
within reviewed windows and a bounded elbow delta. Do not widen these windows to
make an unknown post-drop pose pass. If no supported read-only baseline path is
available, design/review that path before enabling a motion test.

## Private storage and baseline-path review

`providers/windows/diagnostic_image_store.py` now stores staged image bytes under
current-user Windows DPAPI, using the existing bounded protection primitive.
Protected chunks bind a separate image domain, complete-image digest and index.
Exclusive flushed publication and decrypted readback are required; existing or
partial destinations are never overwritten. No plaintext image file is created.
It does not protect against other processes running as the same Windows user,
and Python plaintext byte buffers are not guaranteed to be zeroized.
Tests cover native Windows roundtrip/ciphertext tamper, reordered/mixed/missing
chunks, invalid inputs and no-overwrite. Only synthetic images were stored.

Review of `ConfiguredDiagnosticRuntime`, `AuthenticatedDiagnosticOwner` and the
configured routes confirms that the deployed diagnostics do not expose a separate
fresh whole-arm baseline scan. Status is metadata, not joint acquisition. The
whole-arm read gate is coupled to an authenticated movement attempt. Do not use a
deliberately failing or guessed movement request as a discovery mechanism.

Next implementation milestone: an explicit finite baseline-only acquisition
operation, mutually exclusive with the motion owner. It must read supported
target/position registers for IDs 11 through 17, retain timestamps and raw read
results, stop on read failure, and have no servo-write call path. Simulation must
assert zero writes on success and every failure path. Host collection/export must
retain incomplete evidence without claiming a pose or motion authority. This
requires a separately reviewed application deployment before hardware use; the
already-installed image must not be represented as offering this capability.
Baseline-only acquisition must not provision a motion policy or enable a start
listener. Subsequent movement bounds need the resulting fresh evidence and the
post-drop mechanical setup review, not the old example windows.

Baseline implementation checkpoint: `baseline_only_scan.h` now performs a finite
seven-ID read scan, retaining target/feedback pairs and stopping before later
joints after a failed pair. It checks byte order, read validity and bounded
pair/scan timing, consumes one attempt and never retries. A pair completes both
reads even if the target read fails; this is evidence collection, not a resend.
The native test uses a bus with no servo-write methods and covers all 14 read
failure points with timeout/short-read/device-error responses, repeated invocation,
clock failure and invalid configuration. Moving/unsettled flags are retained as
observations rather than mistaken for motion admission.

This primitive is not deployed and is not a complete scan interface: exclusive
bus ownership, route integration, serialization, host assessment and export must
still be connected and tested before a new application is proposed. Existing
approved-build validation now uses only the recorded header set, keeping new
uninstalled feature headers outside that historical source binding.

Baseline evidence follow-up: `baseline_only_json.h` serializes the finite scan
with boot/scan identity, reference profile, completion reason and raw compact
read pairs. `application/baseline_only_review.py` independently checks identity,
read counts, sequence, timing, return lengths, device errors and decoded values.
Partial/invalid acquisitions yield INCONCLUSIVE (or reject a malformed envelope),
never endpoint arrival or permission to move. Complete scans retain moving flags;
capture is not a stationary-pose claim, simultaneous sample, or proof of freshness
at a later use time. The native simulation now exercises serializer capacity
failure and successful/failed scan export, integrity verification and assessment
replay. Exclusive ownership and the actual controller/host route are still pending;
this code has not been deployed or used to acquire hardware positions.

Exclusive-owner/interface checkpoint: `diagnostic_session_claim.h` provides a
single-main-loop, non-releasing session claim for baseline OR motion.
`baseline_only_owner.h` validates boot/scan identities, queues one scan without
bus access in the request, and captures it on polling. Completed/faulted scans
cannot retry or release ownership. `baseline_only_routes.h` registers an explicit
POST `/rocell/diagnostics/baseline` (exact boot_id/scan_id JSON; 202 queued,
400 invalid, 409 unavailable) and a passive GET of retained scan evidence.
GET never initiates acquisition. Duplicate POST does not repeat reads. No key or
policy files are opened and no motion listener is started by these components.

Native tests cover claims in both orders, failure retaining the claim, request
validation, duplicate JSON keys, repeat POST, and GET without acquisition. The
bus double exposes only reads. The session gate is not a multi-task mutex and
does not protect ingresses that fail to consult it. Therefore the next candidate
must wire the existing motion challenge through this gate, instantiate/poll the
baseline owner, register the routes, and test that integrated composition before
any deployment proposal. These headers alone do not change the installed image.

Integrated candidate checkpoint: `prepare_owner_firmware_candidate.py` now has
an explicit `--baseline-scan` option requiring a new configured revision. Revision
3 was generated separately from installed revision 2. It initializes the scan
owner after boot identity generation, registers the baseline POST/GET routes,
polls the queued owner in the diagnostic loop, and makes the existing motion
challenge acquire the SAME session claim before loading configuration/key files.
The original source and installed candidate remain unchanged.

Tests compile the actual generated challenge header: baseline-first blocks all
configuration opens/runtime initialization; motion-first (including configuration
failure) retains the motion claim and excludes scanning. Route/owner simulation
also checks repeated requests cannot reacquire the bus. Candidate wiring is
checked separately. The ESP32 target is compiled with the default 4 MB layout and
PSRAM disabled; build results must be reviewed before proposing installation.
No deployment or hardware scan is authorized by these implementation tests.

ESP32 compilation completed successfully. Verified build export:
`wizard-20260918T142539650146Z-b647003206cc4cd190819583d13e6be8`.
Revision 3 application SHA-256:
`46e23efb7f9f18557882b1b185ecf4874ba4b2123ef64867f3a2831c56e01ee1`.
Generated partition SHA-256 remains
`148b959cbff1c38aa8e1d5c0ba9d612c54997b945e56a63f41223eef650653a1`,
matching the reviewed installed layout. This is compile/export evidence, not
runtime validation or upload approval. Host one-shot request/collection support
and a precise deployment review remain before using this capability on the arm.

Host follow-up: `baseline_only_client.py` provides a bounded single POST and
separate GET, with a durable per-endpoint/boot claim before transmission and
verified preparation/result exports. Lost replies are DELIVERY_UNCERTAIN; failed
collection is COLLECTION_INCONCLUSIVE; neither permits a resend. Tests cover
complete/partial scans, delivery/collection errors, persistent duplicate rejection,
wire format and result-export failure. Ten targeted host/integration tests passed.
The precise next approval boundary is now `BASELINE_SCAN_R3_DEPLOYMENT_PROPOSAL.md`.
No actual baseline request has been sent and no r3 deployment has occurred.
