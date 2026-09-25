# Original stage-9 arm identity onboarding — proposed work order

Status: **proposed and unimplemented**, 2026-09-09. This is the bounded next
arm-identity increment in the [application completion matrix](ONBOARDING_APPLICATION_COMPLETION_MATRIX.md),
not completion of the arm connection, startup or feedback path. It changes no
current source, effect policy, physical release or historical evidence.

## Outcome and prerequisite

Deliver an explicit service-backed original submission, assessment and
independent exact review for `arm_identity`. Its outputs are only
`arm_physical_identity`, `exact_arm_physical_identity` and a
`controller_inventory_candidate`, as assigned by the
[stage catalog](../config/physical_onboarding_stage_catalog.json).
Actuator power must remain disconnected; stage 9 permits metadata inventory,
not serial opening, firmware queries, power changes or motion.

Admission requires the genuine original stage-8 (`static_registration`) PASS
receipt, assessment and review, followed by explicit stage-9 entry. **That
physical predecessor is not implemented/available yet.** Pure contracts and
service tests can be developed with clearly labeled modeled predecessors, but
the production path must remain unavailable until its actual original producer
exists. Do not manufacture a prefix, relabel rehearsal passes, or skip stages.

## Reusable foundations and their limits

- [Native arm metadata](../src/rocell/application/wizard_native_arm_metadata.py):
  `decode_controller_snapshot`, `correlate_native_arm_metadata` and
  `summarize_native_arm_metadata`; full
  `rocell.wizard_native_arm_metadata.v1` report, maximum 768 KiB.
  Retain the separate exact generic SERIAL review that its hashes reference.
- [Arrival](../src/rocell/application/arrival_wizard_service.py): existing
  generic inventory/candidate review and explicit native-arm inspection,
  source/launch invalidation, exact-result checks and completion-log publication.
  `METADATA_CORRELATED` is not stage acceptance or connection authority.
- [Received-camera service](../src/rocell/application/physical_received_camera_service.py):
  reuse the ownership pattern for append-only originals, partial retention,
  exact review and publication; do not reuse camera-specific schemas.
- [Intake inbox](../src/rocell/application/physical_intake_inbox.py): assigned
  input-folder discovery, opaque choices, bounded selected bytes and revalidation.
  Keep the existing allowed media and privacy rules; no arbitrary user paths.
- [INT-010 source](../../hardware/static_overhead_camera/hardware_intake_template.csv):
  robot `exact_model_and_serial`, unit `text`, requirement `RoArm-M3 Pro required`.
  [Camera prerequisites](../src/rocell/application/physical_camera_prerequisites.py)
  derive only the first four stages, and the
  [existing notebook](../src/rocell/application/physical_intake_notebook.py)
  accepts only sixteen camera-receipt questions. Preserve both historical
  contracts; add a separate arm requirements/observation codec.

## Proposed implementation handoff

1. **Pure originals — new `physical_arm_identity_submission.py`.** Define
   strict bytes-only `ArmIdentityRequirements`, `ArmIdentitySubmission`,
   `ArmIdentityAssessment` and `ArmIdentityReview`, with immutable payloads,
   SHA-256, detached dictionaries and compact summaries. Builders/verifiers take
   independent expected bindings, hashes and exact original references; no
   caller-supplied verdict or authority flags.

   Requirements retain the controlled stage/hazard/epoch/intake rules and exact
   [arm serial profile](../config/arm_connection.json). Submission binds unique
   collection ID, original source/cell/session/header, current launch/operator,
   stage-8 trio and stage-entry event, requirements hash, generic review, native
   correlation and selected original attachments. Record explicit OBSERVED or
   UNKNOWN for chassis model/serial, controller association, supply/cable,
   disconnected-power observation and ownership declaration. An observed claim
   must identify its supporting originals and method; unknowns retain reasons.

   Assessment recomputes completeness, reference integrity and comparisons.
   Independent review binds the exact submission and assessment, records a
   distinct reviewer and never treats text or a checkbox as measured truth.
   Close the stage-9 acceptance checklist before implementing an accepting
   verdict; do not replace the missing checklist with an always-PASS or
   permanently-BLOCKED wrapper.

2. **Original storage/readback — new `physical_arm_identity_readback.py`.**
   Retain separate requirements, generic-review, native-correlation, submission,
   assessment and review JSON roles, plus selected original media. Agree closed
   labels, per-role caps, aggregate quota and a small cycle limit before coding;
   preserve existing family/stage limits. Authenticate every role's actual
   bytes and full reference under the existing M1 stage-only leases.

   First submission uses the explicit stage-9 WAITING entry; committed
   submission/assessment moves to REVIEW_PENDING, exact review to PASS or
   BLOCKED. A new cycle requires a committed BLOCKED review and explicit
   successor entry citing that exact trio. Partial originals are retained and
   export-only, never automatically completed or resubmitted. Preserve the
   complete genuine earlier stage and campaign history; no fabricated snapshot,
   new storage framework or unqualified parallel vault.

3. **Application owner — new `PhysicalArmIdentityService`.** Add a narrow Setup
   operation scope using the same original session/runtime and shared operation
   lock. Proposed actions are `physical_arm_identity_begin`, `_submit`, `_review`
   and explicit `_revise`; finalize names in the action registry before UI work.
   Reuse existing metadata actions and input-folder discovery. Begin must
   establish context before fresh metadata acquisition. Submission accepts only
   exact successful current-launch publications, with original operation/result
   hashes; restart must not infer a fresh acquisition from cached reports.

   Follow existing `view`, `context_sha256`, `perform`, `validate_publication`,
   `publication_completed`, `invalidate` and `retained_diagnostics` ownership.
   Source/launch/head/inventory changes, Stop and failed completion logging
   withdraw current status without discarding collected originals. No public
   GET, refresh, preview or reopen performs metadata acquisition or opens COM.

