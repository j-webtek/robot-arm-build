# Passive camera intake draft contract

`application/physical_intake_notebook.py` implements the pure notebook model in
the [integration brief](PHYSICAL_INTAKE_NOTEBOOK_IMPLEMENTATION.md). It does not
read/write files, open M1, inspect attachments, enumerate devices, issue epochs,
accept stages, authenticate operators or authorize camera/arm activity.

## API and original requirements

```python
notebook = PhysicalIntakeNotebook.start(
    exact_retained_prerequisites, launch_session_id=current_launch,
)
next_notebook = notebook.record(
    record_id="INT-001",
    observation_status="UNKNOWN",
    observed_value="Hardware has not arrived",
    method="Not measured",
    evidence_note="Not supplied",
    operator_id="setup-operator",
    recorded_at_ns=server_recording_timestamp,
)
```

The application must first obtain CURRENT, original M1-read-back
`PhysicalCameraPrerequisites`. The model takes that exact type and re-derives
the sixteen `camera_receipt` questions, preserving their original labels,
units, requirements, template provenance and acceptance fields. INT-018 belongs
to identity and is not a notebook option. Candidate 610/457/38/86.8 dimensions
never populate observations. Out-of-order draft notes are not stage evidence.

All four narrative fields are required for either status: value/reason at most
256 UTF-8 bytes, method 512, evidence note 1024, operator label 64. Empty text,
surrounding whitespace and Unicode control/format characters are rejected,
not normalized. Use explicit "not measured"/"not supplied" where appropriate.
An operator label is descriptive, not proof of an authenticated human identity.

OBSERVED values in `mm`/`g` use plain decimal text `[0-9]+(\.[0-9]+)?` and must
be positive; INT-005 flatness alone permits zero. Signs, exponent notation,
commas, unit suffixes and nonfinite values are rejected. No conversion to float
or operational limit/accuracy acceptance occurs; numeric text remains bounded
by 256 bytes, not by an invented physical maximum. Other source units/questions
use bounded text. UNKNOWN requires an explicit nonempty reason in the value
field; the software cannot verify whether the human's narrative is accurate.

INT-005 retains `DEFERRED_LIMIT`, owner `noncontact_acceptance`, and prerequisite
`TARGET_ACCURACY_BUDGET_CLOSED`, even after an observed numeric draft is entered.
Evidence notes are descriptions only: attachment bytes are never inspected.

## Immutable snapshot and reconstruction

`.payload` is complete canonical sorted compact ASCII JSON without a newline,
at most 64 KiB. `.sha256` hashes these exact bytes. `.to_dict()` returns a
detached full snapshot; `.view()` adds only `snapshot_sha256`, which is not part
of the hashed document. `.choices()` returns the sixteen original record IDs
and labels. Neither construction nor any getter performs filesystem work.

The schema is `rocell.physical_intake_notebook.v1` with:

- `binding`: source SHA, original session, original launch, current application
  launch, and original prerequisite SHA.
- `revision`: 0–128; `previous_sha256`: null only for revision zero.
- `rows`: the original sixteen question dictionaries. Only `observation` changes
  from null to `{status, observed_value, method, evidence_note, operator_id,
  recorded_at_ns}`. Time must be a positive signed-64-bit integer; UI should not
  display it as an exact JavaScript number.
- `coverage`: total 16 plus separate observed, unknown and unrecorded counts.
- Constant false `physical_authority`, `hardware_qualified`,
  `canonical_stage_pass`, `device_io_performed`, `attachment_bytes_verified`.
- A fixed draft/non-acceptance meaning.

`record()` returns a new object and binds its previous snapshot hash. Revising a
row replaces only that row in the new snapshot; the earlier object remains
unchanged. The service must retain/export earlier action results to retain
history. A snapshot alone does not prove the contents or availability of all
previous revisions. At revision 128, further recording is refused without
truncation, mutation or automatic reset.

`PhysicalIntakeNotebook.from_payload(payload, prerequisites=exact_original,
expected_sha256=independently_retained_hash)` reconstructs purely and verifies
the full schema, original questions/binding, numeric/text rules, coverage and
hash. It does not search for a file or automatically import another launch's
notebook. The service still verifies the current launch/source and ticket
context; hashes detect different bytes but do not authenticate their author.

The ordinary diagnostic sanitizer must still run before publication/export.
The notebook preserves operator text exactly; credential-like text that requires
redaction must hold current publication rather than quietly changing the bytes
named by its snapshot hash. The UI/service owns this publication boundary and
the dedicated `physical-intake-notebook.json` export attachment.

## Tests

`tests/unit/test_physical_intake_notebook.py` covers original question binding,
no populated observations, immutability/revision links, strict numeric and UTF-8
limits, UNKNOWN coverage, deferred flatness acceptance, tamper/hash failures,
pure cached operations, and lossless bounded public/export envelopes. Its
observations are test data only, never received-hardware evidence. Actual
CURRENT prerequisite access, log/source/Stop publication, retained history and
dedicated export persistence are separate service integration tests.
