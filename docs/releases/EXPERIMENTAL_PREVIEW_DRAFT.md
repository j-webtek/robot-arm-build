# Tactevra experimental source preview — draft notes

**Unpublished draft. Not a stable product, installer, or hardware deployment.**

Proposed scope: a source snapshot for developers exploring offline request
interpretation, model-to-arm contracts, and simulated planning. The release tag,
source commit, publication approval, and candidate-specific validation remain
unselected. Complete the [release checklist](../RELEASING.md) before publication.

A [pinned source-baseline verification](BASELINE_2026-09-26.md) is available for
`b1bb742`. It is supporting evidence, not approval of a final release candidate.

The [compatibility and content review](COMPATIBILITY_CONTENT_REVIEW_2026-09-26.md)
at `3660fc4` found no incompatibility in the tested offline selection. Release
content/provenance review and both workstream owners' sign-off remain pending;
generated source archives also include tracked CAD and print-package assets.

## What this preview is intended to include

- Tactevra's public-facing documentation and branding, with compatible `rocell`
  commands and historical identifiers preserved.
- Introductory offline request interpretation and nominal coordinate previews.
- AI/arm integration contracts and software checks. Describe the exact included
  increments after selecting and reviewing the candidate commit.
- Scoped Linux/Windows CI, explicit audit-fixture review, support guidance, and
  private vulnerability reporting.

These are scope intentions, not claims that a release candidate has passed.

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
| Approved title and tag | Not selected |
| Exact full source SHA on main | Not selected |
| Included changes and compatibility review by both workstreams | Pending |
| Four hosted CI results and merged-main run | Pending for selected candidate |
| Fresh-checkout setup and example results | Pending for selected candidate |
| Snapshot audit and release-content review | Pending for selected candidate |
| Known failures and unavailable prerequisites | Populate from candidate review |
| Publication approval and final release URL | Not approved or published |

## Getting started and help

Follow [getting started](../GETTING_STARTED.md) for hardware-free examples and
[verification tiers](../CI.md) to understand their boundaries. Use
[support](../../SUPPORT.md) for ordinary questions and
[security reporting](../../SECURITY.md) for sensitive findings. Do not run
historical physical test scripts as part of installing this preview.
