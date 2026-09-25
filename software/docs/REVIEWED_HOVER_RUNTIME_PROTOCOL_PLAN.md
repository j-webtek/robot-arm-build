# Reviewed hover runtime protocol — implementation plan

Status: **offline contract only; no live runtime-manifest route exists**. The
installed r84 image still contains one fixed five-leg campaign. Do not send
the manifest to its generic Waveshare JSON endpoint or label the offline
preview as a physical movement test.

Release blocker: the current canonical manifest explicitly says
`hardware_access=false` and `motion_authorized=false`, yet the native route
prototype originally would start its movement owner if included in a firmware image.
Those fields are honest for offline previews, not a live authorization
contract. Before any image build, define a separate live-admission envelope
and digest (or versioned manifest) with unambiguous motion authority, require
it in the signed route, and prove offline manifests cannot be started. Do not
deploy the prototype route unchanged.

Interim containment is implemented: the default native route rejects
`RCHM1` before service reservation or movement; the current board seam also
rejects live admission with `LIVE_RELEASE_UNAVAILABLE`. Only a compile-time
simulation variant accepts the offline selector, and
it requires services marked `simulation_only`. The real board adapter is
marked non-simulation. Native tests prove the production-default rejection
and preserve the isolated simulation campaign. This containment alone does
**not** authorize a firmware release.

An offline **v2 live-intent wire contract** is now specified and parsed on
both host and native sides:
`RCHL2:<boot32>:<count2>:<pose-IDs>:<recipe-SHA256>:<release-SHA256>:LIVE_NONCONTACT`.
The host encoder requires an explicit noncontact-motion choice, a nonzero
boot ID and reviewed release digest, and the existing exact recipe validator.
The native parser rejects malformed lengths/case, boot or release mismatch,
unreviewed pose edges, and recipe-digest mismatch through a required verifier
callback. Parsing performs no I/O and grants no authority. The decoded host
result deliberately reports `motion_authorized=false` and
`controller_support_verified=false`. The existing HTTP client permits the old
`RCHM1` start only on loopback, where the simulated-host tests run.

The authenticated native route now parses `RCHL2` in its production-default
mode, checks boot and release against trusted-service values, recomputes the
recipe digest, and only then attempts owner configuration and reservation.
Native fake-service tests cover an accepted one-use selector and wrong boot,
release, recipe, mode, and offline-selector rejection before any write. The
signed-facade test also confirms that the live selector requires a valid
request signature and rejects replay. The
real `ReviewedHoverBoardAdapter` deliberately returns no release digest, so
that route remains closed on the only current board seam. The simulation mode
continues to accept only `RCHM1` with simulation-marked services.

Still required before release: source the expected release digest from an
independently reviewed image/build record (not a caller-supplied echo), wire
it to board services, verify installed app identity on device, retain
exclusive movement-owner selection, add release identity to durable evidence,
and test one-use admission plus export faults on the compiled candidate.
The host HTTP client also does not yet send `RCHL2` to the arm; keep it that
way until the reviewed candidate and trusted release lookup are ready.

The offline `reviewed_hover_release_identity.py` now provides a candidate
review contract for that next step. It derives a release ID from the full
pre-build compile source manifest (excluding only its generated stamp),
toolchain lock, profile, and recipe digest; checks a deterministic stamp's
hash in the compile report; verifies the source bytes, compile-report digest,
app bytes/hash, and presence of the binary release marker; and never reports
deployment authority. The review-backed live-intent encoder consumes that
checked pair rather than a request-echoed release ID. This is exercised only
with synthetic images so far. It does **not** prove the stamp is referenced by
the installed route, that an actual device runs the reviewed image, or that
the candidate passed independent human review. A real staged build, binary
inspection, durable review export, app-only readback, and startup identity
check remain before the board adapter can expose a release digest.

## r85 compile-only integration checkpoint

An isolated r85 source tree was staged from r84. Its shoulder-session include
selects `reviewed_hover_board.h`, which constructs one reviewed-hover
composition using the existing authenticated web facade and admitted seven-
servo acquisition. The board adapter still returns `false` for release
identity, so `start` fails before reservation. The stage changed only
`shoulder_board_session.h` and `air_typing_policy.h` among inherited files,
plus seven new reviewed-hover headers. Other legacy diagnostic routes remain
in the surrounding sketch; this is **not** a complete exclusive-route audit.

The offline r85 build compiled under the default 4 MB/no-PSRAM profile.
Its app image is 1,144,240 bytes in a 1,310,720-byte slot, SHA-256
`e8f8c2f553fd604c05aefd1e917a54323abd3df12044da38123c85d5c2fc9cb9`.
The binary contains `/rocell/reviewed-hover/start` and
`LIVE_RELEASE_UNAVAILABLE` and does not contain the old
`/rocell/air-multi-hover/start` marker. The exact-source/image review is
exported as `wizard-20260925T032055337658Z-bdbd150df0f745d29bd62ab133f41179`;
its compile input is
`wizard-20260925T031915246927Z-86950360cffe4640ad2cf64764a31a05`.
No firmware upload, startup, controller read, or movement occurred. The r85
image is deliberately **not deployable**: its live route is closed, its release
stamp is absent, and it has not passed a whole-image exclusivity or physical
release review.

## r86 narrow-boot offline checkpoint

