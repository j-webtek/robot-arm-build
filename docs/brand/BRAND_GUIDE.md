# Tactevra brand foundation

Updated September 26, 2026. The project owner selected **Tactevra** as the new
brand. Commercial clearance remains pending; GitHub-facing documentation uses
Tactevra while the repository remains
`j-webtek/robot-arm-build`, and existing technical identifiers remain unchanged.

Canonical spelling: **Tactevra**. Lowercase slug: `tactevra`.
Recommended pronunciation: **tak-TEV-ruh**. Transitional description:
**Tactevra, formerly RoCell**.

Start here for consistent product language. Use the [naming review](NAMING_REVIEW.md)
for the selection record and the [migration plan](MIGRATION_PLAN.md) for rollout.
These documents do not change software or hardware behavior.

## Positioning

Product category: local-first robotics software and workcell integration.

Positioning statement:

> An experimental local-first robotics platform connecting user intent,
> visual evidence, and checked physical actions.

Short description for current use:

> Tactevra brings AI target proposals and robot control into one inspectable
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

Use these names for public documentation; this table does not rename deployed components:

| Surface | Naming rule | Purpose |
| --- | --- | --- |
| Product | Tactevra | Umbrella identity |
| GitHub repository | `tactevra` (planned) | Main source repository |
| User interface | Tactevra Studio | Setup, task review, results |
| Arm software | Tactevra Runtime | Validation, planning, execution records |
| AI workstream | Tactevra AI | Intent and perception components |
| Physical assembly | Tactevra Workcell | Hardware integration |

These are descriptive components, not separate companies or independent brands.
Update active public-facing material in the coordinated rollout; preserve RoCell
in historical records and compatibility identifiers. Do not rename third-party models.

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
or a logo tied exclusively to the current arm. The initial GitHub identity uses a
path-to-target symbol and a dark wordmark banner in [assets/brand](../../assets/brand/README.md).
This is a repository presentation asset, not a legally cleared logo.

| Role | Proposed value |
| --- | --- |
| Main text / dark surface | Ink `#142633` |
| Page surface | Mist `#F5F7FA` |
| Brand accent | Teal `#007F78` |
| Accent on dark banner | Mint `#58D5C4` |
| Attention | Amber `#A45A00` |
| Error | Red `#B42318` |
| Typography | System sans-serif; monospace only for commands and data |

These are draft tokens, not installed UI assets or a contrast certification.
Test every actual foreground/background pairing, focus state, and disabled state
before release. Status must also use text or icons, never color alone. Preserve
clear separation between decorative branding and operational warnings.

Keep vector masters in `assets/brand/`. Monochrome variants and application UI
tokens remain future work; this GitHub refresh does not restyle the running app. Do not add
downloaded fonts or icons without recording their license and source.

## Ownership and consistency

The project owner approves name, spelling, pronunciation, slug, tagline, and
commercial identity. Both AI and arm contributors use this guide; neither lane
creates a competing product name. Brand-guide changes go through a documented PR.

Every public release checks the README, docs navigation, UI title, package
description, screenshots, repository description, and release notes against the
same approved identity. Rebranding does not change licenses, safety permissions,
protocol semantics, or historical evidence.
