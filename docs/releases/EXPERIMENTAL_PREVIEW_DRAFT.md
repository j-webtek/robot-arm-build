# Tactevra experimental source preview — draft notes

**Unpublished draft. Not a stable product, installer, or hardware deployment.**

Proposed title: **Tactevra v0.1.0-alpha.1 — experimental source preview**.
Proposed tag: `tactevra-v0.1.0-alpha.1` (not created or approved).
Proposed source: `dcd87db12c9593f1c17b7a222cb711c4fbe7845e`, a merged snapshot,
not the moving main branch. See the [candidate record](CANDIDATE_DCD87DB.md)
for verification and unresolved gates. **Publication is on hold.**

This preview is for developers exploring offline request interpretation,
model-to-arm contracts, and simulated planning. Complete the
[release checklist](../RELEASING.md) before publication. These notes and the
candidate record are later preparation documents, not files in that pinned
snapshot. Including them in a different source target requires revalidation.

A [pinned source-baseline verification](BASELINE_2026-09-26.md) is available for
`b1bb742`. It is supporting evidence, not approval of a final release candidate.

The [compatibility and content review](COMPATIBILITY_CONTENT_REVIEW_2026-09-26.md)
at `3660fc4` found no incompatibility in the tested offline selection. Release
content/provenance review and both workstream owners' sign-off remain pending;
generated source archives also include tracked CAD and print-package assets.
The project owner has since [confirmed original authorship of the CAD/print
designs](../HARDWARE_PROVENANCE.md); software/model attribution and workstream
sign-off remain separate.

## What this preview is intended to include

- Tactevra's public-facing documentation and branding, with compatible `rocell`
  commands and historical identifiers preserved.
- Introductory offline request interpretation and nominal coordinate previews.
- AI/arm v2 proposal contracts and software checks: AI supplies named coordinates;
  the arm owns motion policy and checked planning. Nominal examples grant no
  execution authority.
- Zero-write controller-byte previews, lifecycle and acknowledgment rehearsals,
  and r97 firmware staging source. r97 is an offline compiled candidate, not
  installed or independently qualified firmware; no firmware binary is offered.
- Scoped Linux/Windows CI, explicit audit-fixture review, support guidance, and
  private vulnerability reporting.

Generated source archives include tracked historical CAD/print material and a
vendor camera geometry file. They are not software-only packages or newly
qualified print bundles. Vendor redistribution review remains unresolved.

## Important limitations

This is not a demonstrated camera-to-arm physical typing system. Synthetic
geometry, offline planning, and controller feedback do not establish measured
tip accuracy or successful device input. Real-camera localization, calibration,
tool geometry, and contact qualification require their own evidence.

Python package and CLI names remain `rocell`; the Tactevra release label does not
rename schemas or upgrade historical firmware. Dependencies use supported ranges,
not a complete lockfile. A fresh checkout lacks private lab records, local model
installations, and generated native helpers. Selected CI passes are not a
full-suite pass, a security certification, or authorization to move an arm.

## Candidate evidence to complete

| Required item | Status |
| --- | --- |
| Approved title and tag | Proposed above; explicit approval pending |
| Exact full source SHA on main | Proposed `dcd87db12c9593f1c17b7a222cb711c4fbe7845e` |
| Included changes and compatibility review by both workstreams | Pending |
| Four hosted CI results and merged-main run | Passed; linked in candidate record |
| Fresh-checkout setup and example results | See candidate record for scoped results |
| Snapshot audit and release-content review | See candidate record; vendor rights and owner dispositions remain open |
| Known failures and unavailable prerequisites | Native helpers, broader collection limits, physical calibration and qualification remain outside portable checks |
| Publication approval and final release URL | Not approved or published |

## Getting started and help

Follow [getting started](../GETTING_STARTED.md) for hardware-free examples and
[verification tiers](../CI.md) to understand their boundaries. Use
[support](../../SUPPORT.md) for ordinary questions and
[security reporting](../../SECURITY.md) for sensitive findings. Do not run
historical physical test scripts as part of installing this preview.