The isolated r86 candidate inherits r85 and changes only `diagnostic_boot.h`
and `reviewed_hover_board.h`. After Wi-Fi and servo-serial initialization, its
boot selects `registerShoulderSessionRoutes()` once and polls that composition
only. The composition registers the five reviewed-hover routes plus a read-only
`/rocell/reviewed-hover/capabilities` route. The latter explicitly reports
`live_release_available:false` and `motion_authorized:false`. There are no
startup servo commands in this path. The linked ELF contains the reviewed
registrar but no `registerDiagnosticRoutes`, `webCtrlServer`,
`initHttpWebServer`, or `registerHoldDiagnosticRoutes` symbols. Some legacy
route *strings* remain in the image, so a raw binary string scan alone is not
evidence that those routes are active. The source startup path and linked
symbols support narrow route registration; actual on-device HTTP behavior has
not been tested.

The offline default 4 MB/no-PSRAM build produced a 1,058,384-byte app image
in the 1,310,720-byte slot, SHA-256
`5186a02c981053de88f7507fc41328f5c9ffe57bb5527c007556432d1b80e2ef`.
The compile export is
`wizard-20260925T032454876046Z-c4ffe9f4e8c747fb817722a6ee3ce404`;
the exact-source/image and linked-symbol review export is
`wizard-20260925T032836430476Z-b4f987b0876e45cdac3ab259520dccf7`.
`scripts/review_r86_reviewed_hover_boot.py` reproduces the review. No device
connection, upload, startup, or movement occurred. This remains **not
deployable**: the board adapter deliberately withholds release identity, so
live `start` fails closed. The next gate is an independently reviewed release
identity and on-device startup/read-only route check, not a movement campaign.

## r87 stamped offline candidate

The isolated r87 candidate inherits r86 and changes only
`reviewed_hover_board.h`, adding a generated release-stamp header. The stamp
binds the exact pre-build source inventory (543 files), toolchain lock,
default 4 MB/no-PSRAM profile, and the current 16-leg ghost-key recipe digest
`6663ded0b59ae4d5e0a89a048cf23f1e6fe620e791bde497c27799030cdc8f16`.
The source-derived release ID is
`ff943ae5e84c33cbe18975779cd5be586757a5b6b4161c08d25b3b9769dc00ec`.
The read-only capabilities response exposes it as
`stamped_release_sha256`, while still reporting
`live_release_available:false` and `motion_authorized:false`. The board
adapter is unchanged and continues to return `LIVE_RELEASE_UNAVAILABLE` to
live start; a stamp by itself is not permission to move.

The compile-only app is 1,058,528 bytes in the 1,310,720-byte slot, SHA-256
`d9179f0773b207fa209c6edc39b7942c07d014dd0d092dd79b9d389cbbd3776b`.
The compile export is
`wizard-20260925T033348685036Z-79e8711857c141299d49d47d57659253`;
the source/stamp/image pair review export is
`wizard-20260925T033628734682Z-ddbcd69c4b9540cf9d2e4ae39609969a`.
`scripts/derive_r87_reviewed_hover_stamp.py` prints the deterministic stamp,
and `scripts/review_r87_reviewed_hover_stamp.py` checks the pinned pair and
linked registrar exclusivity.
Neither script contacts the arm. This is a generated candidate record, **not
independent release approval, installed-image attestation, or motion
authority**. Before any device test, review the exact r87 delta, verify
source-level startup routing, and decide whether this fixed recipe is the
intended first live campaign. An app-only installation/readback and read-only
startup check would still precede any separate motion admission.

## r88 first-recipe pin, still offline

The r87 review record pinned the 16-leg ghost-key recipe, but the controller
could still accept any other valid reviewed-hover recipe carrying the same
release ID. r88 closes that gap *before* owner configuration or service
reservation: the staged board adapter supplies the fixed recipe digest and
the live route returns `RECIPE_NOT_RELEASED` for another otherwise-valid
recipe. A staged native harness exercises both that rejection with zero
reservation/writes and acceptance of the pinned recipe. The adapter's release
identity method still returns false, so neither recipe can start on r88.

The offline default 4 MB/no-PSRAM r88 build is 1,058,528 bytes, app SHA-256
`80d9a7eb3e574a1d3db7c5c4e8dea0f18ec6983a15e99433b4b6a8f79a35161f`,
with source-derived release ID
`707f550044719fb7461aa076658bd5c00ce4af3fd716038331d1645a1a08b034`.
The compile export is
`wizard-20260925T034109658406Z-fc5e9c41bdf84ec8b6eeb2219dea3516`;
the exact source/stamp/image/pin review export is
`wizard-20260925T034154149453Z-a2d9d9d9fdc048daa039ee5ea924d704`.
`scripts/review_r88_reviewed_hover_pin.py` checks the source delta, pinned
digest, ordering before reservation, compiled image and linked route
exclusivity. This remains **compile-only and not deployable**. No firmware
upload, controller startup, or movement occurred. The next gate is a separate
review of whether and how the verified release identity may be exposed by the
live adapter, followed by installed-image verification and read-only startup
checks before any motion admission.

## r89 live-capable image — installed, no movement yet

