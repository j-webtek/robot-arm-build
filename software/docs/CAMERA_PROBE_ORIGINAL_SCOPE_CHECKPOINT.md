# Camera probe: authenticated original setup under camera ownership

10 September 2026. Successor to the
[file-only preparation wizard](CAMERA_PROBE_SETUP_WIZARD_CHECKPOINT.md), within the
existing [developer playbook](CAMERA_ARM_DEVELOPER_PLAYBOOK.md).

This increment implements a read-only internal handoff. It does **not** expose
a new Connect button, grant camera admission, start a native camera worker, open
a serial port, pass a hardware stage, or enable robot motion.

## What changed

The new camera_probe_original_scope.py reads the complete reviewed v16 setup
using the caller-owned M1PhysicalCameraTransaction and exactly CELL, SESSION and
CAMERA leases. The original assigned directory comes from the scoped store.
Browser paths and comparison hashes cannot substitute for that original store.

Session now has one shared full-history reader. Its existing stage-only
entrypoint still accepts exactly CELL and SESSION. The new internal camera path
uses read_camera_evidence, requires strict full-history verification, and
preserves all existing role, manifest, byte-limit, journal and predecessor checks.
No nested transaction or new persistence implementation was introduced.

After authentication, VerifiedCameraProbeOriginal holds the immutable snapshot,
full workflow, original binding, preparation and review. Its detached summary
has all authority/connected/qualified flags false. There is no deserialize or
restore entrypoint. Its private provenance marker prevents accidental internal
construction, not arbitrary Python code executing inside the application.

The assert_current method permits semantic reuse only after checking:

- Current application guard, source fingerprint, cancellation and the original
  deadline. The guard must finish normally with no returned approval value.
- Exact active transaction and camera leases, matching cell/session, and the
  fixed probe action. Capture and unrelated actions are not accepted.
- Fresh M1 campaign records and the actual session snapshot, then exact equality
  with the authenticated snapshot, including the entire inventory and journal.
- Context and lease ownership again after those reads.

The existing core still owns changing attempt/quarantine heads, the exact
execution challenge and one-use authorization. This handoff issues no permit.

## Timing

The complete semantic history must be authenticated before issuing the existing
short-lived permit. Repeating that audit inside every permit check would consume
its limited lifetime.

The reader honors a maximum 180-second original-read budget within the caller's
bounded operation (at most 300 seconds at entry). Reuse keeps that original
deadline. Shared-reader source checkpoints recheck source, Stop and time after
file hashing. A clock earlier than the completed original read is rejected.

These are admission limits, not measured hardware performance guarantees.
Fresh M1 snapshots still validate actual stored bytes. The full-history test
uses a modeled clock and storage; real maximum-size store latency under the
30-second permit lifetime still needs measurement in the integrated path.

## Verification boundaries

1. Fast handoff tests model the full-reader result, clock and transaction. They
   exercise hashes, exact leases, launch/review state, source checkpoints, expiry,
   Stop, changed context, request and snapshot mismatches. They do not establish
   original-history truth.
2. Complete composition runs every original v16 predecessor verifier on the
   same typed history through the CAMERA route. Storage, device observations and
   the clock are modeled. It checks all original references, unchanged snapshot,
   semantic reuse without replay, old stage-only boundary refusal and corrupted
   original-byte rejection.
3. The real NTFS/M1 test uses actual qualified local storage and OS leases, but
   deliberately models semantic authentication over a synthetic predecessor.
   Closed scopes, added packages and corrupted original payloads prevent reuse.
   No device admission or execution permit is requested.

The first full-composition draft caught a callback-signature mismatch: the shared
reader calls check(source=True). The handoff now accepts and honors that contract,
including post-hash deadline checking. Fast tests exercise the same callback.
Failed draft reports remain preserved.

No single lane claims a complete public wizard + genuine original store +
physical camera integration.

## Required next integration

1. Bind this handoff to the existing Setup/Arrival owner and current logged
   enrollment, retaining the operation deadline and one-use lifecycle. Never
   import a saved summary as a live owner.
