# Compatibility and release-content review

Reviewed September 26, 2026 at merged commit
`3660fc4d956d8503e2ae91a0cef624449058f926`.

**Outcome: tested offline interfaces are compatible; release publication remains
pending content/provenance review and both workstream owners' sign-off.** This is
a technical evidence review, not legal clearance or a substitute for owner review.
Unmerged AI work is outside this baseline.

## AI/arm compatibility

| Boundary | Evidence reviewed | Finding and limit |
| --- | --- | --- |
| AI batch to arm consumer | `test_model_motion_v2_shared_gate.py`, `test_batch_emitter_v2.py` | Actual assembler bytes pass the consumer and schema checks with synthetic observations; repeated H/H/I actions retain order. Not a real-camera demonstration. |
| Raw request to shadow path | `test_shared_shadow_runner_v2.py` | Shared offline path retains blockers and zero authority. Missing measured calibration is not bypassed. |
| Planned envelope to command bytes | `test_zero_write_waveshare_adapter_v1.py`, `test_zero_write_waveshare_contract_v1.py` | Synthetic envelopes produce checked T=102 fixture bytes and schema-valid records; no transport is opened. |
| Execution lifecycle | `test_zero_write_sole_writer_v1.py` | Ownership, reservations and fault/restart rules are exercised as modeled events, not physical writes. |
| Controller evidence | `test_installed_controller_qualification_v1.py` | Missing or mismatched evidence blocks. Modeled passing evidence permits only zero-write profile binding, not execution. |

The schema contract separates jobs: AI proposes named coordinates in
`board_mm_xy_plane_v2`, not servo angles or wire commands. The arm owns movement
policy, planning, encoding, and eventual dispatch admission. V2 removes
model-owned speed and clearance choices. See the
[schema index](../../software/ai/schemas/README.md).

Validation used the fresh baseline Python 3.10 environment documented in
[the earlier checkout record](BASELINE_2026-09-26.md), against this revision's
source and explicit `TESTS` list from `scripts/ci/offline_checks.py`:
**171 passed in 16.28 seconds**. This was an existing-environment source test,
not a new clean-install qualification of this revision. No training, inference,
camera, controller connection, firmware operation or physical movement occurred.
No incompatibility was observed in this tested selection; arbitrary model output
and future workstream branches are not covered.

## Tracked-content inventory

Counts from `git ls-files` at the pinned revision:

| Artifact extension | Count |
| --- | ---: |
| ZIP | 1 |
| 3MF | 97 |
| STL | 246 |
| STEP | 113 |
| BIN, PT, PTH, ONNX, GGUF, SAFETENSORS | 0 each |

These are filename-extension counts, not a complete binary detector or proof that
all model/firmware content is absent. The tracked ZIP is
`hardware/static_overhead_camera/cad/output/revisions/SYSTEM_PRINT_PACK_v1.zip`.
Its directory lists 87 members, with no member name containing `license`,
`notice`, or `readme`. Member contents, embedded 3MF metadata, and ownership were
not exhaustively inspected. Do not infer missing rights merely from filenames.

The root Apache-2.0 [LICENSE](../../LICENSE) is present. A filename search found no
separate tracked LICENSE/NOTICE files. The public README already limits its
license statement to original contributions and preserves third-party terms.
That statement alone does not establish provenance for each asset.

The [AI overview](../../software/ai/README.md) explicitly records unverified
weight origin/license for an earlier locally installed Llama 3.1 candidate.
No tracked checkpoint with the listed weight extensions was found. Do not bundle
local models, adapters, or their caches without a separate provenance review.

## Decisions needed before publication

1. **Project/hardware owner:** confirm authorship or upstream sources and
   redistribution terms for CAD/print packages, including the ZIP. Supply
   attribution records where required. Preserve frozen archives; use a companion
   provenance record or a separately reviewed release artifact rather than
   silently rewriting historical bytes.
2. **AI owner:** sign off the exact candidate's producer contract and identify
   any code/data/model materials needing additional notices. This review does
   not approve redistributing locally installed weights.
3. **Arm owner:** sign off the exact candidate's consumer/encoder contracts and
   identify vendor-derived material or notice requirements. Tests are not proof
   of the installed firmware's behavior or its redistribution terms.
4. **Release maintainer:** choose full-repository source archives only after the
   content review, or prepare a separately inventoried software subset. GitHub's
   generated source archives include tracked historical CAD/print assets; merely
   omitting uploaded binaries does not exclude them. Do not delete source assets
   or rewrite history as part of this review.

Record reviewer identity, reviewed SHA, disposition, and evidence in the release
PR. No tag, release asset, NOTICE attribution, or license exception was invented
by this review. Publication remains subject to the [release checklist](../RELEASING.md).
