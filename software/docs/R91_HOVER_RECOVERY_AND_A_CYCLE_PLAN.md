# r91: recover from A_HOVER and run an A-only ghost-key cycle

Status: the r91 app was installed, read back, and started once on 2026-09-25.
The new boot passed public identity and three-snapshot pose checks; no r91
movement has been sent. This is a finite route to the next useful physical
test, not a claim of keyboard contact or tool-tip accuracy.

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
   startup, explicitly account for possible torque loss: maintain the external
   servo supply, send no torque-off command, and provide a temporary physical
   catch/support at the present pose during the controller reset. Controller
   reset is not the same event as disconnecting the external supply, which
   previously caused a fall, but continuous torque through reset is not
   established for this exact unit. A clear movement area alone is not a
   support, and an uncontrolled gripper strike on the board is not an
   acceptable substitute. Existing r90 credentials/settings remain untouched.
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
  before a bad third-leg receipt, and no retry after a lost second-leg receipt.
  Recovery receipts are now included in the session's delivery-uncertainty
  accounting.
- Added an r91-only board composition. Its recovery adapter permits only the
  three fixed A poses, rejecting B poses, wrong speed/acceleration, missing
  ownership, unhealthy service state, and serial-bus error. The native
  adapter harness passes. Pose observation remains acquisition-only.
- Staged the r91 source tree separately from hash-checked r90 source and app
  inputs. The release stamp is derived from the fixed recovery recipe,
  source hashes and pinned toolchain. Stage export:
  `wizard-20260925T132159536186Z-6178f1d1529945e594e061a3ccef2309`.
- The offline r91 compile succeeded. The app is **1,073,440 bytes** in the
  1,310,720-byte app-only slot. App SHA-256:
  `d69438a1a3483ba6105e2bc5f939dd04c58ee9a197bb28332cb42dc627b7e65f`.
  Source-derived release SHA-256:
  `376f50bb4b372608bbb5eb488229d883fc0ff802cf47b1a53dbccad2cf4942d6`.
  Independent image review checked exact source and stamp hashes, the
  embedded release, recovery and pose-observation route markers, absence of
  the old r90 movement route, and linked entrypoints. Review export:
  `wizard-20260925T132443178692Z-90971789a3914b20852c44a0f0f1920c`.
- The release-pinned live host accepts only that app/release pair, a fresh
  sequence-zero authenticated session and exact boot. It reserves the boot
  durably before start and exports the actual next authenticated sequence
  with each leg. Construction does not touch the device.
- The new read-only install preflight verified the archived full-flash and
  protected-filesystem backups, r90 installation journal, exact r91 image,
  and current public r90 capabilities. Current controller boot remains
  `2d4c94e2cfd8ae25a14f3faed903c11f`, already consumed by the r90 first
  leg. It did **not** re-read the predecessor app flash today; the future
  installer must do that before writing. Preflight export:
  `wizard-20260925T132907250068Z-9ae303c968cd476ea4e3eaf351c8a156`.
- Prepared a library-only r91 app installer. Its offline preparation verifies
  the exact r91 and r90 app bytes, release, backups and empty one-use journal.
  Its live function requires an explicit supported-reset argument, exact USB
  adapter and MAC, r90 predecessor flash MD5, partition/filesystem MD5,
  app-only write at `0x10000`, complete app readback, protected-region MD5
  before/after, one reset, a fsynced journal, and no retry. Only preparation
  and the unsupported-reset refusal were tested; the live function was not
  invoked against hardware.
- The related reviewed-hover suite now passes **316 tests**, excluding the
  unrelated r89 installer test whose `scripts` import resolves to an installed
  package during broad collection.
- The prior r90 live preflight is not reusable as-is: it compares historical
  r89 release sources with the current evolving diagnostics tree and fails
  at `Source bytes differ`. The r91 preflight uses the verified historical
  build, installation journal and backup evidence instead; it does not
  silently reinterpret that failure as success.
- At the time of offline preparation, the physical reset strategy, live
  install/startup, fresh source observation, and five-leg trial remained open.
  The dated installation section below supersedes that preparation status.

## Pre-install reset decision (2026-09-25)

The user confirms that the movement area is clear but the arm is **not
physically supported**. Do not invoke `install(..., supported_for_reset=True)`
under that condition. The installer performs a controller download-mode reset
and one startup while keeping the external supply connected; it does not
deliberately release servo torque. The staged firmware's `setup()` likewise
does not send a torque-off command. Those code and wiring facts reduce the
likelihood of the full-supply-loss fall seen earlier, but they do not prove
uninterrupted holding torque through a real reset or flash fault. The
installer's support guard remains in force.

Preferred next action: with the external supply and USB still connected,
place a temporary stable support or soft catch immediately below the lowest
arm assembly at its **current** pose, without lifting, forcing, or changing
joint angles. Keep it clear of cables and the eventual five-leg path; remove
or reposition it only after the new boot's read-only pose and torque checks
and a fresh clearance review. If such a support cannot be placed without
touching the arm or obstructing the path, defer the install and plan a
separate, controlled repositioning procedure.