2. Build substantive facts from that context: accepted-unit continuity, applicable
   dependency epochs, current operator-reported conditions distinguished from
   measured conditions, and capacity for the assigned output/evidence directories.
   Retain the underlying facts, not only hashes. Initial probe admission must not
   depend on its own future capture/calibration outputs.
3. Connect scoped facts to the existing exact M1 transaction and v2 dispatch owner.
   Keep Session's default-denying provider until this is complete. Audit full
   originals before prepare/execute and revalidate in subsequent transactions,
   preserving the core's changing attempt heads.
4. Reuse the campaign's fresh endpoint/driver matching, installed-file policy,
   bounded child supervision, paired-result retention and preview ingestion.
   Do not create another camera controller or raw browser command endpoint.
5. Prove public probe/preview with an incapable producer and real storage:
   stale frames, Stop, changed source/identity, uncertain publication, cleanup
   failure and export after interruption.
6. Continue capture/baselines and placemat calibration, then RoArm identity,
   connection/startup/feedback. Connection is separate from permission to move
   or contact a keyboard/phone.

### Existing-owner integration details

The current M1 camera facts callback receives only request and snapshot.
The handoff's assert_current additionally requires the actual active transaction.
That transaction-bound facts join is not implemented by this increment. Extend
the existing persistence owner narrowly; do not use a fake transaction, subclass,
saved approval value or a second coordinator to satisfy the callback.

PhysicalCameraSession keeps its default-denying facts callback. Its stage
transaction clears its cached store on exit and requires refresh; it is not a
long-lived acquisition transaction. A later probe must bind the existing
acquisition service to the verified original session before comparing its plan,
especially when the current wizard launch differs from the original launch.

The existing acquisition service's run_admitted_activation_campaign already
accepts the exact persistence, request key, expected plan hash, cancellation and
original-context revalidation callback. Its dispatch owner uses separate CAMERA
transactions for admission, prepare, execute and terminal readback. Authenticate
once before short-lived permits, then revalidate the actual original snapshot
inside each transaction without freezing the core-owned changing attempt heads.

Admission-fact retention and output capacity are still missing: camera facts
currently freeze documents but do not themselves prove their meaning, and the
camera reservation path does not yet retain the underlying substantive facts.
Any new retention role needs bounded original readback and failure/partial-write
tests, while preserving existing camera/USB record formats and generic limits.

## Export destination

The user confirmed:

    C:\Users\Jack\Desktop\robot-arm-build\software\runs\wizard-exports

The launcher already uses that default. Each diagnostic export creates a fresh
bundle without restoring hardware authority. Prior exports, native binaries,
runtime pins and checkpoints are unchanged.

## Verification record

Application source fingerprint:

    d4760f1d03e378e93b49cfc53e6c22ceda1f1173018d856d5b911d88294975f4

- probe-scope-final-20260910-01.xml: **219 passed**, 127.12 seconds. Selected
  wizard/setup/storage tests, including 49 cases in the new handoff test file.
- probe-scope-full-final-20260910-01.xml: **2 passed**, 315.49 seconds. Existing
  stage-only original composition and the new complete CAMERA-scope composition.
- Total: **221 passed**, zero failures/errors/skips. This is a selected 13-file
  regression run, not the complete repository suite or hardware qualification.
- Mypy: both changed production modules clean. Black: all five changed Python
  production/test files clean. Browser JavaScript syntax check passed.

Both launcher modes passed inert -Check: zero operations, camera/arm
NOT_CONNECTED, preparation NOT_PREPARED, no physical authority, and the confirmed
export folder. All 46 previously indexed native files matched their original
hashes. No capable worker was run.

A copy-only developer delta checkpoint is saved under the confirmed export
directory in developer-checkpoint-camera-probe-scope-20260910-01: this document,
the two production modules, three test files and two final JUnit reports. It is
not a complete source archive, an importable session or hardware authorization.
