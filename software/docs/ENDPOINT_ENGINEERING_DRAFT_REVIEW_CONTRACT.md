# Endpoint engineering draft review contract

Status: codec, authenticated binding verification and native packaging implemented;
engineering-decision and final operator-confirmation forms connected; production
launch evidence assembly and live qualification still incomplete. No live motion
is enabled by creating a draft review.

## Why this exists

A live request has a maximum 30-second lifetime; native preparation requires
27 seconds remaining. Human engineering inspection must happen before that
window. Increasing the deadline or relabeling an old inspection as a current
observation is not the solution implemented here.

## Two distinct records

1. `rocell.engineering_draft_review.v1` retains the engineer's actual decision,
   actor, rationale, original monotonic timestamp, original expiry and exact
   draft hash. Its maximum lifetime is five minutes. APPROVED, DENIED and UNKNOWN
   are representable; only a still-valid explicit approval can be bound.
2. `rocell.bench_endpoint_review.v2` records a later **binding event**, not a new
   inspection. It contains the original draft review bytes in base64, the exact
   request hash and the binding timestamp. Its expiry is no later than either
   the original review expiry or the request deadline.

The original timestamp is never rewritten. A changed target, speed, campaign,
selected trial, USB identity or any reference changes the draft and rejects the
binding. Only the request's attempt ID and execution timestamps are omitted
from draft material, as defined by the existing `EndpointTrialDraft` codec.

## Scope and trust

Only the five existing engineering checks support this binding. All seven
operator checks still require current exact-request v1 records. In particular,
an engineering draft cannot stand in for operator presence, clearance, shutdown
access or the final exact-target/speed decision.

The trusted host must obtain actual decisions and retain their provenance.
An actor string, valid JSON or a digest does not authenticate a reviewer.
There is no browser signing endpoint. The existing host HMAC authority seals
the full set of originals; it now also verifies the nested draft material,
actor/check association, approval and expiry for v2 engineering bindings.
Sealing authenticates host records, not the truth of physical observations.

Current identity/source/reference validation, fresh native baseline checks,
exclusive connection ownership, immutable attempt reservation, one-use command
permission and run/cleanup deadlines remain required and unchanged. No home,
reset, retry, torque change or transport open is performed by this codec.

## Host integration still required

1. Present the immutable draft and actual supporting originals to the engineer.
2. Retain explicit decisions with their original times; do not prefill approval.
3. Collect the final operator decision through authenticated host input.
4. Compile the unchanged draft into the new exact short-lived request.
5. Bind still-valid engineering originals with `EngineeringDraftReview.bind_request`;
   record current operator decisions through `EndpointReviewIntake`.
6. Feed both original sets through existing issuance, current-context validation
   and supervised execution. An expired/changed/denied review stops the launch.

The exact atomic association between final operator input and the compiled
request must be implemented and tested; this document does not authorize copying
historical operator answers into fresh request records. The default wizard has
not yet been given a production endpoint binding.

## Verification

44 focused authority/issuance/draft tests passed. The combined endpoint/campaign
suite passed **309 tests** in 56.67 seconds, process exit 0. Result:
`software/runs/endpoint-engineering-integrated-20260913-01.xml`.
Tests include original-byte/time retention, changed references, expiry extension,
wrong actors/originals, denials and attempts to replace operator checks. Native
package dependencies explicitly include the draft and engineering-review codecs.
All decision fixtures are synthetic. No device was opened or moved in this work.

## Concrete coordinator adapter

`EngineeringDraftReviewReader` now supplies the existing `engineering_reader`
dependency accepted by `EndpointWizardBinding` / `run_endpoint_draft`. Construct
it from an immutable tuple of the five actual canonical review originals. It
rejects missing/duplicate checks and mixed drafts. The coordinator supplies its
new exact request; the reader validates and binds all five originals using one
host clock reading. Invocation is consumed even on failure and protected by a
lock, so duplicate/concurrent calls cannot refresh or issue a second binding.

This adapter does not collect decisions or authenticate their source. The host
must still obtain actual engineering originals and current operator input.
Do not populate it with test fixtures or interpret the adapter as a motion permit.

Verification: 37 tests passed for the adapter, draft codec and real coordinator
issuance flow; a subsequent 29-test adapter/native-package/child regression
passed, including concurrent invocation. Both processes exited 0. Results:
`software/runs/endpoint-engineering-reader-20260913-01.xml` and
`software/runs/endpoint-engineering-native-20260913-01.xml`.
The integration test uses synthetic originals and a non-native terminal runner;
it verifies authenticated bundle contents and exact request linkage, not hardware
movement. Native-child tests remain simulated device interactions.

