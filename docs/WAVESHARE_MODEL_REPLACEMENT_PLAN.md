# Independent Waveshare kinematic-model replacement plan

**Status:** Prepared fallback for [issue #88](https://github.com/j-webtek/tactevra/issues/88)  
**Authority:** Process proposal only; this document is not legal advice, a rights determination, or permission to redistribute any existing file

Issue #88 remains the sole registry-controlled preview blocker. Upstream package
metadata and the requested clarification are useful evidence, but neither silence
nor a repository-level license automatically establishes the provenance of every
derived artifact. This fallback gives the project a bounded way to replace the
current projection if durable clearance does not arrive.

## Completion choices

The issue may close only after repository and arm-owner review accepts one of:

1. durable, artifact-specific redistribution evidence;
2. an independently produced replacement merged with the evidence below; or
3. removal of the affected artifact and every maintained dependency on it.

This plan does not preselect a choice.

## Independent replacement procedure

1. Freeze the current artifact as excluded reference material. Record its digest,
   path, and dependency inventory, but do not use its expressive structure,
   comments, names, mesh organization, or XML layout as an implementation source.
2. Write a neutral functional specification using independently measured hardware
   dimensions and public factual interface requirements. Cite every measurement
   source and include uncertainty. Do not copy vendor model text or geometry.
3. Have a separate implementer create a new model from that specification. When
   two people are unavailable, retain a dated declaration of the source boundary,
   inputs consulted, and steps used to avoid copying.
4. Give the replacement a new neutral identity and file path. Preserve API
   compatibility only where tests establish required behavior; do not preserve
   expressive details merely because the old artifact contained them.
5. Validate joint count, axes, limits, transforms, and forward-kinematic samples
   against physical measurements and independently stated requirements. Set
   tolerances before inspecting results. Behavioral similarity is test evidence,
   not proof of provenance.
6. Update manifests, simulation locks, target profiles, documentation, and tests
   in one reviewed migration. Regenerate derived evidence rather than rewriting
   historical records.
7. Retain a replacement provenance record containing contributors, dates,
   measurement sources, source/asset digests, test commands, results, review
   dispositions, and known limitations.
8. Run source-distribution, release-integrity, AI/arm contract, and clean-checkout
   checks. The arm owner must confirm that the replacement does not silently
   change controller semantics or authorize physical execution.

## Acceptance evidence

- An explicit dependency inventory showing no maintained path still requires the
  disputed artifact.
- A reviewable functional specification and measurement record.
- A replacement provenance record with exact commit and file digests.
- Passing deterministic kinematic, shared-contract, source-distribution, and
  fresh-checkout checks at that exact commit.
- Recorded repository and arm-owner dispositions in issue #88.
- A readiness-registry update that cites the merged replacement or removal.

Until all applicable evidence exists, keep issue #88 and the experimental-preview
gate open. This plan can reduce waiting time; it cannot manufacture permission or
turn a planned replacement into completed provenance.
