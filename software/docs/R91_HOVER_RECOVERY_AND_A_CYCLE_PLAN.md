# r91: recover from A_HOVER and run an A-only ghost-key cycle

Status: offline recipe, native owner-policy/signed-route harness, authenticated
client allowlist, and independent raw-record verifier implemented; no r91
image built, installed, or authorized. The installed r90 image is unchanged.
This is a finite route to the next useful physical test, not a claim of
keyboard contact or tool-tip accuracy.

## Why a new route is needed

The r90 live first leg finished at `A_HOVER` and exported verified seven-servo
feedback (`wizard-20260925T121557873142Z-099dc9733cc44ccb9c46709bf267c7ca`).
The host deliberately sent no receipt or `next`. Its exact authentication
sequence was not persisted in that release of the host, so do not guess a
sequence or continue the consumed boot. Public capabilities still identify the
same boot. The installed r90 diagnostic boot polls only the pose-observation
and reviewed-hover owners; its normal JSON control loop is not active. Two
read-only `/js` T105 requests returned HTTP 404. The existing reviewed-hover
manifest requires `A_CLEAR` as its source, so a reset alone cannot make a
valid `A_HOVER`-to-`A_CLEAR` command.

## Exact proposed physical sequence

Current endpoint evidence: `A_HOVER` goals
`[2047,2093,2021,2618,2197,2040,2047]`, last positions
`[2041,2094,2020,2620,2199,2041,2047]`. Fresh feedback, not this old
position vector, must decide admission after startup.

The new one-use recipe starts from `A_HOVER` and has exactly five legs:

1. `A_CLEAR`: `[2047,2075,2039,2600,2233,2040,2047]` (recovery).
2. `A_HOVER`: `[2047,2093,2021,2618,2197,2040,2047]`.
3. `A_DOWN`: `[2047,2105,2009,2630,2173,2040,2047]` (virtual downstroke;
   no physical contact or stylus).
4. `A_HOVER`: same as leg 2.
5. `A_CLEAR`: same as leg 1, a useful parked endpoint.

The recovery step changes only joints 12–15 by `[-18,+18,-18,+36]` counts;
the other legs use previously reviewed A-only edges. Fixed speed 20 and
acceleration 1, one synchronized seven-servo write per leg, no arbitrary
targets. Verify modeled sweep/board clearance again from the **fresh** source
before live admission; the old offline meshless preview is not a physical
clearance measurement.

The first offline candidate is implemented in
`src/rocell/application/reviewed_hover_recovery_recipe.py` and has two passing
unit tests. Its 101-sample-per-leg URDF screen, seeded by the last recorded
endpoint, found minimum modeled hand TCP heights of 76.6, 77.5, 73.6, 73.6,
and 77.5 mm for legs 1–5, and a 55.8 mm minimum modeled link-axis separation.
This is only a meshless model screen: it does not account for the actual board,
gripper, cables, support, or position drift since the saved endpoint.

## Implementation and evidence gates

1. Create a separate r91 fixed manifest and release identity. Do not mutate
   r90's pinned recipe or reinterpret its 16-leg digest. Reject any unknown
   pose, edge, speed, acceleration, length, or source binding.
2. Reuse the native seven-joint sample, prewrite, endpoint, record, signed
   transport, and export-before-receipt machinery. A dedicated r91 source
   policy requires three fresh stable samples: all seven expected *goals*,
   valid feedback/torque, no moving flags, bounded position-to-goal residuals,
   no unexpected passive-joint drift. Treat the r90 last positions as a
   comparison reference, not a command or substitute for fresh samples.
3. Start with an isolated native fake-bus harness: five successes, then fault
   injection at source, prewrite, write, endpoint, export, receipt, and next.
   Assert zero writes before admission, at most one write per leg, and zero
   further writes after a fault or lost acknowledgement. Test servo-limit and
   modeled-sweep rejection with malformed and extreme inputs.
4. Add a host runner bound to the exact r91 image/release and fresh boot. For
   each leg: independently verify the complete raw record; durably export it;
   persist the **actual** authenticated next sequence; only then send the
   matching receipt. Stop at leg 5 with no continuation route.
5. Compile/review the image, app-only flash boundary, settings/credential
   preservation and readback hashes offline. Before any installation or
   startup, explicitly account for brief torque loss: the arm must be in a
   position where a reset cannot let it strike the board, or physically
   supported for that interval. Existing r90 credentials/settings remain
   untouched.
6. After one reviewed install/startup, use read-only identity/capability
   checks. Start r91 only if source, clearance and health gates pass. Export
   all five endpoints and report controller counts, timing and faults. Do not
   infer millimeter or key-press accuracy without a mounted tool/camera and
   board registration.

## Stop conditions

No blind source re-home, sequence guessing, firmware retry, automatic return,
or fallback to raw T102. A controller source rejection, unexpected motion,
invalid/stale feedback, wrong final goal, export failure, or lost signed reply
ends the campaign. A new boot is a new physical event, not a software-only
retry.

## Implementation progress

- Added the exact fixed recovery source/pose policy in
  `firmware/diagnostics/reviewed_hover_recovery_policy.h`. It only accepts
  `{A_CLEAR,A_HOVER,A_DOWN,A_HOVER,A_CLEAR}` from `A_HOVER`, requires the last
  recorded endpoint envelope plus three fresh stable samples, and rejects
  wrong goals, missing torque, moving flags, excess drift, out-of-order
  advancement and mismatched endpoint goals.
- The existing reviewed-hover owner is now policy-parametric while retaining
  the original `ReviewedHoverOwner` alias. The recovery policy runs through
  the same one-write/leg, prewrite, settled-endpoint, export-record, receipt,
  and one-use state machine. An intermediate next-leg indexing regression was
  caught and corrected by the existing native suite before completion.
- The fake-bus recovery owner passes a five-leg success case and 45 injected
  failures (nine fault classes at each leg), checking that no extra write or
  retry occurs. The combined related suite has **219 passing tests**.
- Added a separate `/rocell/recovery-hover/` signed native route with an exact
  boot/recipe/release-bound admission body. The route uses the five-leg
  recovery policy, cannot be confused with the r90 route, and rejects wrong
  path, release, boot, recipe, replay, and sixth-leg requests in native tests.
- The authenticated Python transport now has an exclusive recovery-release
  opt-in. It validates exact start, receipt, and next bodies before network
  I/O, rejects sequence-resumed writes, and preserves no-retry latching. Its
  loopback signed exchange and negative cases pass.
- The independent host verifier parses the native 1,163-byte seven-servo
  record and checks each leg's binding, chronology, source continuity,
  selected-joint travel, passive-joint drift, and endpoint residual. All five
  synthetic native records pass after binding their fixed recipe digest;
  altered boot, leg, target, and feedback bytes fail.
- A simulation-only five-leg host runner reuses signed no-retry progression,
  checks each independent raw-record assessment, and durably exports before
  each matching receipt. Its tests verify five successful receipts, fault-stop
  before a bad third-leg receipt, and no retry aft