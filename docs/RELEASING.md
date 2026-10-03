# Preparing a Tactevra experimental release

This procedure covers a **source-only experimental preview** for developers.
It does not qualify physical operation or publish an installer, firmware image,
model bundle, or new printable hardware package. Publication is a separate
maintainer decision; this document creates no tag or GitHub release.

Begin with the [current readiness dashboard](releases/READINESS.md), then use the
[release-record index](releases/README.md) to distinguish current status from
superseded exact-revision evidence. Never update a historical candidate record
to imply that it covers newer source.

The machine-readable
[`release-readiness.json`](../.github/release-readiness.json) registry is the
offline candidate gate. Ordinary policy checks validate its schema; candidate
mode fails for every entry still marked `open`. GitHub issue state is routing
context, not clearance. A reviewed change may mark an entry `cleared` only with
a resolution summary and durable evidence links. Repository-relative evidence
must exist in the tracked candidate; external links remain subject to human
review. This prevents network state or an administratively closed issue from
silently authorizing a candidate.

Vendor geometry that lacks established redistribution permission is link-only.
In particular, `hardware/static_overhead_camera/vendor/B0477.STEP` must remain
untracked; its source URL and digest are recorded in the adjacent vendor README.
The release-integrity policy rejects reintroducing that path.

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
- [ ] Produce an identity-bound clean-checkout receipt using
  `scripts/ci/verify_clean_checkout.py`. Review the
  [source-distribution footprint](SOURCE_DISTRIBUTION.md); do not describe the
  GitHub-generated archive as slim while the tracked tree remains above its
  reduction targets.
- [ ] Run the snapshot audit at the candidate revision and review findings;
  inspect release contents for private data, license notices, and unexpected
  artifacts. This heuristic scan is not a full-history or security certification.
- [ ] Review [`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md) against the
  exact candidate contents and resolved dependency set. Resolve every unknown
  or incompatible redistribution term. For the derived Waveshare kinematic
  projection, preserve the exact provenance, upstream-declared-MIT status, and
  incomplete-notice caveat recorded in
  [decision 0001](decisions/0001-waveshare-model-license-disposition.md); do not
  present vendor material as an Apache-2.0 Tactevra contribution.
- [ ] Run `python scripts/ci/check_release_integrity.py --mode candidate` at the
  candidate revision. Candidate mode must pass without removing a blocker merely
  to silence the check; resolve the linked review issue or record an approved
  exclusion/replacement disposition and its evidence in the same reviewed
  change. Reconcile the human-readable readiness dashboard and the machine-readable
  registry before selecting the candidate.
  A maintainer may instead dispatch the read-only
  [Preview candidate audit](../.github/workflows/preview-candidate-audit.yml)
  from the intended protected `main` revision and provide that exact full SHA as
  the identity assertion. The input does not select a checkout. The workflow
  verifies the GitHub-selected revision against the assertion, runs candidate
  integrity, the snapshot audit, maintained-document checks, and the source-
  archive footprint check. It uploads a 30-day review packet containing the
  exact Git-tree inventory, candidate metadata, check outcomes, and manifest
  digest. The packet is evidence for review, not a release asset; the workflow
  creates no tag, source archive, attestation, or GitHub release. A blocked
  candidate still receives a packet and then fails the final gate so reviewers
  can inspect the exact disposition without mistaking it for approval.
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

Ordinary CI runs the check in `policy` mode. That mode rejects newly tracked
private-backup paths, credential filenames, keys, executable/native binaries,
firmware images, model weights, and archives unless an exact path and SHA-256
allowance is reviewed in `.github/release-integrity-policy.json`. A policy-mode
pass means the inventory follows the recorded path policy and the readiness
registry is structurally valid; it does not override the stricter candidate
blockers, inspect file contents, or establish third-party
redistribution rights. The separate snapshot audit remains required.
The manual candidate workflow is additional release evidence, not a protected
merge check or a publication approval. Its uploaded review packet is not an
SBOM, binary provenance attestation, redistributable source bundle, or approval
record. A failed run is expected while a recorded candidate blocker remains and
must not be bypassed or reclassified as success.

## If a release needs correction

Do not move or reuse a published tag. For a defective preview, visibly mark the
release as withdrawn or superseded and link a corrected, separately tagged
preview. Record what changed and whether users need to stop using it. Follow
[private security reporting](../SECURITY.md) for sensitive details before public
disclosure. Preserve historical evidence rather than rewriting failed results.
