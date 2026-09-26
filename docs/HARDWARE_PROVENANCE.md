# Tactevra hardware-design provenance

## Owner confirmation — September 26, 2026

During release-content review, the project owner was asked whether the repository's
CAD/print designs were entirely their original work or included third-party designs.
The owner replied: **“yes entirely my work, proceed best next steps.”**

This records the owner's authorship confirmation for the CAD/print designs reviewed
at source baseline `3660fc4d956d8503e2ae91a0cef624449058f926`, including the historical
RC02/RC03 workcell designs and static-overhead-camera print pack. It resolves the
open authorship question in the [release-content review](releases/COMPATIBILITY_CONTENT_REVIEW_2026-09-26.md).
It is an owner declaration, not an independent asset-by-asset forensic audit.

The repository's existing [Apache-2.0 license](../LICENSE) and
[public license statement](../README.md#license) remain unchanged. This record
does not add a new license, change copyright attribution, or claim trademark,
patent, regulatory, or physical-safety clearance.

## Scope and boundaries

- The confirmation concerns the project's CAD/print designs, not Waveshare hardware,
  upstream firmware, Python dependencies, model weights, vendor documentation,
  or third-party software.
- Embedded slicer settings, metadata, or other non-design content in containers
  are not independently audited by this declaration. Preserve any applicable
  third-party notices.
- Frozen ZIP/3MF/STEP/STL files are unchanged. This companion record supplies
  provenance context without changing historical file hashes.
- New imported designs or third-party material need their own source and license
  records; this declaration is not blanket approval for future additions.

### Explicit vendor exception

The tracked [Arducam geometry proxy](../hardware/static_overhead_camera/vendor/README.md),
`B0477.STEP`, is identified by its own record as a vendor download, not an original
project design. The owner's confirmation above does not establish redistribution
rights for that file. The source-preview review requires a recorded license or
permission disposition before publishing archives containing it. No asset was
removed or relicensed by this clarification.

A design's authorship does not establish print readiness, fit, strength, electrical
compatibility, or safe robot operation. Follow the exact hardware revision's
measurement and qualification requirements.
