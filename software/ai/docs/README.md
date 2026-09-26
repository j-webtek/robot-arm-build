# AI documentation

For a user introduction, start with [getting started](../../../docs/GETTING_STARTED.md)
and [current capabilities](../../../PROJECT_STATUS.md). This directory contains
developer contracts, research records, and implementation plans.

Contributors should start with the
[shared AI-to-arm workplan and evidence backbone](SHARED_AI_ARM_WORKPLAN.md).
It is the common stage board for the AI/model and arm/runtime workstreams and
the append-only index for cross-lane evidence.

Then read [the integration contract](CONTRACT.md), followed by the
[model-to-arm translation assurance process](MODEL_TO_ARM_TRANSLATION_ASSURANCE.md),
then [the roadmap](ROADMAP.md).
The [model research note](MODEL_RESEARCH.md) records the published Llama
methods and what still needs a baseline experiment.

The [AI system baseline and implementation plan](AI_SYSTEM_BASELINE_AND_IMPLEMENTATION_PLAN.md)
records what is implemented, what the evidence establishes, how an Ollama or
llama.cpp multimodal observer fits beside the precision pose model, and the
prioritized path to a physically qualified system.

These documents include both implemented offline components and proposed work.
Read each document's date, result, and limitations. Current RoCell
capabilities and physical status remain in the repository's
[project status](../../../PROJECT_STATUS.md),
[software architecture](../../docs/ARCHITECTURE.md), and code. The AI documents
must be revised when those contracts change.