4. **Presentation/export.** Extend the existing Arm page and terminal from the
   same compact service view, including missing evidence and historical/partial
   state. Reuse Arrival's diagnostic log, assigned export parent, full-original
   metadata attachments and `verify_export`; do not create another export
   system. Raw photographs require the existing explicit private-original
   export consent. Exact review subjects remain exportable after result-card
   rotation, failed publication and fresh original reopening.

## Evidence and authority boundaries to settle explicitly

- [RoArmUsbSerialIdentity](../src/rocell/application/physical_connection_contracts.py)
  has nominal Pro/ESP32 defaults. These are not observations of the received
  chassis or its installed firmware. USB VID/PID and a bridge serial cannot
  substitute for photographs/labels and independently reviewed arm-to-controller
  association. Generic serial provenance is not USB-descriptor provenance;
  COM number and friendly name are not persistent selection authority.
- Current metadata correlation is one point-in-time mapping. If stage-9
  acceptance requires reconnect/reboot stability, specify its original
  acquisition/order policy and owner; the existing correlation alone does not
  implement it. Do not relabel camera USB trials as arm continuity evidence.
- Expected firmware package and an approved future readback procedure are not
  installed-firmware proof or measured boot/reset behavior. Define those later
  independent evidence contracts without querying firmware during stage 9.
  [Configuration epochs](../src/rocell/application/physical_configuration_epochs.py)
  assign arm identity to stage 9 and controller/firmware identity to stage 12;
  requiring completed stage-12 outputs before stage 9 would create a cycle.
- Do not construct
  [ReviewedControllerBinding](../src/rocell/providers/windows/arm_feedback_worker.py)
  from metadata: it separately requires model, installed-firmware, boot-policy
  and serial-profile evidence. Stage 9 cannot produce
  `qualified_controller_identity`, set the profile to QUALIFIED, enable
  `arm_connect`, energize, or open serial. Stages 10–12 remain separate original
  safety/startup/feedback work; Stage-9 PASS never automatically starts them.

## Small acceptance suite

Add focused codec, reader/service and public-Arrival test files. Reuse fixtures
from [native metadata tests](../tests/unit/test_wizard_native_arm_metadata.py)
and [public metadata integration tests](../tests/unit/test_wizard_native_arm_integration.py),
not their observations as actual physical evidence.

1. Reject duplicate/unknown fields, rehashed substituted subjects, wrong model,
   swapped media, fabricated firmware proof and ambiguous/changed native mapping.
2. Exercise explicit UNKNOWN/BLOCKED and policy-valid exact review; reviewer
   substitution or metadata correlation alone cannot accept the stage.
3. Changed source, launch, generic review, metadata publication or original
   inventory fails before writes; previews and cached views remain inert.
4. Partial writes, Stop and lost completion logging preserve useful originals
   and export; reopen never repeats submission, review or device actions.
5. Public tickets/queue/result/log through real isolated NTFS/M1 retention,
   assigned-folder export verification and fresh original reopening; all
   physical facts explicitly modeled, serial/device/process entry points
   forbidden, and later-stage/connection authority still absent.

No implementation or execution is authorized by this document. Review the
proposed wire, acceptance policy, quotas and stage-8 dependency before source
work begins after the current freeze.

## Read-only integration cross-check — 2026-09-12

Reviewed while the P1 full-history run-06 source is frozen; no arm implementation,
configuration, stage release, serial opening or new test execution is part of
this cross-check. The stage-9 work above remains proposed. This ties later
P4 implementation to actual current boundaries, rather than treating camera
startup improvements as arm connection readiness.

| Existing boundary | Confirmed current behavior | Required later integration |
| --- | --- | --- |
| `arm_connection.json` | Port/model-unit/firmware observations unresolved; 115200 baud; RTS/DTR false; no auto-connect, initialize or blind retry | Retain unknowns until their own observed originals exist; configured signal levels are not measured no-reset proof |
| `wizard_native_arm_metadata.py` | Bounded generic/native correlation, COM1–COM4096 validation, no connection/qualification authority | Stage-9 service must bind the exact successful current-launch metadata publication and keep the full generic review separately |
| `ReviewedControllerBinding` in `arm_feedback_worker.py` | Requires independent identity, model, installed-firmware, boot-policy and serial-profile references; COM1–COM4096 | Do not derive this stronger object from metadata-only stage-9 acceptance or a typed COM string |
| Stage catalog, stages 10/11/12 | Separate power-safety, manual startup observation and feedback-only exchange; each owns distinct originals | New services must preserve these boundaries and end-disconnected requirements; no automatic transition to power or serial |
| `feedback_wire.py` | Shared pure bounded T=1051 parser; rejects pre-request bytes because responses lack an echoed transaction ID | Fake and later qualified physical backends must exercise the same stale-buffer, framing, type and reset-banner rules |
| `arm_nonpurging_adapter.py` | Separate non-purging owner bridge exists; native activation is held | Reuse the bridge and existing process/ownership qualification work, not a new UI serial backend or a removed release hold |
| `SerialTransport` | Existing live interface permits only separately authorized feedback; physical motion is blocked | Stage-12 onboarding must not fabricate legacy commissioned feedback/motion permits or add an arbitrary command box |

Developer follow-up remains the original stage-9 submission/assessment/review
codec and service, after closing its acceptance policy and real stage-8 producer
dependency. Test the complete service/publication/export path with modeled
predecessors first. Merely displaying a correlated controller must continue to
show that firmware, power/startup qualification and serial access are separate.
