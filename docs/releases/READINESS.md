# Tactevra experimental-preview readiness

**Document status:** Current release-readiness dashboard  
**Authority:** Status and routing only; this page does not select a candidate, approve publication, or authorize hardware operation  
**Last reconciled:** September 27, 2026, against protected `main` at `91c30eb`

Tactevra has not published a GitHub release. No source commit, tag, release notes,
or downloadable asset set is currently approved. This dashboard is the concise
public summary of the first source-only experimental preview. Use
[issue #57](https://github.com/j-webtek/tactevra/issues/57) for the actionable
checklist and the [release procedure](../RELEASING.md) for the required process.

`main` may advance after the reconciliation commit above. A later merge does not
silently become the candidate and does not inherit earlier evidence. The exact
candidate SHA will be selected only after the blocking owner evidence closes.

## Current gate summary

| Gate | State | Evidence or next action |
| --- | --- | --- |
| Repository governance | **Ready for candidate preparation** | Protected `main` requires strict, app-bound offline verification and CodeQL checks; linear history, administrator enforcement, and conversation resolution remain enabled. |
| Tracked-content policy | **Ready for candidate preparation** | Release-integrity policy and snapshot review tooling are present. The earlier Arducam redistribution blocker was resolved in [issue #45](https://github.com/j-webtek/tactevra/issues/45). |
| External AI artifact identity | **Blocked on AI-owner evidence** | Complete the exact checkpoint manifest and artifact-absent/artifact-present proof in [issue #56](https://github.com/j-webtek/tactevra/issues/56). |
| Reviewable AI evidence disposition | **Blocked on AI-owner evidence** | Land the focused replacement evidence described in [issue #61](https://github.com/j-webtek/tactevra/issues/61); do not revive the superseded bulk proposal. |
| Waveshare URDF redistribution basis | **Blocked on repository/arm-owner evidence** | Resolve, replace, or remove the derived kinematic projection as required by [issue #88](https://github.com/j-webtek/tactevra/issues/88); do not infer a license from silence. |
| AI and arm compatibility dispositions | **Not started for a candidate** | Record both workstream dispositions only after an exact candidate SHA is selected. |
| Exact candidate commit | **Not selected** | Wait for issues #56, #61, and #88 to close, then choose one full SHA already on protected `main`. |
| Candidate audit and fresh-checkout review | **Not run** | Run against the selected SHA; ordinary development CI is not substitute evidence. |
| Tag and pre-release | **Not approved or published** | Requires explicit maintainer approval of the exact tag, SHA, notes, and source-only asset scope. |

## What is already established

- The first preview is scoped to GitHub-generated source archives. It excludes
  installers, firmware images, trained model bundles, and newly qualified
  printable hardware packages.
- Protected `main` requires four offline verification jobs and three CodeQL
  analyzer jobs: Actions, JavaScript/TypeScript, and Python.
- Repository policy distinguishes reviewable source and compact scorecards from
  external checkpoints and bulk generated evidence.
- Historical candidate and baseline records remain bound to their recorded
  commits. None is the current candidate.
- A merge, development CI pass, CodeQL pass, simulation result, or controller
  readback does not qualify physical typing or approve a release.

## Blocking path

1. The AI workstream completes [issue #56](https://github.com/j-webtek/tactevra/issues/56)
   with exact artifact identity, deterministic clean-clone behavior, and a
   separate verified artifact-present result.
2. The AI workstream completes [issue #61](https://github.com/j-webtek/tactevra/issues/61)
   with reviewable compact evidence and an approved disposition for bulk output.
3. The repository and arm owners complete
   [issue #88](https://github.com/j-webtek/tactevra/issues/88) with a reviewed
   redistribution basis or a replacement/removal disposition for the derived
   Waveshare URDF.
4. The maintainer reconciles issue #57, selects a full SHA on protected `main`,
   and creates a new candidate record. Do not reuse the superseded `dcd87db`
   record.
5. AI and arm owners record compatibility dispositions against that same SHA.
6. The maintainer runs the exact-SHA candidate audit, fresh-checkout checks,
   tracked-content/provenance review, and release-note review.
7. Publication occurs only after explicit approval of the exact tag, SHA, notes,
   and asset scope. A candidate passing every technical check is still not
   self-authorizing.

## Ownership and routing

| Work | Responsible lane | Completion signal |
| --- | --- | --- |
| Pose-checkpoint manifest and verification | AI | Focused PR merged; issue #56 acceptance evidence recorded |
| Compact AI evidence and bulk-output disposition | AI with repository review | Focused PR merged; issue #61 acceptance evidence recorded |
| Waveshare URDF redistribution disposition | Repository with arm-owner review | Durable rights evidence or reviewed replacement/removal merged; issue #88 closed |
| Arm compatibility disposition | Arm | Review recorded against the selected candidate SHA |
| Repository inventory, candidate audit, and release notes | Repository maintainer | Exact-SHA record links every required result |
| Publication approval | Repository owner | Explicit approval names the tag, SHA, notes, and source-only assets |

No lane may approve another lane's technical evidence. Repository checks can
verify shape, identity, and policy compliance; they cannot establish model
accuracy, physical clearance, successful device input, or third-party rights.

## Dashboard maintenance rules

- Update this page when a listed gate changes state, not for every development
  merge.
- Record action-level evidence and discussion on issue #57 or its linked blocker;
  keep this page concise.
- Name exact commits for candidate evidence. Never describe moving `main` as the
  tested release.
- Preserve failed and superseded records. Do not rewrite them to match a newer
  candidate.
- If this page and an exact-SHA candidate record disagree, stop and reconcile the
  discrepancy before publication.

For historical records, use the [release-record index](README.md). For the full
manual process, use [preparing an experimental release](../RELEASING.md).
