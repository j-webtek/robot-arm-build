# Decision 0001: Waveshare model license disposition

**Status:** Accepted

**Date proposed:** 2026-09-29

**Decision owners:** Repository owner and repository-maintenance workstream

**Issue:** [#88](https://github.com/j-webtek/tactevra/issues/88)

**Pull request:** [#185](https://github.com/j-webtek/tactevra/pull/185)

## Context

Tactevra's reduced RoArm-M3 kinematic projection is derived from
`src/roarm_main/roarm_description/urdf/roarm_m3/roarm_m3.xacro` at Waveshare
commit `40dbd84b553695212fab713e8465f817ba95454d`. The containing ROS package's
`package.xml` has declared `MIT` since its initial commit. The upstream tree does
not contain an applicable complete MIT license text or copyright notice, the
Xacro has no file-level header, and GitHub does not identify a repository-level
license.

The project requested clarification in
[waveshareteam/roarm_ws#12](https://github.com/waveshareteam/roarm_ws/issues/12).
No response was available when this decision was recorded. Silence is not
treated as additional permission and does not strengthen the upstream record.

The projection is deeply integrated into the current simulation and runtime
tests. Removing or externalizing it immediately would break a large validated
software surface without changing how the installed arm is controlled.

## Decision

The project will retain and use the projection under the explicit package-level
MIT declaration, recording its status as **upstream-declared MIT; complete
notice and scope unconfirmed**.

Tactevra will:

1. preserve the upstream repository, commit, path, and content digests;
2. state the missing notice and unconfirmed scope wherever redistribution is
   summarized;
3. never present the projection or other Waveshare material as an original
   Apache-2.0 Tactevra contribution;
4. keep the official SDK's AGPL-3.0 terms separate from Tactevra's independently
   written protocol adapter;
5. continue to reference firmware, drawings, and other vendor artifacts by
   source and digest unless their redistribution terms are independently clear;
   and
6. revisit this disposition if Waveshare supplies a complete notice, narrows the
   declaration, or otherwise changes the available rights evidence.

This is a repository-owner risk disposition based on the upstream metadata. It
is not a legal opinion or a claim that the absent notice was recovered.

## Alternatives considered

- **Wait indefinitely for clarification.** Rejected because no response time is
  guaranteed and the open wait did not improve the evidence already recorded.
- **Describe the artifact as unqualified MIT without a caveat.** Rejected
  because that would erase a material provenance limitation.
- **Immediately remove or externalize the projection.** Retained as a future
  option, but not selected now because the file is embedded throughout the
  tested simulation/runtime surface.
- **Produce an independent replacement.** Retained as the preferred way to
  eliminate the ambiguity when engineering capacity permits.

## Consequences

Issue #88 and the corresponding preview-readiness blocker can close because the
repository owner has selected and documented a disposition rather than waiting
for upstream clarification. Source users can continue using the tested model
and Waveshare integration surfaces.

The incomplete upstream notice remains a disclosed risk. A distributor with a
different risk threshold may exclude the projection, retrieve upstream sources
directly, or complete the independent replacement plan before distribution.

## Compatibility and migration

No file path, model hash, runtime contract, controller protocol, firmware, or
hardware behavior changes. The independent replacement plan remains available
and would require a separate reviewed migration before changing model identity.

## Evidence and dispositions

- Upstream package metadata at commit
  `40dbd84b553695212fab713e8465f817ba95454d` explicitly declares `MIT`.
- The pinned raw Xacro SHA-256 is
  `b6333849d0e377008eee0a87a5b8cdcf44f7a73edf3d7600e95506a023a234b6`.
- The retained local projection SHA-256 is
  `a565718e7d74b07702802cf41eb9549a6e38e50b5e80aa9b887ab1ae3d0d8190`.
- The repository owner directed continued use with the declaration and caveat
  recorded together.
- No arm numerical, runtime, AI, or hardware disposition changes are inferred.

## Explicit exclusions

This decision does not relicense Waveshare material under Apache-2.0, supply a
missing copyright notice, approve firmware redistribution, alter the AGPL-3.0
SDK obligations, authorize a release by itself, or authorize physical motion.

## Supersession

None. A later rights clarification or independent-model migration should cite
and supersede this record.
