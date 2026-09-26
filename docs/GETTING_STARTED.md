# Getting started with Tactevra

Tactevra (formerly RoCell) is an experimental robot workcell for keyboard and phone interaction.
Start by exploring its software rehearsal and text interpretation. You do not
need a robot, camera, stylus, GPU, or downloaded language model for the examples
on this page.

The examples prepare or inspect tasks; they do not type into your keyboard or
move an arm. Read [project status](../PROJECT_STATUS.md) for the current physical
capabilities and remaining work.

## Install the software

Use Windows PowerShell, Git, and Python 3.10 or newer. These instructions assume
you have access to the repository. Run the commands from a directory where you
want the checkout to live:

```powershell
git clone https://github.com/j-webtek/robot-arm-build.git
cd robot-arm-build
python -m venv .venv
.\.venv\Scripts\python -m pip install -e './software'
```

Keep subsequent commands in the repository root. Using the explicit virtual
environment interpreter avoids needing to activate the environment. The base
installation downloads Python dependencies; local rehearsal does not need a
model service. Additional AI training, vision, serial and test dependencies are
separate developer setup choices.

## Try a text request

```powershell
.\.venv\Scripts\python software/ai/run_offline.py ground --request 'Type "hi" on the keyboard'
```

The command prints a structured result describing the interpreted request.
Inspect its decision, device and text. Supported requests can be passed to the
compiler; an ambiguous or unsupported request should produce a clarification or
rejection. This example uses the grounded parser, so it requires no Ollama model.

To inspect the offline coordinate preview:

```powershell
.\.venv\Scripts\python software/ai/run_offline.py coordinate-preview --request 'Type "hi" on the keyboard'
```

This uses the development configuration and nominal geometry. A preview can show
candidate targets or explain a blocker. Its coordinates are not measurements of
your desk, keyboard or robot. The developer [AI reference](../software/ai/README.md)
describes saved-image experiments and optional model runtimes.

## Explore the interface

```powershell
.\start-rocell-wizard.ps1
```

The launcher defaults to rehearsal and opens the local browser interface. You can
inspect the software baseline, rehearse connection workflows, prepare tasks and
export diagnostic records. Launching rehearsal does not open physical devices.
For terminal navigation, use:

```powershell
.\start-rocell-wizard.ps1 -Ui terminal
```

Follow the [workbench guide](../software/docs/WIZARD_WORKBENCH.md) for individual
actions. Keep the launching terminal open while using the browser interface;
stop the server with Ctrl+C when finished. Exports normally stay in the local
`software/runs/wizard-exports/` directory.

## Understand what the software tells you

| Term | Meaning |
| --- | --- |
| Rehearsal | A software workflow using simulated device behavior |
| Nominal coordinates | Coordinates from the configured design, before measuring your installation |
| Ghost typing | Arm movement above a keyboard without pressing keys |
| Proposal or batch | One or more requested named targets, with supporting evidence |
| Calibration | Measured relationships between the camera, board, device, robot and tool |
| Abstain / blocked | Required information is missing, inconsistent or outside the supported scope |
| Lease / freshness | A time limit on how long an observation can be reused |

An accepted proposal means it passed a particular software check. It does not
mean the arm moved or the intended character appeared. Look at the result's
stage and evidence type before interpreting it as a completed task.

## Common first-run issues

- **Python or Git is not recognized:** install the missing tool, reopen the
  terminal, and check `python --version` or `git --version`.
- **RoCell cannot be imported:** rerun the editable installation with the same
  `.venv` interpreter used for the example.
- **PowerShell blocks a launcher:** use your organization's approved script
  execution policy. The direct Python text examples can still be used; do not
  change machine-wide policy merely to follow this guide.
- **A model name or image file is missing:** those belong to optional research
  examples. Begin with `ground`, which needs neither.
- **A plan reports missing calibration or evidence:** retain that result and
  inspect the named prerequisite. A fresh clone does not contain the lab's
  private calibration and device records.

## Choose your next step

- To assemble a workcell, read the [RC03 build guide](../active-project/RoCell_v0_3/BUILD_BY_STEP/README.md)
  and its [print-readiness record](../active-project/RoCell_v0_3/PRINT_READINESS.md).
- To develop software, read [contributing](../CONTRIBUTING.md).
- To work on AI or arm integration, use the [shared developer workplan](../software/ai/docs/SHARED_AI_ARM_WORKPLAN.md).
- To understand the evidence and roadmap, read [project status](../PROJECT_STATUS.md).
