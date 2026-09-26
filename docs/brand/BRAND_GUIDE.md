# Brand foundation — draft for owner review

Prepared September 26, 2026. No new name has been adopted. The current project
remains RoCell and the repository remains `j-webtek/robot-arm-build`.

Start here for consistent product language. Use the [naming review](NAMING_REVIEW.md)
to choose a candidate and the [migration plan](MIGRATION_PLAN.md) to implement an
approved identity. These documents do not change software or hardware behavior.

## Positioning

Product category: local-first robotics software and workcell integration.

Positioning statement:

> An experimental local-first robotics platform connecting user intent,
> visual evidence, and checked physical actions.

Short description for current use:

> RoCell brings AI target proposals and robot control into one inspectable
> workflow. It supports offline research, command validation, and supervised
> movement experiments while physical typing and phone interaction are developed.

Future brand tagline candidate: **Intent into action.** This is a creative
proposal, not a cleared slogan or a claim of completed autonomous operation.

The differentiating story is the connection between intent, evidence, planning,
execution, and verification. Do not describe this as legally unique, patented,
certified safe, or superior to competitors without supporting evidence.

Initial audience: technical builders and developers integrating AI with physical
device interaction. Consumer convenience is the product direction, not proof of
consumer readiness. Medical or accessibility performance claims require separate
evidence and review.

## One product, consistent component names

After an owner-approved and screened name is selected:

| Surface | Naming rule | Purpose |
| --- | --- | --- |
| Product | `<Brand>` | Umbrella identity |
| GitHub repository | lowercase brand slug | Main source repository |
| User interface | `<Brand> Studio` | Setup, task review, results |
| Arm software | `<Brand> Runtime` | Validation, planning, execution records |
| AI workstream | `<Brand> AI` | Intent and perception components |
| Physical assembly | `<Brand> Workcell` | Hardware integration |

These are descriptive components, not separate companies or independent brands.
Do not publish literal `<Brand>` placeholders. Until adoption, retain RoCell in
active user-facing material. Do not rename individual third-party models.

## Voice and capability language

- Lead with what the user can do, then explain prerequisites and limitations.
- Prefer “requested target” to “intent payload,” and explain technical terms.
- Distinguish “accepted for planning,” “command sent,” “position reported,” and
  “intended input verified.” Never collapse them into a generic “success.”
- Say “tested under these conditions,” not “guaranteed safe” or “perfectly precise.”
- Label simulations, nominal geometry, historical runs, and measured results.
- Describe local-first operation by component; do not promise that installation,
  updates, or all optional services are offline.
- Keep workstream IDs and detailed evidence in developer references, with links
  from concise consumer explanations.

Example: “The target passed validation. Movement has not started.”
Avoid: “AI completed your task” when only a proposal has been accepted.

## Proposed visual direction

Calm, precise, and approachable; avoid hazard-stripe decoration, humanoid imagery,
or a logo tied exclusively to the current arm. A simple path-to-target symbol is
a possible direction, not a finalized or cleared logo.

| Role | Proposed value |
| --- | --- |
| Main text / dark surface | Ink `#142633` |
| Page surface | Mist `#F5F7FA` |
| Brand accent | Teal `#007F78` |
| Attention | Amber `#A45A00` |
| Error | Red `#B42318` |
| Typography | System sans-serif; monospace only for commands and data |

These are draft tokens, not installed UI assets or a contrast certification.
Test every actual foreground/background pairing, focus state, and disabled state
before release. Status must also use text or icons, never color alone. Preserve
clear separation between decorative branding and operational warnings.

After approval, keep vector logo masters, monochrome variants, and usage examples
in `assets/brand/`, and machine-readable UI tokens alongside them. Do not add
downloaded fonts or icons without recording their license and source.

## Ownership and consistency

The project owner approves name, spelling, pronunciation, slug, tagline, and
commercial identity. Both AI and arm contributors use this guide; neither lane
creates a competing product name. Brand-guide changes go through a documented PR.

Every public release checks the README, docs navigation, UI title, package
description, screenshots, repository description, and release notes against the
same approved identity. Rebranding does not change licenses, safety permissions,
protocol semantics, or historical evidence.