The isolated r89 candidate inherits r88 and changes only the board adapter,
read-only capabilities response, and generated stamp. The adapter now returns
the source-derived, nonzero release digest from the compiled stamp rather
than a request value. The route still requires a signed, boot-bound `RCHL2`
selector, the pinned ghost-key recipe, one-use ownership, fresh feedback,
and per-leg export receipts. The capabilities response says
`live_release_available:true` but `motion_authorized:false`: a discovery GET
is not a movement request. Because this candidate would be able to accept a
valid authenticated live start if installed, it must not be treated as a
read-only diagnostic image.

The offline default 4 MB/no-PSRAM r89 app is 1,061,360 bytes in the
1,310,720-byte slot, SHA-256
`89c0d91334ab4362d392a3e3e66433c216d7e1740842dbba1b87881b722236b0`.
The source-derived release ID is
`653729599a9ba29baed5095b3ed156810b38396065a0b6a3a06fe6c7dd74ab1a`.
The compile export is
`wizard-20260925T034619289604Z-68658f0139aa430793f4b8ba5c5345b4`;
the exact source/stamp/image review export is
`wizard-20260925T034728622941Z-f15a2f14fa5847df8340a884d9d53856`.
`scripts/review_r89_reviewed_hover_live_candidate.py` reproduces the offline
review, including the recipe pin and linked route selection. Staged native
tests verify the adapter returns the compiled stamp/recipe and the route
rejects an alternate valid recipe before reservation. No firmware upload,
startup, or physical movement occurred.

The app-only second attempt has now passed full readback and protected-region
verification. The next gate is a bounded, independently reviewed live selector
through the authenticated host workflow. Do not infer physical tool accuracy
from controller counts, and do not send a live `start` as part of a read-only
startup check.

## r89 installation preparation and first pre-write failure

`scripts/deploy_reviewed_hover_r89.py --preflight-only` passed locally. It
reopens the exact r89 review and compile exports, verifies the 1,061,360-byte
app and r84 predecessor hashes, the original dual 4 MB flash backups, and
the reviewed encrypted settings snapshot. The connected Windows USB adapter
enumerates as the recorded COM7 CP210x serial number, and the currently
running arm returned HTTP 403 to a read-only authenticated-route probe,
consistent with an active protected route. Neither observation proves the
installed app hash; the installer will check that on-device before writing.

The dedicated one-use installer permits only `0x10000` app-region flashing,
checks controller MAC/security/flash ID plus r84 and protected-region MD5
before a write, disables automatic block retry, then compares full r89 app
readback and protected-region digests. It journals one startup reset; it has
no provisioning or motion command. Fake-device tests pass for one successful
write/reset and a predecessor mismatch causing zero writes/resets. The
separate `scripts/check_r89_read_only_startup.py` is prepared to validate the
new capabilities boot/release fields and one authenticated `NEW|0` status,
then export a report. It does not send `start`, `prepare`, or `next`.

The first one-use installation attempt was made after the user's repeated
authorization to proceed with the supported, clear, powered setup. It stopped
in ESP32 ROM synchronization: download mode was detected, but there was no
sync reply. The deployment journal contains only `RESERVED` and `STOPPED`;
`IDENTITY_AND_PREWRITE_VERIFIED`, `WRITE_ATTEMPT_STARTED`, `FLASH_VERIFIED`,
and `STARTUP_RESET_SENT` are absent. No flash write or movement command was
sent. The failed journal is preserved at
`private-backups/controller-20260918-session1/app-r89-deployment-events.jsonl`
with SHA-256 `3b4fdaddfbb3ea427d062a2e378f9c9eaa4e47ef2de16e2a0b5f5137b865f33a`.
The verified failure export is
`wizard-20260925T035959888074Z-9fc542198d0f4c55b23a9a9e907208e8`.
The exact-journal, no-device exporter is
`scripts/export_r89_prewrite_failure.py`.

After that failure, COM7 still enumerated, while Wi-Fi did not respond. A
separate one-use recovery reset, guarded by the exact failed-journal hash and
adapter identity, was sent using
`scripts/recover_r84_after_r89_connect_failure.py`; its verified export is
`wizard-20260925T040058555862Z-6e5ccccf721446f78a4dd4e10771cd45`.
The protected Wi-Fi route then returned HTTP 403, consistent with an active
application, but this is **not** proof of its on-device hash or servo pose.
There was no installation retry, reflash, or movement target. The prior r84
image is the last verified installed image; r89 is not installed.

The installer now has a separate, opt-in second-attempt path. Its local
`--preflight-second-attempt` passed without opening hardware or reserving a
journal; it verifies the exact first-failure hash and recovery export and
reserves a distinct journal only in authorized mode. Its two fake-device
tests pass: a matching predecessor writes/reads back once, and a predecessor
mismatch writes nothing. This is preparation, **not** a second deployment.
The workstation still enumerates the pinned COM7 CP210x adapter, and the
protected Wi-Fi route responds with HTTP 403. Historical r27, r42, r64, and
r69 deployment journals show the same pre-write no-sync failure followed by
successful, separately journaled second attempts. That history supports a
bounded second attempt, but it does not identify the present serial failure's
root cause or prove the arm's physical pose/clearance.
Before using `--authorized-second-attempt-app-only-and-startup`, assess the
intermittent ROM sync path and verify physical support/clearance again because
a bootloader reset may release torque. The new attempt must still repeat
controller identity, predecessor, and protected-region checks before writing.
The host HTTP client also still blocks live `RCHL2` starts, so a successful
future installation/read-only startup would not silently begin the
ghost-key campaign.

## r89 second attempt and startup — 2026-09-25