Do not lower the arm toward the board merely to shorten a possible fall.
The r90 one-use movement route on the then-current boot was consumed. A manual
pose change would invalidate r91's fixed `A_HOVER` source and require a new
read-only baseline, clearance screen, route/release and reviewed image. It
also risks uncontrolled contact during the change. This pre-install decision
did not authorize a reset, install, or movement by itself.

## Installation and startup evidence (2026-09-25)

- The user confirmed a soft catch beneath the arm. External DC and USB were
  kept connected; no torque-off command was sent. The first installer call
  exited before serial access because the active Python lacked `pyserial`.
  The installer was corrected to load the already-pinned esptool tool directory
  before importing its bundled `pyserial` 3.5. Focused tests passed.
- One r91 app-only write then completed at `0x10000`. The installer verified
  the prior r90 image and controller MAC `fc:e8:c0:f8:d5:38`, read back every
  r91 app byte against SHA-256
  `d69438a1a3483ba6105e2bc5f939dd04c58ee9a197bb28332cb42dc627b7e65f`,
  confirmed protected regions unchanged, and issued exactly one startup reset.
  The private deployment journal is retained outside Git.
- Public r91 capabilities returned release
  `376f50bb4b372608bbb5eb488229d883fc0ff802cf47b1a53dbccad2cf4942d6`
  and new boot `2adaa8657729046162db3a8c403a9654`. Movement was not
  authorized by that public endpoint.
- The acquisition-only pose route produced three complete snapshots and a
  terminal record with zero actions. Assessment export:
  `wizard-20260925T134630545997Z-385394bdb89646b7b5d116a842cd1d84`.
  All seven joints reported torque on, unchanged controls, and zero sampled
  position span. Final goal/position counts for IDs 11–17 were respectively
  `2047/2041`, `2093/2095`, `2021/2020`, `2618/2620`, `2197/2199`,
  `2040/2041`, `2047/2047`. This establishes a stable post-reset pose, not
  a continuous torque trace through the reset.
- Before any r91 movement, the temporary catch must be removed or repositioned
  outside the complete modeled five-leg swept volume, and the user must
  confirm the board and cables are clear. Then the live host must independently
  apply its fresh source, health, and clearance gates. No movement has yet
  been sent on this boot.
- Added `scripts/run_r91_recovery_cycle.py` as a boot- and evidence-pinned
  launcher. Its default invocation performs only a public-capabilities GET and
  exports a read-only preflight. It checks the one-use installation journal,
  retained three-snapshot source evidence, exact r91 release/boot and absent
  live-claim marker. Live mode requires both an explicit noncontact-cycle flag
  and a catch-outside-swept-path flag; the controller still independently
  rechecks its source before writing. The preflight ran against the actual
  controller with no movement. The focused r91 suite passes 81 tests.

## Rejected first start and corrected sequencing (2026-09-25)

- After the catch was removed, the r91 read-only preflight passed. The first
  authenticated `start` received a verified non-2xx response. The host stopped,
  exported fault
  `wizard-20260925T135506905728Z-d67f59792812420184e904b5f2fcfa65`,
  and sent no receipt, next leg, retry or servo write. A one-use signed
  sequence-one **GET only** returned `RESERVATION_FAILED|1`; result export:
  `wizard-20260925T135702313279Z-63065a25d9334fcd85a2ea1ea004acb6`.
- Root cause is the same-boot pose capture, not a directional/endpoint error.
  `rocellReservePose()` sets `rocellPoseReserved` and `rocellDiagnosticOwned`
  for the lifetime of the boot. The recovery service's `reserve()` explicitly
  rejects either flag. Thus the acquisition-only post-install capture was a
  valid diagnostic but consumed the exclusive owner needed for movement.
- The live launcher now refuses this boot and any fresh boot with a
  same-boot `pose-observation-<boot>.json` reservation. On a **new** r91 boot,
  it uses the new public boot identity, retains the prior pose export only as
  historical evidence, and lets the recovery owner collect its own three
  fresh source samples before any write. No firmware rebuild or app
  installation is required for this fix.
- Next live sequence: provide the temporary soft catch again for one
  controller-only restart while external DC stays on; verify the new r91
  public boot/release; do **not** call `/rocell/pose/capture`; remove the catch
  from the swept path; run the corrected read-only preflight and then at most
  one one-use recovery cycle. No restart or further movement has been sent
  after this rejection.
- Added a one-use controller-reset launcher for this exact claimed boot. Its
  read-only preflight verified the signed `RESERVATION_FAILED|1` export and
  public r91 identity. The live flag without physical-support confirmation
  correctly refused before serial access and created no reset claim. It keeps
  external power on and sends no torque-off or movement command. The focused
  r91 suite now passes 84 tests.
- The user restored the soft cloth catch, and the exact-boot controller-only
  reset was sent once. Reset result export:
  `wizard-20260925T140230104094Z-7c61adc069d54d2aafa083a1d76ba276`.
  Public r91 capabilities then returned a new boot
  `fd1421c7f4737db0e21fa16e0cdf85eb` with the expected release. The
  corrected read-only movement preflight passed and exported
  `wizard-20260925T140242900468Z-4d20caf1fa1649c3aafbf1277d8a3cae`.
  This new boot has neither a pose-observation reservation nor a movement
  claim. No pose capture, servo write, or movement was sent after reset.
  The cloth remains in place until the user confirms it is outside the
  complete five-leg swept path.