## Wizard decision intake

The physical-mode action `record_endpoint_engineering_review` is now available
through the normal generated wizard form and parent action/ticket workflow.
Inputs are exact draft JSON, reviewer identity (explicitly self-reported), one
of the five engineering checks, explicit decision and evidence/rationale.
Decision defaults to UNKNOWN. It never converts recording success into approval.

Execution validates the draft against the current wizard source and publishes
immutable operation-scoped draft and review originals in the session log.
Only execution supplies the real host timestamp and five-minute expiry; preview
does not record a decision. Refusals remain retained. Standard diagnostic export
includes the draft, decision, hashes and non-authority status. There is no device
open, inventory, key operation or automatic endpoint binding in this action.

This solves collection, not independent verification of reviewer identity or
their evidence. Host assembly must select and verify actual originals before
passing them to `EngineeringDraftReviewReader`. Final current operator checks
and the exact-input/request association remain necessary before live launch.

Verification: **329 combined endpoint/campaign tests passed** in 56.42 seconds,
exit 0; `software/runs/endpoint-intake-integrated-20260913-01.xml`. Public service
tests exercise prepare/execute, UNKNOWN/DENIED/APPROVED retention, verified export,
invalid input, mismatched-source refusal and no automatic endpoint binding. The
form uses the existing generic action renderer; no rendered-browser visual QA
was performed in this checkpoint. No physical hardware was accessed.

## Loading selected originals for host assembly

`load_engineering_review_reader` connects retained wizard records to the concrete
coordinator reader. The trusted host supplies its session-log root, exact draft,
five explicit `(operation ID, review SHA-256)` receipts from retained results,
current source hash and a current-context/cancellation callback. No filesystem
path is selected by browser input and no search for the latest approval occurs.

The loader reads bounded regular files through the existing substitution-aware
file helpers. Each retained draft must match byte-for-byte, each review must
match its receipt hash, and every decision must be an unexpired approval of the
same draft. The reader verifies five unique checks and rechecks expiry/material
at actual request binding. Reading creates no files and refreshes no timestamps.
Hashes prove integrity against the selected receipts, not reviewer identity.

Verification: **31 selection/public-intake/coordinator-reader tests passed**,
exit 0; `software/runs/endpoint-engineering-selection-20260913-01.xml`. Includes
selection integrity, duplicate/path inputs, source mismatch, missing checks,
expiry, current-context refusal, UNKNOWN/DENIED and expiry after selection.
The records used by tests are explicitly synthetic. This loader is a trusted
host dependency, not an automatically installed live binding. Final operator
input/request association and production evidence assembly remain unfinished.

## Final operator host transaction

The host transaction is implemented in `endpoint_operator_confirmation.py`;
connecting it to accepted wizard-button input remains required. No additional
operator approval format or relaxed native timestamp rule was introduced.

The authenticated final-click handler must call `record_final_confirmation`
with the displayed draft, expected hash, newly assigned attempt, actual actor,
all seven explicit true operator answers and the original action deadline.
It creates the exact short-lived request **first**, then publishes that request
and the seven existing v1 operator records against its hash. Current-context
checks surround publication. Missing/false/non-boolean answers, changed drafts
and invalid actors fail before request publication. Partial publication remains
retained and cannot be retried under the same attempt.

The coordinator now accepts this typed `prepared_request`. It verifies exact
draft material, attempt, validity and parent deadline and uses the same bytes;
it never rematerializes a confirmation with a new timestamp. The original
30-second maximum and 27-second preparation reserve still apply. Delayed queues
therefore fail rather than refreshing operator presence.

Call this transaction at authenticated acceptance, not later in a queued worker.
Do not populate answers from historical setup, inferred clearance or test
fixtures. The factory records input; it does not independently authenticate a
person, observe the arm, issue a signed bundle or grant a movement permit.

Verification: 23 focused confirmation/coordinator tests passed; **350 combined
endpoint/campaign tests passed**, exit 0, in 64.57 seconds. Durable result:
`software/runs/endpoint-confirmation-integrated-20260913-01.xml`. Tests verify
retained operator/request association, duplicate refusal, missing/false/numeric
answers, changed draft/attempt/deadline, cancellation and delayed dispatch.
All operator answers are synthetic fixtures; no actual user confirmation was
created by the tests and no physical device was opened.

## Final button connected to host transaction

`run_endpoint_trial` now requires operator identity and seven explicit unchecked-
by-default confirmations in addition to the exact draft hash/acknowledgement.
The normal action validator refuses any missing, false or non-boolean required
answer. No historical setup record is copied into these answers.

