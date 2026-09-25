# Coordinator-backed feedback rehearsal

This is the stage-12, **hardware-incapable** composition in
`application/arm_feedback_rehearsal_campaign.py`. It invokes the actual
`ArmFeedbackWorker` against the exact sealed `IncapableSerialBackend`. It does
not invoke the standalone diagnostic shortcut, enumerate devices, open a real
COM port, activate a native backend, change power or move the arm.

Read with the [remaining-stage map](WIZARD_REMAINING_STAGE_INTEGRATION.md),
[worker contract](ARM_FEEDBACK_WORKER.md), and
[lossless feedback evidence contract](REHEARSAL_ARM_FEEDBACK_EVIDENCE.md).
The [implementation record](WIZARD_IMPLEMENTATION_PROGRESS.md) tracks the
separately owned shared-service/UI/reopen integration and its acceptance tests.

## Exact plan and prerequisites

The service first verifies the original source/session and reviewed stage-9,
stage-10 and stage-11 receipt/assessment/review/evaluation chains. Its
`RehearsalFeedbackBinding` hashes those complete dependencies and supplies the
synthetic reviewed controller. The campaign's frozen plan contains:

```text
ArmFeedbackRehearsalPlan(
    binding_sha256,
    source_sha256,                       # workspace source, not worker file
    controller: ReviewedControllerBinding,
    power_event_observation_sha256,      # retained stage-11 evaluation
    scenario="nominal",
    final_power_observation: SyntheticFinalPowerObservationSpec | None = None,
)
```

`SyntheticFinalPowerObservationSpec(observer_id, observed_power_state)` is an
explicit **specification**, not an existing observation. State is the closed
`ObservedPowerState` enum: `DEENERGIZED`, `ENERGIZED` or `UNKNOWN`. The default is
no specification, which cannot supply final-power confirmation. A selected
observer must match the independently named envelope observer and differ from
its operator. This input never authorizes or measures physical power.

No COM override, raw command, serial factory, backend switch or physical-enable
argument is accepted. Controller provenance must be `SYNTHETIC_REHEARSAL`.
Firmware/driver/boot-policy fixture hashes are not received-unit measurements.
The supplied source/dependency hashes remain server-owned inputs; this module
does not establish that an arbitrary caller's hashes are authentic.

## Explicit coordinator registration

```python
worker = ArmFeedbackRehearsalCampaign(
    plan,
    worker_executable_sha256=trusted_worker_module_sha256,
)
registration = worker.registration()
coordinator = CellCommissioningCoordinator(
    persistence=qualified_rehearsal_m1_store,
    registrations=(registration,),
    workers={registration.worker_id: worker},
    retained_campaign_actions=(registration.action_id,),
)
permit = coordinator.prepare(exact_source_and_state_bound_request)
result = coordinator.execute(permit, cancellation=operation_cancel_event)
```

Construction, `status()` and `registration()` are inert. The fixed registration
is `rehearsal-arm-feedback`, worker `incapable-arm-feedback-worker`, stage
`feedback_only_connection`, and effect class `SERIAL_OPEN_OR_WRITE`. Its operation
hash covers the full immutable plan. The budget permits one open attempt, one
fixed T105 write attempt, at most 512 reads, no frames, one close attempt, a
10-second coordinator budget and 128 KiB aggregate retained evidence. The inner
worker keeps its own tighter lifecycle/time/line-size limits.

The explicit `retained_campaign_actions` option leaves existing camera/default
worker calls and serialized registrations/permits unchanged. The serial wrapper
rejects `run_campaign`; it only implements the new admitted retained path. It
cannot fall back to a legacy unretained run.

## Ordering and actual one-use authorization

```text
CELL → SESSION → ARM_CONTROLLER owned leases
  → exact source/state/identity/envelope recheck
  → durable INTENT_DURABLE
  → durable one-use EFFECT_ARMED
  → one-use exact consumed-permit acknowledgement
  → actual ArmFeedbackWorker / sealed memory serial lifecycle
  → separate post-worker synthetic final-power observation, if specified
  → complete immutable private evidence publication + durable readback
  → observed/cleanup receipts and exact AttemptResult evidence
  → SEALED_KNOWN only if every required predicate still holds
```

The coordinator passes a scope-bound `authorize_consumed_permit` callback only
after successful durable consumption. That callback permits exactly one call,
checks the same exact permit, deadline/cancellation and M1 owned armed state, and
is disabled immediately when the worker returns. The arm adapter's mandatory
authorizer additionally checks the exact reconstructed campaign request, source,
controller, admission, operation and envelope. A callback's existence alone is
not counted as authorization; the coordinator requires its successful one-use
acknowledgement. No callback or process-local permit survives restart for reuse.

The adapter derives a `SingleT105FeedbackRequest` from the consumed permit and
the reviewed plan. The worker still performs its closed configuration, identity
rechecks, unexpected-byte rejection, at-most-one newline-terminated query, strict
T1051 parsing, no-retry lifecycle and cleanup/error accounting. All those serial
API counts describe **memory simulation**, not actual hardware access.

## Durable full-result retention

The core adds these exact typed return values and transaction methods:

```text
CampaignEvidence(schema, label, payload: bytes)
RetainedCampaignExecution(receipt: WorkerReceipt,
                          evidence: tuple[CampaignEvidence, ...])

transaction.assert_consumed_permit(permit) -> None
transaction.retain_campaign_evidence(permit, evidence) -> None
transaction.read_campaign_permit(attempt_id) -> ExactOperationPermit
transaction.read_campaign_evidence(attempt_id) -> tuple[CampaignEvidence, ...]
```

