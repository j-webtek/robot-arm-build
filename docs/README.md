# Documentation guide

Start with the [project overview](../README.md) and
[current status](../PROJECT_STATUS.md). Use the links below when you need
implementation details or evidence for a specific part of the system.

## Current arm and typing work

| Document | What it explains |
| --- | --- |
| [r91 recovery and A-cycle record](../software/docs/R91_HOVER_RECOVERY_AND_A_CYCLE_PLAN.md#live-five-leg-result-2026-09-25) | The completed five-leg physical cycle, feedback results, and export references |
| [Photo-estimated keyboard screen](../software/docs/PHOTO_ESTIMATED_KEYBOARD_SCREEN.md) | The photographed keyboard placement, modeling assumptions, and limits of the estimate |
| [Stylus loading procedure](../software/docs/STYLUS_LOADING_PROCEDURE.md) | Controller prerequisites, attended loading, and mounted-tool measurements; not yet executed |
| [Selected stylus reference](../software/docs/SELECTED_STYLUS_REFERENCE.md) | The selected tool and what still needs measuring and validating |
| [Full-size keyboard ghost-typing plan](../software/docs/PERIBOARD_PHYSICAL_GHOST_TYPING_PLAN.md) | Keyboard geometry, virtual tip modeling, and noncontact test design; includes earlier checkpoints |

Servo feedback establishes reported joint positions. It does not by itself
measure the stylus tip or confirm that a key was pressed. The status page
distinguishes these kinds of evidence.

## Software and architecture

- [Developer setup and contribution workflow](../CONTRIBUTING.md): installation,
  scoped checks, Git workflow, and sanitized evidence sharing.
- [Wizard workbench](../software/docs/WIZARD_WORKBENCH.md): local browser and
  terminal interface usage.
- [Software reference](../software/README.md): detailed component descriptions,
  setup, commands, and earlier implementation checkpoints. Use project status
  for the latest physical-test summary.
- [Reviewed-hover protocol](../software/docs/REVIEWED_HOVER_RUNTIME_PROTOCOL_PLAN.md):
  command handling, feedback, and export contracts.
- [Official Waveshare tooling reuse plan](../software/docs/OFFICIAL_TOOLING_REUSE_PLAN.md):
  how the SDK, protocol, and models fit into this codebase.
- [Pinned arm model](../software/models/roarm_m3/README.md): model provenance
  and the kinematic contract.
- [System master plan](../ROBOT_TYPING_SYSTEM_MASTER_PLAN.md): overall system
  design and roadmap.

## Hardware and camera

- [RC03 package introduction](../active-project/RoCell_v0_3/README_FIRST.md)
  and [assembly steps](../active-project/RoCell_v0_3/BUILD_BY_STEP/README.md).
- [Print readiness](../active-project/RoCell_v0_3/PRINT_READINESS.md): which
  print jobs are released and which still depend on measurements.
- [Integrated build plan](../active-project/RoCell_v0_3/RC03_INTEGRATED_BUILD_PLAN.md):
  engineering rationale and package organization.
- [Static overhead camera hardware](../hardware/static_overhead_camera/README.md)
  and [camera architecture plan](../STATIC_OVERHEAD_CAMERA_ARCHITECTURE_PLAN.md).

## Simulation, provenance, and deeper history

- [Virtual commissioning](../software/docs/VIRTUAL_COMMISSIONING.md): simulated
  keyboard/phone sessions and replay.
- [Trajectory simulation](../software/docs/TRAJECTORY_SIMULATION.md) and
  [collision foundations](../software/docs/COLLISION_FOUNDATION.md): path
  checks, modeled geometry, and their limits.
- [Prehardware qualification](../software/docs/PREHARDWARE_QUALIFICATION.md):
  simulation regression campaigns.
- [Build alignment](../BUILD_ALIGNMENT_FREEZE.md) and
  [freeze records](../software/freezes/README.md): controlled source versions
  and hardware/software traceability.
- [Historical workspace reference](history/WORKSPACE_REFERENCE.md): the
  detailed former root README, including camera development history, simulation
  results, command examples, and the RC03 package map.

Older plans retain earlier outcomes and proposed next steps. Read their dates
and later result sections before using them. Raw exports referenced by these
documents may exist only on the lab workstation; sharing them is covered in
[the contribution guide](../CONTRIBUTING.md#export-sharing).