The distinct second-attempt journal is
`private-backups/controller-20260918-session1/app-r89-attempt2-deployment-events.jsonl`.
It records the pinned MAC and pre-write predecessor/protected-region checks,
one app-region write, full readback SHA-256
`89c0d91334ab4362d392a3e3e66433c216d7e1740842dbba1b87881b722236b0`,
unchanged protected regions, and one startup reset. The installer exited
successfully. No movement, settings write, provisioning, or automatic retry
was sent.

The fresh capabilities GET reported boot ID
`0b31699b215fb45a4f9d13afbfbe6310`, the expected compiled release digest,
`live_release_available:true`, and `motion_authorized:false`. One signed,
read-only status GET returned `NEW|1`. The startup checker initially marked
this as a failure because it incorrectly expected `NEW|0`. The native owner
starts with `leg_=0` but reports `leg()+1`, making `NEW|1` the correct idle
status; no campaign has been reserved. The original verified capture is
`wizard-20260925T112230268400Z-d2cc89a69c314fe880f1d17d5eb271a1`.
`scripts/check_r89_read_only_startup.py` now expects `NEW|1`, and the
offline-only correction review, with no additional signed request or hardware
access, is
`wizard-20260925T112402757756Z-e4fb5e9ddb13490f910e12b31c1a0e45`.
The focused installer/adapter/release test set passes (15 tests).

The next step is to review and exercise host `RCHL2` admission in simulation
and inspect the current read-only pose against the approved A-clear source
before sending any first live start. This installation alone proves neither
servo movement nor spatial typing accuracy.
The startup status GET consumed signed sequence zero for this boot. The
one-shot checker process has exited; `CharacterizationHTTP` intentionally
allows a resumed sequence only for GET requests, and its default mode rejects
live `RCHL2` starts on a non-loopback address. Do not create a fresh sequence-zero
writer against this boot or bypass that guard. A future live runner must
either establish a fresh boot-bound session or implement and test explicit
sequence reconciliation before any movement admission.

An acquisition-only pose capture was attempted on this same boot using
`scripts/run_r89_pose_observation.py`. Its local preflight passed and the
current capabilities boot matched, but the capture failed before a queued
response or snapshot was retained. The one-use export is
`wizard-20260925T112858157635Z-68a2f561f2894ad8bfd36ff2648a344a`:
`INCONCLUSIVE`, `ValueError`, zero response records, no progression authority.
The `pose-observation-<boot>.json` marker was consumed; no POST retry or
movement was sent. A subsequent read-only record GET returned HTTP 404,
which does not distinguish a missing route from a route with no retained
record. Do not call the current pose measured or use this failed capture to
admit motion.

`CharacterizationHTTP` now has an opt-in `reviewed_hover_live_release_sha256`
transport mode. It accepts only a fresh sequence-zero session and an exact
`RCHL2` body matching boot, release and the pinned 16-leg ghost-key recipe;
the default still blocks non-loopback starts. This is host-side framing only,
not by itself movement authorization. `ReviewedHoverLiveHost` now uses that
framing in a one-use runner: it writes and verifies an intent export and
atomically claims the boot before a start, enforces a fresh authenticated
sequence-zero client, verifies each raw leg record, exports it durably before
its receipt, then advances only on an authenticated response. It retains a
fault export and forbids retry/next after corrupt records or uncertain receipt
delivery. Loopback tests cover all 16 legs, corruption at leg 8, lost receipt
at leg 8, duplicate boot claim, and constructor permission/session rejection;
the focused HTTP/admission/loopback/pose test set passes (44 tests). No live
runner CLI or controller movement was executed. Next bind the runner to
verified installation/release artifacts and a **fresh** boot, and assess the
current source pose/clearance before any physical start. The current boot and
failed pose capture must not be reused for that test.
The wider reviewed-hover unit selection passes: 236 tests.

## Live-launch preflight and pose diagnostics — 2026-09-25

`scripts/preflight_r89_live_campaign.py` now independently replays the reviewed
source/image release, verifies the successful second-attempt installation
journal and read-only startup review, and reads only public current-boot
capabilities. It labels software readiness separately from physical clearance,
source-pose proof, and motion authorization. The current boot
`0b31699b215fb45a4f9d13afbfbe6310` is correctly rejected: it is the prior
observed boot and has both a signed-status marker and the consumed pose-capture
marker. Its verified read-only preflight export is
`wizard-20260925T113952804155Z-cf14fb2f2d4049d3884e20641702d996`.
No live session or movement request was created. The pure boot/claim and
capabilities tests pass.

The pose capture exchange now distinguishes an HTTP rejection by status code
without retaining arbitrary response text, and `capture_pose` exports that
bounded status. The original r89 capture remains inconclusive and cannot be
retried on its boot; the code change does not retroactively determine its HTTP
response. The combined reviewed-hover, r89 preflight, and pose-capture unit
selection passed (246 tests) before the next attempt.

### Fresh-boot acquisition attempt and route diagnosis

