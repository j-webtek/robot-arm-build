# Windows camera prepared requests

This API prepares the exact native camera request without touching the
filesystem or hardware. It does not authorize an operation or qualify the
received camera. Native activation remains held by the application composition.

## API

`WindowsCameraWorkerClient.prepare_probe(binding, *, source_sha256, campaign_id,
budget)` returns `PreparedCameraCampaign`.

`WindowsCameraWorkerClient.prepare_capture(binding, mode, output_directory, *,
source_sha256, campaign_id, budget, controls=())` returns the same type.

Its frozen fields are:

- `request`: a `CameraActivationRequest` with defensive copies of the exact typed
  endpoint binding, requested mode, immutable controls and campaign budget.
- `arguments`: the canonical argument tuple for the fixed native operation.

Preparation validates scalar bounds, exact nested types, endpoint/hash equality,
native YUY2 constraints and lexical absolute paths without parent traversal.
The helper and output directory may not exist yet. Preparation does not hash or
open files, create/reserve directories, check disk space, enumerate metadata,
invoke a runner, inspect modes, activate a camera or consume authorization.

The existing request and native receipt schemas have not changed. Arguments
include private endpoint/path values and are an internal contract, not browser
input or a UI command runner.

## Coordinator integration

1. Resolve the reviewed endpoint binding on the server. Assign the campaign ID,
   source hash, exact settings, bounded capture budget and fresh absolute output
   path. No camera index or same-name fallback is permitted.
2. Call `prepare_capture` or `prepare_probe`. Review and bind the **complete
   request**, not only `request.arguments_sha256`: that digest covers argv, while
   source, campaign, reviewed-binding provenance and helper digest are separate
   request fields. `windows_camera_capture_ingest.activation_request_sha256`
   provides the existing full capture-request digest.
3. For capture, pass `plan.request` to the existing pure
   `prepare_windows_camera_ingest` before creating its assigned directories.
   Dataset quotas and retention deadlines are separate from native budgets.
4. When an independently qualified coordinator allows execution, use the
   existing `capture`/`probe` API with the reviewed inputs and its mandatory
   authorizer. There is intentionally **no** public `execute(plan)` API.
   Execution reconstructs the request with the same pure builder, rechecks the
   registered helper hash/path and (for capture) the output path, emptiness and
   free-space bound, then calls the authorizer with that exact request.
5. The authorizer must reject stale/mismatched requests and consume exact one-use
   authority. Returning from an arbitrary callback is not qualification. Denial
   produces no runner invocation. Authorization-time request/type/registration
   mutation also blocks invocation; authority is never automatically retried.

After a successful finite capture, pass the validated receipt and the reviewed
request to existing ingestion. Pixels, frame lengths/hashes, clock domains,
cleanup verification and post-dispatch uncertainty behavior are unchanged.

## Limits and tests

Preparation is a plan, not a path reservation, helper installation check,
identity refresh, freshness proof or physical-stage pass. The current native
runner's process/path containment qualification and external physical admission
remain separate work; this change does not make hash preflight race-proof or
provide a cancellation channel. Probe still activates a source and therefore
cannot be called as metadata inventory.

`test_windows_camera_preparation.py` uses blocked filesystem hooks and incapable
Python fixture runners. It covers exact plan-to-authorizer/argv equality,
defensive snapshots, forged and substituted nested inputs, helper/output drift,
denied authority, canonical hashes and the pure ingestion-plan join. No test
executes the native helper, enumerates devices or opens hardware.
