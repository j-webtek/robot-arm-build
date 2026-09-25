# Static-camera original design contract

2026-09-08. This API checks design consistency, not received hardware,
installation, optical calibration, identity or native activation. It neither
creates an M1 store nor mutates a stage. The original-store service owns those
operations and publication after durable readback and logging.

## Inputs and subjects

`physical_static_contract.collect_static_camera_contract(workspace, *, binding,
source_qualification, cancellation, progress, deadline_ns)` returns an immutable
`StaticCameraContractReceipt`. Collection is explicit, one-shot and file-only.
The original deadline is capped at 30 seconds, never renewed. The source
qualification must be the exact typed original receipt whose deterministic
assessment is PASS. The binding includes the original qualification receipt,
assessment and review hashes, original prerequisite/header/session/source/store,
the exact explicit static entry-event hash and the current collection actor and
launch. The caller must authenticate the original review and entry event under
the real original M1 scope; document self-hashes do not authenticate them.

The fixed five-file roster is `FIXED_PATHS`:

- selected camera architecture plan;
- purchased Arducam B0477 profile;
- static overhead support design;
- original workcell layout;
- original robot reach-screening input.

Original UTF-8 strings, byte lengths and SHA-256 values are retained exactly.
Fresh reads use existing regular-file/ancestry checks and sharing pins. Whole
source fingerprints are checked before collection, after the complete fixed
file observation, and at final return. No directory or original is created or
modified. Each file is bounded at 64 KiB and their aggregate at 128 KiB.

The receipt embeds the strict original software receipt from its authenticated
source qualification, not a second copy of its ownership experiment. It retains
all 17 existing physical-onboarding static cross-checks, published design values,
support screening calculations, all original blockers and HZ-007/HZ-010.
The existing architecture and support file loaders now delegate to reusable
pure byte parsers; their normal APIs and validators remain available. The
purchased-camera profile already supplied its pure parser.

## Pure verification and review

All three record types expose immutable `.payload`, `.sha256`, `.to_dict()` and
`.safe_summary()`; returned documents are detached. Byte payloads must be exact
canonical ASCII JSON, with duplicate keys/nonfinite numbers/extra fields refused.

`verify_static_camera_contract_receipt(value, *, prerequisites,
source_qualification, expected_binding, expected_receipt_sha256)` independently
joins all subjects and reparses every retained original design byte. It performs
no filesystem access, source fingerprint, host calculation or device operation.

`assess_static_camera_contract(receipt)` deterministically yields PASS only when
all 17 strict checks pass, otherwise BLOCKED. Both outcomes retain physical
blockers: design-only PASS does not assert those blockers have cleared.

`review_static_camera_contract(receipt, assessment, *, reviewer_id,
review_launch_id, reviewed_at_ns)` requires the exact assessment and a portable
ASCII reviewer label distinct under Python casefold from the collection actor.
Its review time must not precede collection. This records a procedural review;
it does not itself transition a stage or enter received-camera inspection.

The corresponding assessment/review verifiers take the exact typed subjects and
independently expected artifact hashes. They recompute the deterministic chain.
No caller boolean can replace an assessed check or verdict.

## Bounds, history and meaning

Receipt cap is 256 KiB; assessment and review caps are 32 KiB each. Each compact
summary is bounded at 24 KiB. Raw-free summaries mark design values explicitly
`DESIGN_NOT_MEASURED`; a published catalog mode is not a received negotiated mode.
All physical authority, hardware qualification, device I/O and native runtime
release flags remain false, including for PASS.

`StaticCameraContractError` exposes a fixed `.code` and optional `.receipt`.
A fully verified receipt remains available after late Stop, deadline, source,
progress or pin-close failure. It is historical only and must not be published
as current. Incomplete or malformed source bytes are not promoted into a valid
receipt. There is no retry, replay, repair, source-lock refresh or release API.

The dedicated tests exercise actual controlled files with an explicitly modeled
broad source/admission context, exact retained verification with all path reads
forbidden, parsed original-source conflicts, tampering, late failure retention,
distinct review and old-loader/pure-parser equivalence. No test in this slice
executes camera helpers, inventories devices or observes received hardware.
