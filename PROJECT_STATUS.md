# Tactevra project status

Reviewed September 26, 2026 against merged source through `b1bb742`.
Unmerged workstream branches are not included in this summary.
This is a capability summary for readers; the
[shared workplan](software/ai/docs/SHARED_AI_ARM_WORKPLAN.md) retains detailed
stage ownership and test evidence as development continues.

Tactevra (formerly RoCell) is an experimental robot workcell intended to carry out keyboard and phone
tasks from a person's text request. You can explore the software and run offline
examples today. A reliable physical typing or phone-operation product is still
being developed.

## What works today

| Area | Available now | What this establishes |
| --- | --- | --- |
| Local interface | Browser and terminal rehearsal, task planning, diagnostic exports | Software workflows can be explored without connecting a robot |
| Text interpretation | Grounded parser and deterministic compiler for supported requests | Supported text can become an ordered list of named actions; arbitrary language is not guaranteed |
| Scene assessment | Local vision adapters and experimental Gemma scene checks | Saved images can be assessed for device visibility and quality; results remain provisional |
| Keyboard localization | KeyboardPoseNet trained on synthetic images | Candidate keyboard poses and key coordinates can be evaluated offline; real-camera accuracy remains unqualified |
| AI-to-arm interface | V2 batch assembler, strict decoder, registry snapshot, and freshness checks | Actual assembler output passes shared software tests with synthetic evidence, preserving action order and rejecting tested invalid inputs |
| Precision evidence | Identity and capture-receipt binding helpers | These establish software checks, not a qualified real-camera observation; authenticated capture and usable localization confidence remain open |
| Arm planning adapter | Admitted v2 proposals enter the arm-owned measured planning policy | The tested valid input reaches the planner but stops for missing or stale calibration; no trajectory or controller command is produced |
| Controller-command preview | Sealed synthetic trajectories can be encoded into Waveshare T=102 bytes and a proposed dispatch schedule | Offline encoding and published schemas are tested; the preview has no transport and sends nothing to the arm |
| Execution lifecycle rehearsal | Ownership, single-use reservations, fault handling, and restart reconciliation are modeled | Tests exercise no-retry and fault rules without device I/O; this is not an installed live execution service |
| Arm control research | Documented supervised noncontact movement and joint-feedback checks | Specific lab sequences were completed; controller feedback does not measure key-contact accuracy |
| Hardware | RC03 workcell design and step-by-step assembly package | Design and print resources exist, with their own measurement and print-readiness requirements |

### Recent progress, in plain language

The arm lane can now inspect what controller-command bytes a synthetic movement
would produce, without sending them. It also rehearses how one command owner
would reserve work, stop on faults, and reconcile a restart without automatic
retries. Published schemas and an exact-byte fixture let the workstreams check
the same boundary. These developments do not remove the real planning path's
calibration block or qualify an installed controller mapping.

The AI lane has a translation-focused training candidate that improved mean key
position error from about 0.937 to 0.907 mm on reused synthetic development data.
That is a development-selection result, not independent generalization or real
camera accuracy. At this merged checkpoint, a fresh held-out comparison remains
the next dependency; no runtime checkpoint was replaced by this experiment.
The earlier confidence-head experiment **failed its synthetic research criteria**
and accepted no evaluation targets. Better pose estimates do not establish usable
confidence or erase that failure.

Detailed evidence is in AI-035/036 and ARM-018/020 of the
[shared ledger](software/ai/docs/SHARED_AI_ARM_WORKPLAN.md). ARM-020 records 229
passing tests in its selected integration run, with zero hardware writes and
zero physical movements. Test selections overlap and are not a model-accuracy
score, full-suite qualification, or physical typing success rate.

Repository improvements include protected-main CI, support and private security
reporting, and an experimental source-release checklist. The snapshot audit now
uses [exact reviewed synthetic-fixture exceptions](docs/AUDIT_FIXTURE_REVIEW.md);
historical failed audit records remain intact. An audit pass is not security
certification. See [test tiers](docs/CI.md) for clean-checkout limits.

## What still needs work

The main gap is connecting trustworthy perception to physical execution. The
current v2 assembler consumes supplied observations. The precision preflight
does not yet produce a complete qualified batch from a real camera capture.
The trusted registry is an in-process snapshot; creating it does not establish
the provenance of the measurements it contains.

Before physical typing can be demonstrated, the system needs measured camera,
board, device, robot and tool relationships; qualified localization and confidence;
validated movement and contact behavior; and independent confirmation that the
intended character actually appeared. The phone workflow also needs fresh screen
state observations between actions. Phone contracts and simulations do not yet
demonstrate an operating dialer or completed call.

## Current development direction

The AI lane needs independent evaluation of the localization candidate and
separate confidence qualification, alongside capture provenance. The arm lane
needs independently verified installed-controller mapping and firmware evidence
before connecting its zero-write preview to any physical dispatch path. Both use the same
[AI/arm workplan](software/ai/docs/SHARED_AI_ARM_WORKPLAN.md).
The next shared milestone is a complete offline path from user text and visual
evidence to a checked movement plan. Further physical qualification is tracked
separately. Stylus loading and additional ghost routines are retained as specific
lab procedures, rather than the general next step for every reader.

## How to interpret results

- **Simulation:** a result under modeled geometry and assumptions.
- **Controller feedback:** the joint positions reported by the device.
- **Visual observation:** what a person or camera saw during a particular test.
- **External measurement:** a position or clearance measured independently.
- **Verified device input:** confirmation that the intended key or screen action occurred.

A successful result at one level does not establish the next. For example, the
[r91 five-leg record](software/docs/R91_HOVER_RECOVERY_AND_A_CYCLE_PLAN.md#live-five-leg-result-2026-09-25)
is historical noncontact movement evidence, not a reading of the current arm pose
or a physical typing result. Older plans preserve their original failures and
successes; their proposed next steps may have been superseded.

## What a clone includes

The repository contains source, documentation, tests, contracts, hardware design
packages, and selected research records. It is not a copy of the lab workstation.
Private credentials, raw run exports, device backups, local toolchains, and some
measurement/model artifacts are excluded. A link to a lab export may identify
evidence that is unavailable in a fresh clone.

Use [getting started](docs/GETTING_STARTED.md) for a first run,
[the documentation guide](docs/README.md) to find a topic, and
[contributing](CONTRIBUTING.md) for development and sanitized evidence sharing.
