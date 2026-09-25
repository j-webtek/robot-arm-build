# RoCell — Robot Arm Build

RoCell is a work-in-progress system that uses a Waveshare RoArm-M3 to operate
a physical keyboard and tap a phone with a stylus. This repository contains
the arm-control software, simulations, test records, and printable workcell
designs.

The aim is simple: turn a requested key or screen position into a planned
movement, check what the arm actually did, and build toward reliable typing.

## Where we are

As of September 25, 2026, the arm has completed a supervised five-leg,
noncontact movement cycle with verified controller feedback and an export
for each leg. This demonstrates that specific sequence; physical key accuracy
and stylus contact are still to be established.

The next stage is stylus loading and measurement, followed by keyboard
registration and further ghost-typing tests—movements above keys without
pressing them. Camera mounting and integration are also unfinished.

Read [project status](PROJECT_STATUS.md) for the checkpoint, evidence, and
next steps. Simulation results, servo feedback, and measured tip accuracy
are tracked separately.

## Start here

| I want to… | Read this |
| --- | --- |
| Understand what works and what comes next | [Project status](PROJECT_STATUS.md) |
| Set up the code and contribute | [Developer setup](CONTRIBUTING.md) |
| Explore the local interface | [Wizard workbench guide](software/docs/WIZARD_WORKBENCH.md) |
| Build the physical workcell | [Step-by-step assembly guide](active-project/RoCell_v0_3/BUILD_BY_STEP/README.md) |
| Find architecture, test results, or procedures | [Documentation guide](docs/README.md) |

After completing developer setup, launch the local rehearsal interface from
the repository root:

```powershell
.\start-rocell-wizard.ps1
```

Rehearsal is the default; launching it does not open hardware connections.
The [workbench guide](software/docs/WIZARD_WORKBENCH.md) covers the available
actions and terminal interface.

## Repository layout

| Folder | Contents |
| --- | --- |
| [software/](software/README.md) | Python runtime, firmware, models, tests, and technical documentation |
| [active-project/RoCell_v0_3/](active-project/RoCell_v0_3/README_FIRST.md) | Active RC03 hardware design, print files, and assembly instructions |
| [hardware/static_overhead_camera/](hardware/static_overhead_camera/README.md) | Static overhead camera design and mounting work |
| [scripts/](scripts/) | Project tools and experiment runners |
| [docs/](docs/README.md) | Reading guide and historical workspace reference |
| [active-project/RoCell_v0_2/](active-project/RoCell_v0_2/README_FIRST.md) | Frozen earlier hardware release, retained for reference |

RC03 and RC02 parts and coordinates belong to separate releases. Hardware
packages retain their own print-readiness and measurement requirements.

## Working with this project

This is an experimental physical system. Follow the current procedure for
the exact controller and test; a passing simulation or source update does
not establish physical clearance or authorize a deployment.

Credentials, device backups, raw run exports, and local toolchains stay
outside Git. A clone contains the shared development baseline, not the
entire lab workstation. See [contributing](CONTRIBUTING.md) for setup,
verification, and sharing evidence.

Detailed simulation results, command examples, and hardware history formerly
on this page are preserved in the
[historical workspace reference](docs/history/WORKSPACE_REFERENCE.md).
