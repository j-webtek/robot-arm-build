# Lossless stage-12 rehearsal feedback evidence

Module: `rocell.application.rehearsal_arm_feedback_evidence`.
Schema: `rocell.rehearsal_arm_feedback_evidence.v1`.

This pure contract retains an **actual result from the sealed memory-only arm
worker**, not a fabricated exchange or a stage assessment. It performs no file,
device, source-code, clock, worker, subprocess or network operations. The caller
owns admission, execution, durable publication and the exact trusted references.
Physical/native serial activation remains held.

## Callable API

```python
retained = retain_rehearsal_arm_feedback_evidence(
    request,                       # exact ArmFeedbackCampaignRequest
    result,                        # actual ArmFeedbackCampaignResult
    binding_sha256=context_hash,
    source_sha256=workspace_source_hash,
)

verified = verify_rehearsal_arm_feedback_evidence(
    retained_bytes,
    expected_request=exact_request,
    expected_binding_sha256=trusted_context_hash,
    expected_evidence_sha256=trusted_evidence_hash,
    expected_source_sha256=trusted_workspace_source_hash,
)
```

Every verifier argument is required. `source_sha256` means the complete
workspace source binding, **not this module's file hash**, and must equal the
request's source. `binding_sha256` is the caller's full canonical campaign
context digest. The coordinator wrapper can bind its plan, permit, attempt and
request hashes in that context; the plan in turn binds exact stage-9–11 evidence.
This module treats the context as opaque and cannot authenticate hashes derived
from an untrusted incoming document. M1 supplies the independent trusted values.

`RehearsalArmFeedbackEvidence` exposes:

- `canonical_bytes()` and `evidence_sha256`: complete private evidence.
- `to_dict()`: fresh copy of the **private lossless record**, including wire hex.
- `safe_summary()`: fresh bounded raw-free status projection for UI/logs.
- `result`: reconstructed exact `ArmFeedbackCampaignResult`, including its
  complete `SingleT105FeedbackReceipt` when the worker actually created one.

Do not put `to_dict()` or `.result` into ordinary UI logs. Wire replies, boot
prefixes and unknown firmware fields can contain sensitive information. Direct
construction of the immutable wrapper is not verification or trusted admission.
Rejected input raises `RehearsalArmFeedbackEvidenceError`; nothing is repaired,
silently truncated, recollected, normalized into a new identity, or retried.

## Lossless layout and budgets

The exact top-level fields are:

```text
schema, source_sha256, binding_sha256, request_sha256,
controller_binding_sha256, request, result, result_sha256,
wire_accounting, safe_summary, provenance, authority
```

`request` is the existing complete versioned request, including the reviewed
controller binding, single-query context, fixed wire/settings and finite budget.
The existing strict `parse_arm_feedback_request` remains its parser. Origin must
be `SYNTHETIC_REHEARSAL`; physical result/request origins are rejected.

`result` retains **every dataclass field** from `ArmFeedbackCampaignResult`:
outcome/origin/composition, exact request digest, every API counter, primary and
cleanup errors, both ordered settings readbacks, API-reported write count,
open/close timestamps, elapsed time, confirmed close state, response bytes,
unexpected-byte prefix and unretained observed-byte count, and the optional
complete single-T105 receipt.

Each wire field is `{encoding:"hex", bytes_hex, retained_bytes, sha256}` with
canonical lowercase hex. Response plus unexpected prefix is bounded by the
request's line limit plus its single overlength-detection byte, at most **65,537
bytes total**. Omitted unexpected bytes have an explicit observed count; no hash
is invented for bytes that were not retained. The prefix's hash covers exactly
the retained bytes. Accounting never claims to capture future controller output.

The complete successful receipt preserves all ordered transaction times, quiet
buffer counts, request/response/parsed hashes, query/write/retry/motion counts,
provider descriptor and request/controller/session context. To avoid storing
the potentially 64-KiB response twice, its two wire fields are represented by
fixed JSON references:

```text
request -> request.wire_request_hex
response -> result.response_bytes
```

These are two closed JSON locations, not filesystem paths or arbitrary selectors.
The verifier restores the exact byte fields, constructs the real
`SingleT105FeedbackReceipt`, and checks its original receipt hash and complete
round trip. No information is lost by this deduplication.

