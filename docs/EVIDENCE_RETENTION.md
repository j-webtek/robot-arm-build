# Tactevra evidence retention

Tactevra keeps enough evidence in Git to review claims and reproduce portable
checks without treating the source repository as an unlimited experiment-output
store. This policy governs repository placement; it does not judge scientific
quality, promote a model, qualify hardware, or authorize a release.

## What belongs in source history

Commit the smallest reviewable set that supports the change:

- source code, schemas, tests and deterministic fixture generators;
- compact manifests with tool version, source commit, input identities and
  SHA-256 digests;
- compact scorecards containing aggregate metrics, gate results and failures;
- a small representative fixture when a test cannot be understood without it;
- prose that states the population tested, limitations and reproduction command.

Do not routinely commit model checkpoints, raw camera/device exports, private or
licensed datasets, caches, repeated per-sample predictions, or every intermediate
report from a parameter search. Preserve failed outcomes through compact summaries
and hashes; preserving a result does not require committing every generated row.

## Storage classes

| Content | Default location | Required record |
| --- | --- | --- |
| Code, schema, test or generator | Git | Reviewable diff and tests |
| Compact manifest or scorecard | Git | Source commit, inputs, command, outcome and limitations |
| Representative sanitized fixture | Git under `evidence/<issue-or-run>/` | README, provenance, sanitization and license/privacy review |
| Bulk generated report | Local immutable storage until an approved artifact home exists | SHA-256, byte size, producing command and retention owner in the compact manifest |
| Model checkpoint or dataset | External/local by default | Identity, digest, access expectation and applicable terms |
| Credential, private setting or unsanitized export | Never Git or public artifact storage | Handle through the owning private system |

“External” does not mean a personal path is reproducible. A test that requires an
external artifact must detect its absence, identify the expected digest and stop
clearly. It must not download an unpinned replacement or silently skip a claimed
qualification result.

## Ordinary change budget

CI examines generated data changes under `evidence/` and `software/ai/eval/`.
Markdown and source files are not counted as generated data. Without an exception,
one change may include at most:

- 25 changed evidence-data files;
- 20,000 added lines in one evidence-data file;
- 50,000 added evidence-data lines in total; and
- 1 MiB for one resulting evidence-data file.

These are reviewability limits, not target sizes and not scientific thresholds.
Stay well below them. Split code and compact evidence from bulk outputs even when
the bulk output happens to fit.

Run the check against the current commit's first parent:

```powershell
python scripts/ci/check_evidence_scope.py
```

The CI checkout retains two commits so the check can compare the proposed change
with its base. Deletions are allowed because they reduce repository cost.

## Exception procedure

A necessary larger artifact requires an owner-reviewed public issue explaining:

1. why compact metrics, a generator and a digest are insufficient;
2. privacy, credential, third-party license and redistribution review;
3. expected clone/history cost and why another storage channel is unsuitable;
4. exact reproduction or inspection procedure; and
5. retention and later-removal expectations.

After that disposition, add one entry to
`.github/evidence-retention-exceptions.json` with the exact repository path,
SHA-256, issue URL and concise rationale. Exceptions are content-addressed: any
byte change invalidates the entry and requires renewed review. An exception does
not validate the experiment or override release, security or licensing gates.

Do not weaken thresholds, add wildcard exceptions, split one generated result
into many files, or minify data merely to evade review. If bulk artifacts need a
durable hosted home, decide that separately with cost, access, retention and
privacy expectations before uploading them.