During `execute_action`, under the existing action lock and before queueing,
the service consumes the endpoint attachment, logs acceptance, compiles the
request and records the operator originals. It retains the exact request and
all seven review records in diagnostic events. Logging/publication failure
finishes the attempt without dispatch; the same attachment cannot be retried.
Duplicate execute calls return the existing receipt without a second transaction.

The worker receives that unchanged request and its recorded operator reader,
not the externally supplied binding's operator callback. It rechecks the exact
confirmation/attempt/binding/current setup association before delegation to the
existing coordinator. Queue delay does not renew the deadline. Existing
engineering reader, reference validation, native baseline and one-use permit
are still required; a default wizard with no host binding remains unable to run.

Verification: **479 tests passed**, process exit 0, in 73.91 seconds across
endpoint/campaign, action catalog, wizard service and CLI regressions. Result:
`software/runs/endpoint-button-integrated-20260913-01.xml`. Earlier focused runs
exposed and fixed first-action lazy log-directory initialization before final
confirmation publication. Queue deferral, duplicate clicks, seven individually
required checks, publication refusal and diagnostic export are explicitly tested.
This is programmatic public-action verification with synthetic operator input
and incapable native-launch substitutes; no visual browser QA or hardware trial
was performed. Next: assemble the actual host binding from verified hardware
and review originals, then perform fresh physical checks and one slow live trial.

## Host attachment assembly

`assemble_endpoint_binding` now composes the exact draft, eight retained
reference originals, five explicitly selected engineering review receipts and
the existing `EndpointCurrentContextReader` into `EndpointWizardBinding`.
Assembly checks bounded structured originals and hashes, current workspace
source/build snapshot and review selection. It performs no native enumeration,
file publication, signing, binding installation or port open.

When the actual request arrives, the context factory checks unchanged draft
material, decodes its retained controller original against that request and
reuses native identity/reference validation. Source/build/reference reconstruction
runs again against the coordinator-staged originals; prior assembly is not a
cached readiness claim. The placeholder operator reader explicitly refuses:
the public wizard must supply its recorded final-confirmation reader.

The host must supply `metadata_factory(request)` returning a process-supervised,
bounded metadata reader. There is **no unsupervised Windows-call fallback** in
the UI process. A callable alone does not prove supervision; production host
wiring must provide and verify that property. Missing factory input is rejected.
This requirement was confirmed from the existing Windows acquirer's documented
need for process containment; its cooperative deadline alone is insufficient.

Verification: **39 assembly/context/selection/public-button tests passed**, exit
0, result `software/runs/endpoint-binding-assembly-20260913-02.xml`. Synthetic
metadata is acquired only upon explicit context invocation, not assembly.
Tests cover missing/changed originals, source/build/context failures, absent
metadata provider and later reference mutation. Production metadata-provider
wiring and actual evidence selection remain incomplete; no hardware was opened.

## Service-level host installation

`ArrivalWizardService.configure_endpoint_trial` now installs the assembled
attachment using the built-in `SupervisedEndpointMetadataFactory`, service-owned
cancellation, current-state checks and diagnostic retention. It is a trusted
Python host method, not a new browser route or an approval-signing API.

The caller provides a typed draft, original reference bytes and five review
operation IDs. Hashes are reconstructed from this service's completed review
operations, not supplied by the caller. Each selected operation must record an
approval of that draft; the existing loader verifies the underlying originals.
Idle physical mode and an unbound, unattempted attachment are required. A
successful call returns HOST_BOUND_NOT_AUTHORIZED. Fresh powered setup and all
final operator/engineering/native admission checks still gate Run.

Age-sensitive post-snapshot guards check in-memory operation/attachment/source-
error/log state. They do not repeat disk source hashing inside the 100 ms window:
the existing reference reader performs source/build validation before metadata,
and native package/claim verification remains unchanged. Closed, replaced or
no-longer-owned operation contexts are rejected. Metadata results use the
existing diagnostic log; logging failure invalidates the operation.

32 service/assembly/button tests passed, exit 0; result
`software/runs/endpoint-service-binding-20260913-02.xml`. Coverage includes a real
assembler supplied by public wizard review records and actual current source
hashes, but with explicitly synthetic reference meanings and controller data.
No metadata enumeration or native launch was performed by these tests. Rejected
selections, busy/attempted/replaced state, no affirmative recording defaults and
remaining Run holds are tested. Actual unit evidence selection and first slow
live qualification remain unfinished; wiring alone is not hardware approval.