`scripts/reset_r89_for_pose_observation.py` verified the installed app/journal,
old boot and COM7 adapter, exported a one-use intent, then performed exactly
one startup reset without flashing or sending a movement target. Reset export:
`wizard-20260925T114424765909Z-0306d824772049bcbafc0f56069145c3`.
Public capabilities then showed fresh boot
`214bd3293ae53c6b40e50156b241f151`, the pinned r89 release, and
`motion_authorized:false`. The updated pose runner bound the attempt to this
reset record and current boot. Its single acquisition POST returned **HTTP
404** before a queue response or any snapshot. The one-use result is
`wizard-20260925T114529494205Z-a62d81e5d3394c3990fd85a16690ae59`:
`INCONCLUSIVE`, `PoseHTTPStatus`, status 404, zero response records, no
progression authority. No retry, servo command or firmware write occurred.

`scripts/review_r89_pose_route_failure.py` cross-checked the installed app
hash, linked ELF symbols and staged boot entrypoint against that HTTP result.
The r89 image links `registerShoulderSessionRoutes()` but **does not link**
`registerPoseObservationRoutes()` or the broader diagnostic registrar; its
binary contains the reviewed-hover route marker but neither pose route marker.
The pose source code and conditional registration exist in the staged tree,
but `diagnostic_boot.h` selects the reviewed-hover registrar alone. This is
a controller-image route-composition error, not evidence that a servo refused
to report its position. Verified offline review:
`wizard-20260925T114757641449Z-9e0eae959f794d8a884891b1902b59c8`.

Do not spend another boot attempting `/rocell/pose/capture` on installed r89.
For the next candidate, preserve the **single movement owner** and add an
acquisition-only, exclusive seven-servo source-pose path to that selected boot
composition. Verify at source, linked-symbol, binary-string, and HTTP levels
that the exact route is present, with negative tests for accidental duplicate
movement-owner registration. Recheck memory headroom and one-use bus exclusion;
compile and review the new image independently before an app-only install.
Then acquire the seven-joint pose, compare fresh goals/positions/torque with
the `A_CLEAR` source window and real clearance, and only after that consider
a separate fresh-boot reviewed-hover campaign. No r89 campaign movement has
yet been sent.

### r90 offline repair candidate — compiled, not installed

`scripts/stage_r90_pose_hover_composition.py` verified the r89 installed
image and exact compiled predecessor source, then staged a separate r90 tree.
Only `diagnostic_boot.h` and the generated release stamp differ. The active
boot now registers the existing pose-observation owner/routes after the
reviewed-hover owner and polls pose acquisition in the same loop; it fails
startup if either pose allocation fails. The two reservation directions are
exclusive: reviewed-hover services reject an already reserved pose owner,
and the pose owner rejects an already reserved reviewed-hover owner. The
pose path defines no servo write. Stage export:
`wizard-20260925T115135790589Z-58de5734b2394a18aad26c7238621742`.

The r90 default 4 MB/no-PSRAM compile succeeded, with app SHA-256
`f3d5705b16eedfd49b11fec668da1709eee71d50345ceb07eadf26f0384fe129`
and source-derived release SHA-256
`65f0106f05de4e8edf68fbd7729a807ebab179c4b86b9e5e37bba5dca9d7a538`.
The 1,074,080-byte app fits the 0x140000-byte slot; the toolchain reports
88,512 static RAM bytes (the same as r89), leaving 239,168 bytes before
runtime allocation. Compile export:
`wizard-20260925T115330774418Z-399cdfe58f7441d3af02d1584ceddfe1`.
`scripts/review_r90_pose_hover_candidate.py` independently checked the
source/stamp/image pairing, linked pose register and poll symbols, both pose
HTTP markers, the reviewed-hover route marker, and absence of the legacy
diagnostic/web registrars. Review export:
`wizard-20260925T115402595189Z-52243d92ed6a4a9fb9d235b5236d2bf6`.
Nineteen focused native/host tests passed. These are compile and source
findings, not a runtime route or feedback test; r90 has **not** been uploaded.

`scripts/preflight_r90_pose_hover_install.py` then reverified the r90
candidate review, app slot bounds, installed r89 predecessor, two matching
full-flash backups, protected filesystem/settings snapshot, and absence of
an r90 attempt journal. Its local-only export is
`wizard-20260925T115700940388Z-1ebe22ad3b1c463898ef69fcb5d7c06b`.
A separate public-capabilities GET confirmed that the reachable controller
still reports the r89 release on boot
`214bd3293ae53c6b40e50156b241f151`; read-only device preflight export:
`wizard-20260925T115708377445Z-3df2321a92c44ae2886e80f0027c4cc3`.
Neither preflight opened USB, uploaded firmware, nor sent movement. Runtime
memory allocation and actual HTTP route availability remain unproved.

Next: review the offline and read-only preflight evidence immediately before
any installation. If installation is chosen, journal and verify one app-only write and one
startup; preserve settings and credentials. Then GET public capabilities and
probe the pose record route read-only to distinguish it from a generic 404,
before a single one-use acquisition POST. Confirm fresh seven-joint samples
and `A_CLEAR` source compatibility. Do not send reviewed-hover movement on
that same pose-claimed boot; a separately verified fresh boot is required.

### r90 installation and first source-pose capture — 2026-09-25

`scripts/deploy_r90_pose_hover.py` passed local preflight and two fake-flash
installer cases. Its first invocation failed at Python import resolution,
**before** USB access or journal creation; the script/package entry points
were corrected, retested, and preflighted again. The one actual installation
attempt is journaled at
`private-backups/controller-20260918-session1/app-r90-deployment-events.jsonl`.
COM7 serial identity, controller MAC `fc:e8:c0:f8:d5:38`, flash identity,
installed r89 app, partition table, and filesystem digest matched before
the write. A single app-only write at `0x10000` was followed by full
1,074,080-byte readback, SHA-256
`f3d5705b16eedfd49b11fec668da1709eee71d50345ceb07eadf26f0384fe129`,
unchanged protected-region MD5 values, and one startup reset. No provisioning,
settings/credential write, or servo target was sent.