The aggregate is nonempty, unique, at most four artifacts and at most 128 KiB
raw bytes. It is rejected rather than truncated if oversized. The arm wrapper
currently returns one complete artifact. The separate inner evidence format
allows up to 256 KiB, but this composition's stricter **complete wrapper** bound
applies. Its raw response/unexpected-byte data, full typed receipt, errors and
unretained-byte counts are preserved; no omission is hidden to meet the limit.

The M1 adapter writes a qualified immutable record under its existing private
`rehearsal-records` directory, with fixed basename:

```text
evidence-<attempt_id>-retained.json
kind: CAMPAIGN_EVIDENCE
data: {
  attempt_id,
  permit_sha256,
  evidence: [{schema, label, payload_bytes, payload_sha256, payload_base64}]
}
```

Lossless canonical base64 keeps the maximum record below the existing 256 KiB
strict JSON parser limit. No caller supplies a destination or a filename. The
publisher and directory sync return before a fresh qualified read verifies the
record. The receipt must match the exact ordered full-payload hashes and total
raw byte count. Full evidence is retained before a known seal; a diagnostic
status summary is not a substitute.

For every M1 `SERIAL_OPEN_OR_WRITE` known result, the audit derives the mandatory
evidence requirement from the **immutable permit's effect class**, not the
optional runtime retention flag or a removable extra marker. Missing, partial,
corrupt, substituted or mismatched evidence cannot be treated as optional after
restart. Previously created M1 serial known records without this evidence are
held as unsupported; they are never silently upgraded. Existing in-memory legacy
core fixtures are protocol tests, not qualified M1 serial integration.

Private campaign evidence is audited through the M1 rehearsal adapter's owned
transaction boundary. A bare runtime ledger snapshot is not a replacement for
that adapter's full coordinator-record audit. Reads return retained identity and
bytes, not authority to dispatch a reconstructed permit.

Retention/publication failure, missing evidence, mismatched hashes/byte counts,
missing or repeated authorization, cleanup uncertainty, cancellation, deadline
overrun or unconfirmed final power cannot produce `SEALED_KNOWN`. The core records
uncertainty/quarantine, or preserves an unresolved suffix if even that publication
fails. It does not retry the worker or overwrite a partial result.

## Independent synthetic final-power receipt

The observation is constructed **after** the worker returns. Its state comes only
from the explicit independent fixture specification, never `connection_closed`,
cleanup counts or packet validity. Its private receipt binds:

- source, full dependency binding, exact permit and energization envelope;
- stage-11 evidence and the complete inner feedback evidence hash;
- distinct observer identity, worker-finished and observed monotonic timestamps;
- explicit synthetic provenance and `serial_close_used_to_infer_power=false`.

Absence or `UNKNOWN` remains unknown; `ENERGIZED` also fails required final
disconnection. Successful serial parsing/cleanup alone does not clear that hold.
A serial close failure can coexist with a separate synthetic `DEENERGIZED`
observation, but it still prevents known completion. None of these observations
proves actual power state or replaces an independently observed physical event.

## Pure original-store verification and UI projection

```python
verified = verify_retained_arm_feedback_campaign(
    private_retained_payload,
    expected_plan=plan_derived_from_verified_predecessors,
    expected_permit=audited_original_m1_permit,
    expected_evidence_sha256=trusted_full_payload_sha256,
)
```

The integrating service also compares the original registration against the
trusted worker-module source hash and the exact plan. The verifier performs no
filesystem/device operation and never replays a worker. It reconstructs and
validates the original request, full campaign context, inner typed evidence,
bounded lifecycle times, exact private observation and all source/binding hashes.

`VerifiedArmFeedbackCampaign` exposes immutable `canonical_bytes()`,
`evidence_sha256`, `to_dict()`, `request`, `result`, `safe_summary()` and
`final_power_observation`. The first five are private retention/import data;
do not put the full payload or raw bytes in normal logs or browser responses.

`safe_summary()` is the inner raw-free summary **unchanged**. Its final power is
always `UNKNOWN_REQUIRES_SEPARATE_OBSERVATION`. The separate
`final_power_observation` property is a safe dictionary or `None`, omitting
absolute timestamps and including the synthetic observer/state/provenance/hash
fields. The UI must display technical response, serial cleanup and independent
observation as separate facts. A passing fault test never becomes stage PASS.

The retained context's inner `binding_sha256` is the hash of the full
plan/permit/attempt/request context, not the stage's dependency binding by itself.
The latter is at the verified wrapper's `plan.binding_sha256`. Do not interchange
these digests when deriving the stage evaluation.

## Scenarios and verification

Closed scenarios: nominal, startup bytes, short write, timeout, identity change,
close failure, malformed response, wrong response type and extra response bytes.
There is no raw scenario byte input in the application wrapper.

```powershell
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_arm_feedback_rehearsal_campaign.py software/tests/unit/test_commissioning_coordinator.py -q
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_commissioning_campaign_retention.py -q
```

The first group uses the actual arm worker and sealed memory-only backend, with
exact synthetic coordinator stores, cancellation and virtual time. The second
uses isolated actual Windows NTFS stores and OS leases, with incapable receipt
fixtures, covering full-before-known publication, restart reads, deletion and
corruption rejection, retention failures and maximum lossless record size.
These are software/persistence tests, not received-hardware qualification.

Physical activation, driver/reset-line behavior, native process qualification,
firmware identity, final power observation and stages 13–15 remain independently
held. No physical authority is enabled by this module or its evidence.
