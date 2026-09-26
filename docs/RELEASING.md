# Preparing a Tactevra experimental release

This procedure covers a **source-only experimental preview** for developers.
It does not qualify physical operation or publish an installer, firmware image,
model bundle, or new printable hardware package. Publication is a separate
maintainer decision; this document creates no tag or GitHub release.

## Release identity and scope

Use a Tactevra display name and an explicitly experimental tag, for example
`tactevra-v0.1.0-alpha.1`, only after the maintainer confirms that name and its
availability. This is a repository snapshot label, not a change to the existing
`rocell` Python distribution version or protocol identities. Keep historical
RC02/RC03 hardware and firmware revision names unchanged.

Link the exact source commit and its validation results. Never describe a moving
`main` branch as the tested release. The [draft notes](releases/EXPERIMENTAL_PREVIEW_DRAFT.md)
are a starting point, not a completed qualification record.

## Preparation checklist

- [ ] Choose the proposed tag, title, full commit SHA, and maintainer responsible
  for publication. Confirm the candidate is on protected `main`.
- [ ] Review all changes since the previous published preview, or the declared
  baseline for a first release. Include both AI and arm workstream changes.
- [ ] Review README, getting started, project status, support, and security
  guidance against that exact commit. Date capability claims; do not present an
  older status checkpoint as a review of newer code.
- [ ] Have AI and arm maintainers record applicable compatibility checks against
  the shared contracts and any known breaks. Keep model accuracy, simulation,
  controller feedback, and externally measured performance separate.
- [ ] Record all four required CI job results for the exact source revision and
  inspect the merged-main run. If the candidate changes, rerun validation.
- [ ] From a fresh checkout at the candidate SHA, reproduce the documented
  [offline setup and checks](CI.md). Record OS, Python version, commands, results,
  and dependency versions. CI covers selected tests, not the complete suite.
- [ ] Run the snapshot audit at the candidate revision and review findings;
  inspect release contents for private data, license notices, and unexpected
  artifacts. This heuristic scan is not a full-history or security certification.
- [ ] List known limitations, including native-helper prerequisites, absent lab
  records, unqualified real-camera localization, and physical typing status.
- [ ] Review the draft notes and remove unresolved placeholders only when their
  facts have been established. Do not publish incomplete evidence fields.
- [ ] Obtain explicit maintainer approval for the exact tag, SHA, notes, and any
  proposed downloadable assets. Record it in the release preparation PR.

## Publication and verification

After approval, create an annotated tag pointing to the reviewed SHA, verify the
remote tag resolves to that SHA, and create the GitHub release marked
**pre-release**, not the latest stable release. Do not let a release tool silently
choose the then-current branch tip or invent the tag target.

For the first preview, use GitHub's generated source archives only. They contain
the repository snapshot, including historical material; they are not a curated
installer or firmware deployment bundle. No additional binaries or trained model
weights are included by this plan. The repository is large; prefer a shallow
clone at the selected tag when appropriate. Source archives lack Git metadata,
so checks that use `git ls-files` need a checkout instead.

Verify the published title, experimental warning, tag target, source downloads,
and links. Record the release URL and final evidence in the release PR. No release
step should connect to hardware or upload firmware. CI does not publish releases.

## If a release needs correction

Do not move or reuse a published tag. For a defective preview, visibly mark the
release as withdrawn or superseded and link a corrected, separately tagged
preview. Record what changed and whether users need to stop using it. Follow
[private security reporting](../SECURITY.md) for sensitive details before public
disclosure. Preserve historical evidence rather than rewriting failed results.