The restarted controller reported boot
`581cdc3cb1f82fb2da9bf57afe5b3564` and r90 release
`65f0106f05de4e8edf68fbd7729a807ebab179c4b86b9e5e37bba5dca9d7a538`.
Before acquisition, `GET /rocell/pose/record?index=0` returned the route's
specific `POSE_RECORD_UNAVAILABLE` JSON, proving runtime registration rather
than a generic missing-route 404. Verified startup preflight:
`wizard-20260925T120540298366Z-d37ac5e0c2854a4e9ad907d5bccf9510`.

One acquisition-only request was queued and yielded three fresh seven-joint
snapshots plus a terminal record. Capture export:
`wizard-20260925T120550111405Z-39d8a760eafe4ae5a01fa0832819d337`;
raw/assessment replay export:
`wizard-20260925T120550061669Z-9ac8186080ac4fd3906eb16aa21b1c18`.
`scripts/review_r90_source_pose.py` replayed the records and verified that
servo IDs 11–17 all have the exact `A_CLEAR` goals, unchanged controls,
torque on, and zero position span across the three snapshots. Position
difference from the controller's reviewed source values is 0 counts for six
joints and +1 count for joint 11, within the 3-count source window. Review:
`wizard-20260925T120659583576Z-07fd100e64354ea597d0773dfceac3d3`.

This proves a stable **servo-joint source state**, not stylus-tip location,
physical board clearance, or typing accuracy. Pose acquisition consumed this
boot's one-use bus claim: no reviewed-hover movement may be started on the
same boot. Next build and test the r90-specific live host binding; then,
with the physical area still clear, make one separately journaled fresh
startup and run preflight against its new boot before any allowlisted motion.

The live host now accepts the exact r90 app/release pair as an explicit
alternative to r89, with that pair carried into its admission body and
durable intent. A complete 16-leg r90 loopback run passed alongside the
existing r89 tests; no controller live start was sent. The read-only
`scripts/preflight_r90_live_campaign.py` replays the installed image and
source-pose evidence and correctly rejects the **current** boot because it
contains `pose-observation-<boot>.json`; export:
`wizard-20260925T121104317927Z-bf72ace4086d4f51b2382d061e2e7681`.
It preserves the distinction between last-boot joint-source evidence and
current-boot proof. A new boot remains necessary before the first live leg.

## Why this change

The r81–r84 tests established fresh servo-feedback acquisition, finite
one-use movement, per-leg verification, durable exports, and stop-on-fault
behavior. Changing the target list still requires an app-only flash. For
repeated ghost-key experiments, that couples every test design change to
firmware deployment. The next interface should keep firmware stable while
allowing a small, reviewed, bounded sequence to be loaded for one boot.

The first application is the noncontact A/B ghost-key proposal in
`ghost_key_multitarget_recipe.py`: 16 legs, two repeated cycles, using only
six named poses (A/B clear, hover, virtual downstroke). The model-only preview
is `wizard-20260925T021445026561Z-b90703eb95f64348be910cffedb1a70d`.
Minimum modeled TCP Z was 73.56 mm and modeled link-axis separation 55.75
mm. Those values omit the tool, cables, board registration, and physical
clearance. No stylus or contact is authorized.

## Contract boundary

The host-side `reviewed_hover_manifest.py` currently validates an exact v1
manifest: up to 16 pose IDs, speed 20 counts/s, acceleration 1, one-use per
boot, export-before-next, and a fixed A-clear source. It rejects arbitrary
goals, disallowed A/B transitions, unchanged targets, goal jumps below 10
or above 60 counts on selected joints, unknown fields, and policy changes.
Its result is marked `OFFLINE_MANIFEST_VALID_NOT_EXECUTABLE` and
`controller_support_verified=false`.

Controller implementation must **independently** enforce the same finite
pose table and edge graph; the host validator alone is not a safety boundary.
It should accept only the ordered pose IDs and fixed policy fields, not raw
servo counts or free-form JSON commands. A reviewed future envelope change
can expand the table, but should not silently widen this v1 protocol.

