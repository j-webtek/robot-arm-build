# Tactevra maintainer checklist

Use this short checklist during a repository review or before handing maintenance
to another contributor. It is a manual procedure, not a scheduled monitor or a
promise of support response times. For policy and dated settings evidence, see
[repository operations](REPOSITORY_OPERATIONS.md).

This lane maintains the project's GitHub home. AI and arm owners remain responsible
for their implementation and technical qualification. Nothing here authorizes
device access, restarts, torque changes, movement, or release publication.

## 1. Triage incoming work

- [ ] Check [open issues](https://github.com/j-webtek/robot-arm-build/issues),
  [pull requests](https://github.com/j-webtek/robot-arm-build/pulls), and
  [workflow runs](https://github.com/j-webtek/robot-arm-build/actions).
  Distinguish a failed check from a cancelled or still-running job.
- [ ] Route ordinary questions through [support](../SUPPORT.md). Apply the
  existing type/area labels; link duplicates rather than losing their evidence.
  Ask for the missing reproduction detail instead of guessing a cause.
- [ ] Inspect security reports and alerts through the restricted
  [Security view](https://github.com/j-webtek/robot-arm-build/security).
  Follow [security reporting](../SECURITY.md); never copy private findings into a
  public maintenance report. Enabled notifications do not prove delivery.
- [ ] Give each actionable item a next step and completion criterion. Record an
  owner only after agreement. A blocked item stays open with its dependency;
  inactivity alone is not a reason to close it.

## 2. Review each proposed change

- [ ] Read the diff and [PR handoff](../.github/pull_request_template.md), not just
  its title. Keep unrelated work out of the branch and preserve other workers'
  uncommitted files. Stage explicit paths.
- [ ] Confirm which lane owns the change and whether another lane's review is
  needed. For shared contracts, link producer and consumer evidence at the
  reviewed commit. Do not record approval on someone else's behalf.
- [ ] Match required [CI checks](CI.md) to the current revision. New commits or
  reconciliation with main require fresh checks. Missing or pending checks are
  not passes; do not use administrator bypass to finish a merge.
- [ ] Check the public impact: capability, limitation, setup, or none. Update
  the appropriate entry document or link an explicit follow-up with a reason.
  Keep model evaluation, simulation, controller feedback and physical results
  distinct. CI is not evidence of successful typing.
- [ ] Review new files and archives for private data and third-party provenance.
  Use the [snapshot audit and fixture policy](AUDIT_FIXTURE_REVIEW.md); a clean
  heuristic result does not replace inspection or establish redistribution rights.

## 3. Close the handoff after merge

- [ ] Record the merge commit and relevant check links on the PR or tracking
  issue. Close only the acceptance criteria actually completed.
- [ ] Identify the next action, responsible lane, and unresolved prerequisites.
  Update the [shared workplan](../software/ai/docs/SHARED_AI_ARM_WORKPLAN.md) only
  when engineering evidence changes; do not duplicate its history in operations notes.
- [ ] Keep [project status](../PROJECT_STATUS.md) readable and date its evidence
  checkpoint. Do not silently promote a branch proposal into a released feature.
- [ ] A merge is not a release. For publication, use the separate
  [release checklist](RELEASING.md), an exact candidate commit and its own reviews.
  If the candidate changes, reassess its evidence instead of reusing old sign-offs.

## 4. Check the newcomer path

- [ ] Follow README → getting started → support. Check that examples describe
  what users will see and what they do **not** establish.
- [ ] Run `python scripts/ci/check_docs.py` from the repository root after entry
  documentation changes. It checks selected local file links and SVG syntax,
  not remote URLs, anchors, prose accuracy or rendered appearance.
- [ ] Preview changed Markdown on GitHub and check its changed links. Keep
  Tactevra branding consistent without renaming `rocell` interfaces or historical
  evidence. Use the [brand guide](brand/BRAND_GUIDE.md).
- [ ] If setup commands changed, repeat the relevant clean-environment
  [offline checks](CI.md). Do not invoke hardware scripts or broad test discovery
  as a shortcut to a documentation smoke test.

## Record a review without creating another ledger

Add a short comment to the relevant issue or PR. A routine review with no change
does not need a new issue. Use this outline when a handoff is useful:

```text
Reviewed: <date, scope, exact source/PR commit>
Outcome: <completed items and evidence links>
Not established: <limits of checks performed>
Open dependencies: <issue/PR, next action, agreed owner or unassigned>
Public docs: <updated pages or why no change was needed>
Release / hardware actions: none, unless separately authorized and recorded
```

Keep personal contact details, security findings and private exports out of this
public comment. Vendor-rights questions belong with the responsible expert;
an unanswered inquiry is not permission, and documentation work does not lift
a release hold.
