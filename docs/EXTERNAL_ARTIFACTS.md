# External artifact contract

Model checkpoints, datasets, and bulk experiment output are external by default.
Tactevra records their identity in Git without presenting unavailable bytes as a
successful qualification result. This contract supports the
[evidence-retention policy](EVIDENCE_RETENTION.md); it does not promote a model,
grant access to an artifact, or authorize hardware activity.

## Required manifest fields

One compact JSON manifest identifies one external artifact:

| Field | Meaning |
| --- | --- |
| `schema_version` | Contract version; currently `1` |
| `artifact_id` | Stable lowercase identifier |
| `artifact_kind` | `model-checkpoint`, `dataset`, `bulk-evidence`, or `other` |
| `repository_path` | Expected local path below ignored `software/ai/results/` |
| `sha256` and `size_bytes` | Exact identity of the external bytes |
| `storage` | Must be `external` |
| `required_for` | Claims or checks that require the bytes |
| `provenance` | Full producing commit and a credential-free reproduction command |
| `retention` | Responsible owner and ISO review date |
| `limitations` | What the artifact does not establish |

Do not put download credentials, signed URLs, private paths, or secrets in a
manifest. A manifest records identity and access expectations; it is not an
artifact transport.

## Deterministic states

Run the read-only checker from the repository root:

```text
python scripts/ci/check_external_artifact.py path/to/manifest.json
```

It prints one JSON record and returns:

| State | Exit | Meaning |
| --- | ---: | --- |
| `verified` | 0 | Size and SHA-256 match |
| `external_artifact_unavailable` | 2 | Expected external bytes are absent |
| `size_mismatch` or `digest_mismatch` | 1 | Local bytes are not the recorded artifact |
| `invalid_manifest` | 1 | The identity record is malformed or unsafe |

For a clean-clone test that expects external bytes to be absent, add
`--allow-unavailable`. The process then exits zero, but the JSON status remains
`external_artifact_unavailable`; callers must assert that exact status. Never use
that option for artifact-present qualification.

The checker performs no download, copy, write, model load, or controller access.
An artifact-present result needs a separately recorded invocation against the
same manifest. A clean-clone unavailable result and an artifact-present verified
result are different evidence and must not be merged into a single “pass.”

## AI workstream handoff

The pose-keyloss follow-up in issue #56 should provide a focused manifest with
the recorded checkpoint digest and byte size, then bind its portable test to
these states. The AI owner remains responsible for the checkpoint's provenance,
reproduction command, compact scientific scorecard, and artifact-present proof.
Repository maintenance reviews path safety, clean-clone behavior, evidence size,
and source-history placement.