The native structural validator at
`firmware/diagnostics/reviewed_hover_manifest.h` has the same six-pose
table, allowed edges, 10–60-count selected-joint step rule, and 16-leg cap.
Native/Python parity and rejection tests pass. An **offline-only** owner
prototype now exists at `firmware/diagnostics/reviewed_hover_owner.h`. It
retains the manifest and boot binding in fixed-size RAM, checks fresh source
and endpoint feedback, allows one write per leg, seals a binary leg record,
and gates every next leg on a matching export digest receipt. Its native
harness covers all 16 legs and injected failures on every leg. It is **not**
compiled into the installed controller image; no live bus adapter or hardware
validation exists. An isolated exact-route prototype at
`firmware/diagnostics/reviewed_hover_routes.h` now requires an authenticated
web facade, parses only fixed pose IDs, independently hashes the canonical
manifest, and gates record/receipt/next requests. Its simulated 16-leg route
harness rejects malformed starts, wrong digests, unauthenticated calls,
out-of-order receipts, and replay. A separate native composition test routes
requests through the existing signed-request web facade and rejects missing,
wrong-path, and replayed signatures. It uses deterministic test crypto; it
does not establish production key provisioning or deployed security. This is
**not** wired to the installed firmware, live bus, or host socket transport.
The matching host start-body encoder is `encode_reviewed_hover_start`.
The separate host verifier at
`src/rocell/application/reviewed_hover_record.py` now decodes the exact
1,163-byte native record and independently checks boot/manifest/leg binding,
seven-joint source and endpoint evidence, freshness, direction, and residual
limits. `reviewed_hover_offline_campaign.py` durably exports a verified
record before producing a **simulated** receipt value. It has no transport
and does not transmit a receipt or authorize movement. Separately,
`reviewed_hover_simulated_host.py` exercises the complete signed-request,
signed-response and 16-leg export-before-receipt sequence against an injected
simulation-only transport. It stops on a corrupt record, bad response
signature, failed export, or uncertain receipt delivery. A lost receipt reply
is recorded as possibly having authorized continuation, with no retry or next
request. It has no socket or live controller adapter. The existing
`CharacterizationHTTP` socket client now has an exact reviewed-hover route
allowlist and validates the complete start body before any connection.
Loopback-only tests cover signed start/status/record/receipt/next exchange and
a lost receipt reply that latches the client closed. The
`ReviewedHoverLoopbackHost` now runs the complete 16-leg coordinator over
those real loopback sockets with native-format records: success, corrupted
leg, and lost-receipt cases pass. Its constructor rejects non-loopback IPs
and already-used sessions. No arm address was contacted.

The installed r84 composition was inspected read-only. Its
`LargePoseReliefRoutes` aliases the older fixed `AirTypingRoutes`, and its
single-task poll loop gives the selected route exclusive ownership. The new
reviewed-hover route is **not** present in that image or composition. A future
candidate must replace/select one movement owner at build time; merely
registering another route alongside r84 would risk competing poll owners.
An offline `reviewed_hover_composition.h` now assembles only the existing
signed-request facade and reviewed-hover routes. Its native test confirms
exactly five reviewed-hover endpoints, no legacy movement endpoint, and no
write from idle. It is not wired to board services or an app image.

The offline `reviewed_hover_board_adapter.h` now delegates reservation,
ownership, health, heap admission, and raw seven-servo sampling to the
existing characterization services. Its separate write seam accepts only
the six reviewed goal vectors, fixed speed 20 and acceleration 1, an idle
bus, and an owned healthy service, then broadcasts one seven-servo command
with IDs 11–17. A fake-bus native test covers all six rows and rejection of
altered goals, lost ownership/health, bad speed/acceleration, busy bus, and
uncertain delivery without an adapter retry. This is a source-level seam,
not proof of actual board wiring, compiled firmware, or physical movement.

## Proposed controller state machine

1. Boot idle. Reject a manifest unless the authenticated session, fresh
   boot ID, current app identity, stable source goal/position window, and
   durable host export capability match the reviewed release.
2. Validate the complete manifest before any movement: schema/length,
   allowlisted pose IDs and edges, every selected-joint displacement,
   speed/acceleration, total command/time budgets, and no repeats beyond
   the 16-leg cap. Retain the manifest digest in RAM only. No filesystem or
   servo settings change.
3. Reserve one-use admission bound to boot ID and manifest digest. Reject
   reconfiguration, second start, or restart/resume on the same boot.
4. For each leg, acquire three fresh seven-joint source samples, verify all
   goals, positions, torque, motion state, timestamps, and raw feedback.
   Recompute the selected joints from the next allowlisted target.
5. Perform one fresh prewrite scan, issue exactly one synchronized write at
   the fixed speed/acceleration, then retain command-correlated endpoint
   samples. Fault on delivery uncertainty, wrong goal, stale/invalid data,
   excessive travel, unexpected direction, passive-joint motion, loss of
   settling, or a missed deadline. Do not auto-return or retry.
6. Seal a leg record containing boot ID, manifest digest, leg index, source,
   target, command timestamp, and raw before/prewrite/after samples. Wait
   for the host to independently verify and durably export the record.
   Advance only after an authenticated receipt of its digest.
7. Complete after the last receipt. Expose terminal state and a bounded
   read-only fault record. A stopped sequence cannot start again on the same
   boot. Stopping progression does not imply torque-off or cancellation of
   an already accepted servo target.

## Implementation order and acceptance

1. Freeze and review the A/B pose table, graph, source window, binary record
   schema, and protocol wire format. The current Python contract and offline
   preview are the source material, not yet a controller release. The native
   record prototype is binary `RCHOVERR01` with boot ID, manifest digest,
   leg/pose ID, selected wrist goal, timestamp, write count, and seven raw
   feedback captures; host verification is now implemented offline.
2. Build on the native structural validator with a C++ owner using volatile
   fixed-capacity manifest storage and exact route parsing. The owner
   prototype, exact route parsing, a single-owner signed-web-facade
   composition test, and a fake-bus reviewed-hover adapter test are done
   offline. Real key/session provisioning, board-global wiring, image-level
   exclusive bus ownership, and an actual compiled-device feedback/write
   test remain.
   Keep the existing one-use owner operational
   while testing; do not replace it in place without regression coverage.