Failed worker results do not expose every intermediate transaction timestamp.
They retain the available open/close/elapsed fields and no successful receipt;
`transaction_timing_available` is false. The evidence does not invent missing
write/first-byte times or recover an unavailable partial timing trace. Success
requires the actual full ordered timing receipt and the configured quiet window.

The canonical payload limit is **256 KiB**, with no truncation. Use an independent
M1 evidence blob with this explicitly reviewed limit; do not squeeze it into a
smaller generic outer JSON limit. JSON depth is at most 18, containers at most 64
members, integer magnitudes at most signed-63-bit, and numbers finite. Cleanup
issues are limited to eight bounded code/phase/type records. Opens/writes/closes
are at most one, identity checks at most two, reads at most the request's capped
4,096-call limit, and wire byte counts must agree with retained contents.

## Verification and semantic separation

The verifier rejects duplicate/unknown fields, unsupported versions, malformed
hex, hash/length mismatch, Boolean-as-number coercions, changed settings order or
duplicates, inconsistent counter relationships, impossible timing, source/request
or controller substitution, and forged summaries. It reconstructs existing
typed request/timing/receipt values and reuses the wire/typed-feedback validators;
it never reruns `ArmFeedbackWorker` or reads evidence files on its own.

The summary schema is `rocell.rehearsal_arm_feedback_summary.v1`. Important
independent fields are:

- `technical_response_valid`: the retained bytes parse as typed T=1051. It can
  be true even when close failed or unexpected suffix bytes made the exchange
  uncertain. It proves neither firmware revision nor stationarity.
- `feedback_receipt_valid`: the worker actually produced a complete successful
  transaction receipt and the verifier validated it.
- `serial_cleanup_confirmed`: the API close was confirmed without a closing
  error. It is not DC power removal or a stop command. A pre-open rejection does
  not invent a successful close.
- `worker_outcome`: the exact worker outcome enum, with `effect_uncertain`
  separately retained. No successful stage outcome is minted here.
- `final_power_state`: always `UNKNOWN_REQUIRES_SEPARATE_OBSERVATION`.

The remaining summary includes workspace/context/request/controller hashes,
all 12 API counters, fixed error records, response/prefix hashes and byte counts,
and host timing metadata. Raw wire, raw hex, arbitrary port names, decoded
unknown fields and exception messages are excluded. All physical authority and
firmware-proof fields are false. Large nanosecond integers must not be rounded
into apparently exact browser timestamps; retain them in the evidence.

The separately retained synthetic final-power observation belongs to the
coordinator wrapper. It must not overwrite the worker's unknown power field or
be inferred from close. Missing observation remains a seal/assessment blocker.

## Integration responsibilities

After a consumed exact permit, the coordinator wrapper runs the sealed worker
once and passes its actual request/result here. Publish the complete canonical
bytes through the scoped owned transaction **before any known seal**. Bind the
result reference/digest into the coordinator receipt and complete attempt record.
Publication failure, missing worker result or incomplete cleanup preserves the
existing uncertainty/quarantine flow; this contract cannot reconcile it.

At assessment, review, export and original-store reopen, verify the authenticated
M1 blob and its original context/request references, then call the pure verifier.
Do not redispatch the worker or build evidence from a diagnostic summary. Ordinary
exports use `safe_summary`; raw evidence export is separately scoped and must
remain clearly labeled as synthetic/private. Native process containment, child
redemption and non-purging native adapter qualification are separate work.

## Validation commands

```powershell
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_rehearsal_arm_feedback_evidence.py software/tests/unit/test_arm_feedback_worker.py -q
black --check software/src/rocell/application/rehearsal_arm_feedback_evidence.py software/tests/unit/test_rehearsal_arm_feedback_evidence.py
mypy --follow-imports=silent software/src/rocell/application/rehearsal_arm_feedback_evidence.py
```

The tests run real nominal/fault worker lifecycles only against the sealed
in-memory backend. They cover lossless maximum-size response retention,
credential-safe summaries, prefix omissions, complete receipt restoration,
close failure versus packet validity, malformed/extra response bytes, partial
writes, stale identity, pre-open cancellation, counter/timing/settings/hash/schema
tampering and pure verification without worker/file calls. No devices are opened.
