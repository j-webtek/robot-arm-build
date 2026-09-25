# Wizard device metadata selection API

Implemented by
[`wizard_device_selection.py`](../src/rocell/application/wizard_device_selection.py).
This is an **in-memory inventory review**, not connection, persistent device
binding, model verification or commissioning. All `physical_authority`,
`connected`, `qualified` and `persistent_binding` fields remain exactly false.
No method enumerates devices, imports a native provider, opens hardware,
starts a process or writes a file. Random opaque tokens are issued only after
explicit inventory ingest, not during construction or view.

## Call sequence

```python
selection = WizardDeviceSelection(
    mode="rehearsal", session_id=wizard_session_id, source_sha256=workspace_hash
)
staged = selection.staged_copy()
staged.ingest(validated_inventory_report, operation_id=inventory_operation_id)
# Validate and durably retain/log the action result before publishing `staged`.
selection = staged

options = selection.choices("CAMERA")  # No candidate is reviewed by default.
details = selection.preview(operator_choice_id, "CAMERA")
staged = selection.staged_copy()
result = staged.review(operator_choice_id, "CAMERA", reviewer_id)
# Publish the staged state only after the caller's retention/logging succeeds.
selection = staged
```

`SERIAL` follows the same API. The caller owns exact action/source/session
admission, revision checks, cancellation, durable event/result retention and
publication. `staged_copy()` takes the instance lock, creates a fresh lock,
shares only frozen typed values/immutable bytes, and detaches choices,
blocker lists and reviews. It does not publish anything. A discarded staged
copy cannot record a visible acknowledgement in the original instance.

## Input contract

`ingest(report: dict, *, operation_id: str)` accepts the exact complete
`PhysicalDeviceInventoryReport.to_dict()` representation, including its hash.
It bounds and copies the input, reconstructs actual existing candidate,
batch, authority and report types, compares exact canonical bytes and hash,
and requires the aggregate blockers produced by the public pure inventory
composer. Unknown fields, normalization drift, numeric substitutes for false,
wrong platform/source, incomplete collection or tampering are rejected.

Physical mode requires `PYSERIAL_LIST_PORTS`; rehearsal requires
`INJECTED_SERIAL_ENUMERATOR`. Windows cameras require `WINDOWS_PNP`; Linux
cameras require `LINUX_SYSFS`. Rehearsal camera metadata may be an explicitly
synthetic typed fixture with that platform's schema. A report's declared
source/hash is not authentication: the service must admit it only from its
own validated, source-bound inventory action. This module cannot prove that
an external caller actually enumerated the described host.

Limits: 128 KiB complete canonical inventory, 128 candidates per class,
2,048 UTF-8 bytes per source text, eight persistent IDs per candidate, 32
displayed identity blockers, depth eight and 12,000 visited JSON nodes.
Operation/session IDs and reviewer text are bounded to 128 UTF-8 bytes.
Choices have bounded labels; an overlong display name is shortened there
with `...`, while the full bounded name remains in metadata/details.

## Outputs and state

- `choices("CAMERA" | "SERIAL")` returns `[{"value": opaque_id, "label": text}]`.
  IDs identify inventory occurrences, not COM ports, camera indexes or stable
  devices. Duplicate records have distinct choices and explicit ambiguity.
- `preview(choice_id, device_class)` returns schema
  `rocell.wizard_device_candidate_preview.v1`, class, compact `candidate`,
  complete selected `candidate_record`, provenance, report hash, operation ID,
  meaning, four fixed follow-up requirements and the four false flags.
- `review(choice_id, device_class, reviewer_id)` returns the same detail with
  schema `rocell.wizard_device_candidate_review.v1`, a `review` acknowledgement
  and the **complete original `inventory_report`**. Repeated same-candidate/
  reviewer review is idempotent metadata work; it does not redispatch inventory.
- `reviewed_candidate(device_class)` reads that current exact full review result
  or returns None. It never calls `review()`, issues choices or changes reviewer.
  Native endpoint enrollment uses this detached, server-owned evidence anchor.
- `view()` returns `rocell.wizard_device_selection.v1`, status, provenance,
  report hash/operation ID, `devices.CAMERA` and `devices.SERIAL`, each containing
  `candidates` and nullable `review`, the four false flags and nullable
  `invalidation_reason`. The full inventory is deliberately absent from view.
- `invalidate(reason)` clears the report, tokens and reviews. Every new ingest
  also invalidates the previous state first, including a failed replacement.
  Reset tokens cannot be reused. Restart does not restore or connect anything.

Statuses are `NO_INVENTORY`, `METADATA_CANDIDATES_AVAILABLE`,
`METADATA_REVIEW_RECORDED` and `INVALIDATED`. A complete empty inventory has
no choices; the inventory status is not a claim that devices were found.
Initial and invalidated states have null report/operation/platform/time and
empty candidate/review state. Provenance always contains mode, session ID,
workspace source hash and scope `METADATA_SNAPSHOT_ONLY`. Raw capture time is
retained as an integer; a browser must not round it into an exact timestamp
claim. No freshness interval is invented here.

Candidate summaries contain exactly `choice_id`, `display_name`, `vid`, `pid`,
`unit_serial`, `source`, `identity_blockers` and `candidate_sha256`. Summaries
conservatively add missing/duplicate identity blockers without changing the
original inventory. Candidate hashes always name original metadata, not this
derived summary. Missing IDs and shared USB-unit/persistent/OS/locator IDs do
not become a unique binding after review.

Review summaries contain choice/candidate/report/operation bindings,
`reviewer_id`, status `METADATA_ACKNOWLEDGED_FOR_INVESTIGATION`, the four false
flags and these fixed follow-ups:

1. `VERIFY_RECEIVED_MODEL_AND_UNIT`
2. `RESOLVE_UNIQUE_IDENTITY_AND_NATIVE_PREOPEN_RECHECK`
3. `QUALIFY_NATIVE_BACKEND_AND_CONNECTION_CONTRACT`
4. `COMPLETE_CANONICAL_STAGE_AND_PHYSICAL_RELEASE_GATES`

Treat full review metadata as potentially identifying: it includes retained
USB serials and OS instance/path observations. Export it only through the
assigned diagnostic workflow with its provenance intact; it is not a physical
receipt, native pre-open identity check or connection configuration.

## Errors and verification

`DeviceSelectionError(ValueError)` exposes `.code` and a fixed bounded public
message. Codes distinguish invalid input/mode/class, invalid/oversized/
incomplete inventory, mode/source mismatch, stale choice, class mismatch and
opaque-token collision. Original typed errors can remain internal causes;
they are not interpolated into the public message.

[`test_wizard_device_selection.py`](../tests/unit/test_wizard_device_selection.py)
uses synthetic typed metadata only. It covers both modes/platforms, strict
schemas/hash/authority, missing and duplicate identities, 128 choices, stale
tokens, mutation isolation, inert calls and staged-publication isolation.
No test in that suite accesses a physical camera or serial endpoint.