3. Test success plus injected failure at **every leg** for source drift,
   stale feedback, wrong endpoint, write uncertainty, evidence loss,
   timeout, duplicate/reordered receipt, wrong manifest digest, and boot
   replay. The native harness covers source drift, stale feedback, wrong
   endpoint, write uncertainty, evidence loss, timeout, record-hash failure,
   expired/incorrect receipt, and one-use behavior across all 16 legs.
   Manifest-digest mismatch and same-boot route replay are now covered in the
   isolated route harness; a signed-request composition test also rejects
   missing, wrong-path, and replayed signatures. The Python simulated host
   verifies signed responses, including tampering and lost-receipt ambiguity.
   Real crypto in the native route harness and cross-boot replay tests remain.
   Prove zero extra writes and no retry in every fault case.
4. Add an authenticated host transport and independent raw-record verifier.
   The raw verifier and simulation-only export/receipt-value workflow are
   implemented and tested, including wrong binding and corrupted-leg fault
   export. The signed simulated-host workflow now verifies durable export
   before sending each simulated receipt and persists fault evidence on
   transport or export failure. The existing authenticated socket client can
   now frame and verify the new routes, and the full coordinator passes over
   loopback sockets. Actual controller receipt delivery, real source
   provenance and exclusive ownership remain. Validate export receipt before
   `next`; persist a fault bundle even when progression stops.
5. Build once, review exact source/image hashes and protected regions, then
   install app-only. Read-only startup checks precede any movement. Start
   with a short A-only subset of the allowlisted recipe, then expand to the
   full A/B two-cycle campaign after its endpoints and exports pass.
6. Compare the second cycle to the first by pose and approach direction.
   Report controller counts separately from modeled TCP location. No
   millimeter/key-press claims until tool and board registration are measured.

This design preserves the tested diagnostic semantics while removing the
need to compile a new app for every ordering or repetition of the same
reviewed A/B poses. New poses, speeds, or physical contact remain separate
review decisions.

## 2026-09-25 r90 first live leg

- Installed r90 app/release identity was verified and a single no-motion
  startup produced boot `2d4c94e2cfd8ae25a14f3faed903c11f`. The read-only
  preflight found no claim on that boot; source pose had been verified on the
  preceding boot, while the controller's live start retained responsibility
  for fresh source/prewrite checks.
- Added `ReviewedHoverLiveHost.run_first_leg_only()` and
  `scripts/run_r90_first_live_leg.py`. The one-use host reserves an intent,
  starts the exact reviewed 16-leg manifest, verifies and exports leg 1, and
  deliberately does **not** send an export receipt or `next`. Loopback tests
  prove this stop point and a bad-record fault without continuation.
- The one authorized live start reached `A_HOVER` on leg 1. Its record reports
  targets `[2047,2093,2021,2618,2197,2040,2047]`, final positions
  `[2041,2094,2020,2620,2199,2041,2047]`, and final goals equal to targets.
  Selected joints 1–4 differed from target by `[+1,-1,+2,+2]` counts.
  Export `wizard-20260925T121557873142Z-099dc9733cc44ccb9c46709bf267c7ca`
  verified successfully. No receipt or later-leg admission was sent. This is
  controller feedback, **not** measured end-effector or key accuracy.
- A subsequent signed read-only status query attempted at presumed sequence 3
  failed response-sequence verification. It sent no movement, receipt, or
  `next`, and was not retried. An unsigned capabilities read still showed the
  same boot. Offline review found the host polls status a variable number of
  times before fetching the record; sequence 3 was an unsupported guess, not
  evidence of a controller movement failure. The first-leg result and verified
  assessment export now include the *actual* authenticated next sequence,
  tested with extra status polls. The prior live export predates that change,
  so its current authenticated sequence remains unknown. Do not resume this
  boot or probe candidate sequence numbers.
- Before another campaign: establish a new boot with physical support through
  any startup torque interruption, capture the current pose read-only, and
  determine a reviewed bounded path back to `A_CLEAR` if still at `A_HOVER`.
  Only then start a new one-use manifest. A larger A-only or A/B campaign must
  retain export-before-receipt at every leg and distinguish controller counts
  from actual tool-tip position.
- The host now has an offline-tested four-leg `A_HOVER → A_DOWN → A_HOVER →
  A_CLEAR` stop mode and a separate `run_r90_a_cycle.py` launcher. Thirteen
  authenticated loopback tests pass, including variable status-poll counts and
  a stop with three verified receipts but no fourth receipt or fifth-leg
  command. **This four-leg mode has not run on hardware.** Its launcher rejects
  the consumed current boot; do not interpret it as permission to reset or
  move from the present A_HOVER pose without the startup/source review above.
- The installed r90 boot does not expose the normal `/js` readback route (T105
  returned 404 twice), and its diagnostic `loop()` polls only the exclusive
  pose and reviewed-hover owners. A reset would not change the r90 source
  policy from `A_CLEAR`. The next viable software route is the separate
  [r91 A_HOVER recovery and A-cycle plan](R91_HOVER_RECOVERY_AND_A_CYCLE_PLAN.md):
  a fixed, fresh-source-verified recovery leg followed by four A-only legs,
  with full export/receipt gates. The fixed policy and fake-bus five-leg owner
  now pass offline tests; signed route, host, image composition and live
  deployment remain. It has not been built or deployed.
