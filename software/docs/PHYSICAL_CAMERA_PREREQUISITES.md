# Physical camera prerequisite documents

Implemented file-only intake guidance for canonical stages 1–4. This is not a
stage assessor, received-unit inspection, power observation, permit or release.
It pairs with [the developer playbook](CAMERA_ARM_DEVELOPER_PLAYBOOK.md) and
[physical camera selection](PHYSICAL_CAMERA_SELECTION.md).

## API

`application/physical_camera_prerequisites.py` exposes:

```python
collect_physical_camera_prerequisites(
    workspace,
    *,
    source_sha256,
    session_id,
    launch_session_id,
    cancellation,                 # threading.Event, supplied by the action
    deadline_ns,                  # original monotonic deadline, at most 30 s away
    selection=None,               # exact PhysicalCameraSelection
    source_preflight_report=None, # exact PhysicalSourcePreflightReport
    expected_source_preflight_sha256=None,
) -> PhysicalCameraPrerequisites

verify_physical_camera_prerequisites(
    payload,
    *,
    expected_source_sha256,
    expected_session_id,
    expected_launch_session_id,
    expected_evidence_sha256,
) -> PhysicalCameraPrerequisites
```

The frozen artifact owns `payload: bytes`, `evidence_sha256`, `to_dict()` and
`safe_summary()`. Construction, restoration and projections perform no I/O.
Both dictionaries are detached. `PhysicalCameraPrerequisitesError.code` is a
fixed diagnostic code; exception text does not expose provider or filesystem
error strings.

Collection checks cancellation/deadline around every read, validator and broad
source fingerprint. A late failure returns no current prerequisite artifact and
does not refresh the deadline or retry. Each file is at most 64 KiB; the complete
artifact is at most 112 KiB. Oversize input is refused, not trimmed.

## Exact source scope and provenance

The four fixed retained documents are:

1. `software/config/physical_onboarding_stage_catalog.json`
2. `software/config/physical_onboarding_hazards.json`
3. `software/config/configuration_epochs.json`
4. `hardware/static_overhead_camera/hardware_intake_template.csv`

The collector uses their existing validators, including the strict 55-row intake
question-set validator. Bounded regular-file reads reject links/reparse paths;
the exact bytes/hash/length are retained, and validator hashes plus a second
snapshot must agree. The separately computed broad software fingerprint must
match the supplied launch source before and after collection. This is bounded
before/after consistency, **not hostile-writer exclusion or a trusted release**.
No hardware or OS device inventory is performed, and the CSV/configs are never
modified.

The full original source bytes are retained as UTF-8 text with byte counts and
hashes. Derived rows can therefore be checked against their actual question
sources. Pure restoration rechecks canonical structure, byte/hash relationships,
stage/effect/intake/hazard/epoch scope and derived requirements. It does not rerun
filesystem loaders or establish that a self-authored digest is trustworthy: the
caller must supply the original hash from its trusted M1 retention boundary.

An optional selection must be the exact physical-domain selection type, bound
to the same source and launch; its opaque endpoint is not shown in the summary.
An optional source-preflight report requires its independently retained hash.
Its original bytes and **separate source-only session origin** are retained;
neither a coherent nor a held report becomes canonical stage acceptance. This
module does not audit the preflight's original M1 journal.

## Guided requirements, not observations

The summary schema is `rocell.physical_camera_prerequisites_summary.v1`:

- `binding`: exact source, M1 session and wizard launch IDs.
- `source_files`: four fixed relative paths, roles, byte counts and hashes.
- `stages`: exactly the first four canonical stages. Each retains its effect
  class, disconnected-power requirement, artifact requirements, hazard IDs and
  stage-owned intake rows. Row counts are **0, 0, 16, 1**.
- `hazards`: the full controlled requirements for HZ-007/008/009/010/012.
- `epochs`: all eight policy dependencies, each `UNMEASURED` with `value:null`.
- `metadata_selection`: the selection's four-hash safe summary or `null`.
- `source_preflight`: source-only outcome/hash/original session or `null`.
- `missing_requirements`: explicit insufficiency codes, including the absence
  or metadata/source-only limitations of the optional context.

Every intake row retains its exact assembly/measurement/unit/question, original
CSV phase/status/notes, and the needed observation fields: value, method,
observation time, operator, evidence references and uncertainty. All actual
`observation` fields are `null`. No `PASS`, `NA`, accepted checkbox or guessed
measurement is generated.

Stage 3 owns INT-001–009, INT-017 and INT-019–024. Stage 4 owns INT-018. The CSV
`receipt` section is **not** the canonical stage-3 subset. INT-005 flatness retains
`OPEN_LIMIT`: measurement/evidence is required now, but limit acceptance remains
`DEFERRED_LIMIT` at `noncontact_acceptance`, requiring
`TARGET_ACCURACY_BUDGET_CLOSED`. Nominal 610 mm board width is displayed as a
candidate requirement, never copied into an observation.

Top status is always `REQUIREMENTS_RETAINED_NOT_ASSESSED`; stage status is always
`REQUIREMENTS_ONLY`; power is `UNKNOWN`. `canonical_stage_pass`, `qualified`,
`physical_authority` and `device_io_performed` remain exactly false.

## Service integration and tests

The caller owns explicit tickets, current enrollment/source revalidation, one-use
collection, M1 leases and full-byte retention. A stage may remain
`WAITING_OPERATOR` after retaining this document. Completion logging must precede
publishing its current UI projection. Reopen may restore verified bytes without
collecting again; it must not imply that requirements have been satisfied.

Current measured no-context artifact: **67,958 bytes**, approximately 22.7 KiB
for the safe summary. The complete public diagnostic envelope, including both
summary and original document, is covered by a lossless sanitizer test and fits
the existing 128 KiB bound in the tested optional held-preflight case. Larger
selection/preflight combinations remain subject to the aggregate cap.

`tests/unit/test_physical_camera_prerequisites.py` covers actual copied source
validators, exact subsets/deferred acceptance, immutable pure restoration,
optional typed provenance, source drift, Stop/deadlines, byte limits, schema and
derived-claim tampering. Its broad fingerprint and optional metadata/preflight
are explicitly injected fixtures; it makes no hardware or M1 qualification claim.
