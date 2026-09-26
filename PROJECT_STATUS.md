# Tactevra project status

Reviewed September 26, 2026 against GitHub source through `ca8c5ae`.
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
| Arm control research | Documented supervised noncontact movement and joint-feedback checks | Specific lab sequences were completed; controller feedback does not measure key-contact accuracy |
| Hardware | RC03 workcell design and step-by-step assembly package | Design and print resources exist, with their own measurement and print-readiness requirements |

The shared v2 contract suite recorded 73 passing tests at its integration
checkpoint. The subsequent precision-binding increment recorded 31 passing
tests. These are separate, overlapping software selections, not a combined
accuracy score or a physical typing success rate. See entries INT-001 and AI-011
in the [evidence ledger](software/ai/docs/SHARED_AI_ARM_WORKPLAN.md). The newer
ARM-006 entry records 48 passing tests for the planning adapter and its related
checks, including the expected calibration block. Later ARM-010 and ARM-012
entries add ordered coordination and a v2 trajectory-envelope contract; the real
shadow trace still stops at calibration rather than authorizing hardware.

The latest confidence-head training completed but **failed its synthetic research
criteria** (AI-017): no evaluation targets were accepted, and the required scoring
threshold was not met. That is a preserved research result, not production-ready
confidence or evidence of zero false accepts. Passing metric unit tests does not
change the model result.

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

The AI lane is connecting precision output and capture provenance to the shared
command format. The arm lane has connected validated proposals to its planning
policy, ordered coordination, and envelope contracts. The AI lane is investigating
the failed confidence experiment. Both use the same
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
