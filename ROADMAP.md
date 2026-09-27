# Tactevra roadmap

**Document status:** Current public roadmap

**Authority:** Planning and navigation only. This page does not claim capability,
approve a release, or authorize hardware operation.

Tactevra is progressing from reproducible offline research toward checked,
measured physical interaction. The roadmap is evidence-driven: a stage advances
only when its completion evidence is merged and reflected in
[project status](PROJECT_STATUS.md). Dates are intentionally omitted because
physical qualification and third-party review cannot be predicted responsibly.

## Current foundation

The repository currently provides a hardware-free walkthrough, structured
AI-to-arm contracts, simulated planning and command previews, operational gates,
and records of particular supervised noncontact movements. These results show
that individual software boundaries can be tested. They do not establish a
reliable camera-to-arm typing system or autonomous phone operation.

See [project status](PROJECT_STATUS.md) for the dated capability statement and
the [evidence ledger](software/ai/docs/EVIDENCE_LEDGER.md) for detailed records.

## Delivery stages

| Stage | Objective | Completion evidence |
| --- | --- | --- |
| 1. Governed source preview | Make the research source understandable, reviewable, and reproducible without implying physical qualification | Release blockers in [#56](https://github.com/j-webtek/tactevra/issues/56), [#61](https://github.com/j-webtek/tactevra/issues/61), and [#88](https://github.com/j-webtek/tactevra/issues/88) are resolved; an exact candidate is separately reviewed and approved |
| 2. Measured workcell | Replace nominal camera, board, robot, device, and tool assumptions with bound measurements | Calibration identities, uncertainty bounds, installed collision evidence, and fresh observation receipts pass the operational-readiness gate |
| 3. One verified physical action | Execute one bounded keyboard action and independently confirm its result | Intended target, admitted plan, controller receipts, observed motion, and device-level outcome are linked in one reviewable record |
| 4. Reliable bounded sequences | Extend one verified action to short keyboard sequences without weakening rejection or recovery rules | Held-out sequences report target accuracy, abstention, timing, recovery, and independently verified outcomes |
| 5. State-aware device workflows | Add bounded phone and changing-screen interactions | Each action is conditioned on observed device state, checked before execution, and independently verified afterward |

## Workstreams

| Workstream | Near-term responsibility | Shared boundary |
| --- | --- | --- |
| AI and perception | Produce typed intent, scene-quality evidence, and candidate targets with declared frames and confidence | [AI-to-runtime contract](software/ai/docs/CONTRACT.md) |
| Arm runtime | Validate proposals, calibration, geometry, permissions, lifecycle, and feedback before any dispatch | [Runtime architecture](software/docs/ARCHITECTURE.md) |
| Physical workcell | Establish measured installation, tool geometry, clearance, and repeatable observation | [Hardware build guide](docs/HARDWARE_BUILD_GUIDE.md) |
| Repository and release | Preserve reviewable evidence, compatibility, security controls, and honest public claims | [Repository operations](docs/REPOSITORY_OPERATIONS.md) and [release readiness](docs/releases/READINESS.md) |

The active engineering handoff is maintained in the
[shared AI/arm workplan](software/ai/docs/SHARED_AI_ARM_WORKPLAN.md). That document
coordinates implementation; this roadmap remains the concise public view.

## Advancement rules

A stage is not complete merely because a demo looks correct or a simulation
passes. Advancement requires:

1. a named, reviewable evidence record on merged `main`;
2. explicit separation of simulation, controller feedback, observed motion, and
   independently verified task outcome;
3. retained failure and abstention behavior, not only successful examples;
4. documented compatibility and provenance for included assets; and
5. updated project status using language supported by the evidence.

Publication, firmware installation, and physical movement remain separate,
explicitly reviewed actions.
