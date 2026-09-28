# Tactevra brand foundation

Updated September 26, 2026. The project owner selected **Tactevra** as the new
brand. Commercial clearance remains pending. The canonical repository is
`j-webtek/tactevra`; existing technical identifiers remain unchanged.

Canonical spelling: **Tactevra**. Lowercase slug: `tactevra`.
Recommended pronunciation: **tak-TEV-ruh**. Transitional description:
**Tactevra, formerly RoCell**.

Start here for consistent product language. Use the [naming review](NAMING_REVIEW.md)
for the selection record and the [migration plan](MIGRATION_PLAN.md) for rollout.
These documents do not change software or hardware behavior.

## Positioning

Product category: governed interface for embodied AI.

Positioning statement:

> Tactevra is an experimental, local-first nervous system for embodied AI,
> connecting language and vision to checked robot-arm actions in the physical
> world.

Short description for current use:

> Tactevra gives specialized AI models a governed path from understanding and
> visual evidence to bounded physical movement. Models propose what should
> happen; deterministic software decides what may move and verifies what
> happened next.

Messaging hierarchy:

1. **Category line:** Governed interface for embodied AI.
2. **Core metaphor:** The nervous system for embodied AI.
3. **Process line:** Observe. Understand. Check. Act. Verify.
4. **Trust line:** Physical intelligence, checked.

The core metaphor explains a system boundary; it must not be used to imply
sentience, biological equivalence, or autonomous capability. **Intent into
action** remains a compact legacy line for constrained placements, but it is
secondary to the hierarchy above. All lines are creative proposals, not cleared
slogans or claims of completed autonomous operation.

The differentiating story is the semantic bridge and closed feedback loop
between intent, visual evidence, planning, execution, and verification. Tactevra
does not hand model output directly to motors: AI proposes *what* to do, while
the runtime governs *how* and whether physical movement can occur. Do not
describe this as legally unique, patented, certified safe, or superior to
competitors without supporting evidence.

Initial audience: technical builders and developers integrating AI with physical
device interaction. Consumer convenience is the product direction, not proof of
consumer readiness. Medical or accessibility performance claims require separate
evidence and review.

## One product, consistent component names

Use these names for public documentation; this table does not rename deployed components:

| Surface | Naming rule | Purpose |
| --- | --- | --- |
| Product | Tactevra | Umbrella identity |
| GitHub repository | `j-webtek/tactevra` | Main source repository |
| User interface | Tactevra Studio | Setup, task review, results |
| Arm software | Tactevra Runtime | Validation, planning, execution records |
| AI workstream | Tactevra AI | Intent and perception components |
| Physical assembly | Tactevra Workcell | Hardware integration |

These are descriptive components, not separate companies or independent brands.
Update active public-facing material in the coordinated rollout; preserve RoCell
in historical records and compatibility identifiers. Do not rename third-party models.

## Voice and capability language

- Lead with what the user can do, then explain prerequisites and limitations.
- Pair the “nervous system” metaphor with a concrete explanation of the
  language/vision input, typed proposal boundary, deterministic runtime, arm,
  and observed feedback loop.
- Prefer “embodied AI” or “AI-to-physical-world interface” over “AI robot
  brain.” Tactevra connects components; it is not a claim of sentience.
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
