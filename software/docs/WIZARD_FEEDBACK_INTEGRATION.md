# Guided feedback-only rehearsal: stage 12

This increment connects the existing arm feedback worker to the local onboarding
wizard. It is **hardware-incapable rehearsal**, not permission to power or connect
the received RoArm. Native serial/process qualification, installed calibration,
noncontact acceptance and physical handoff remain separate work.

## Operator workflow

1. Launch `start-rocell-wizard.ps1` in its default rehearsal mode.
2. Follow the [workbench](WIZARD_WORKBENCH.md) through the camera, optics, arm
   identity and two power-procedure stages. Export after stage eight and explicitly
   reopen the same store in another launch to stay within the operation budget.
3. At **Feedback-only connection**, collect/open the due stage. This saves its
   operator and verifies the exact reviewed predecessor chain; it does not open
   even a simulated serial connection.
4. Preview and execute **Run coordinated memory-only arm feedback**. The service
   chooses the closed nominal fixture. No browser field selects a COM port,
   controller, protocol command, firmware claim, power state or arbitrary script.
5. Inspect the separate packet, complete-transaction, serial-cleanup and synthetic
   post-campaign power results. The serial worker's own power result stays UNKNOWN.
6. Assess retained evidence, then explicitly review the exact assessment with a
   different rehearsal reviewer ID. These local IDs model roles; they are not
   authenticated people or proof of physical observation.
7. Export diagnostics to the assigned workspace directory. Closing and reopening
   the original store restores its verified report without replaying serial work.
   A pending review requires fresh explicit acceptance.

The next stage, reference-frame calibration, remains held in this service slice.
All fifteen physical stages remain pending, including after twelve rehearsal PASS
states. A software Stop is not an E-stop or evidence of power disconnection.

## How the code connects

| Layer | Responsibility |
| --- | --- |
| `wizard_actions.py`, `arrival_wizard_service.py` | Closed action, explicit preview and one-use ticket; no raw command inputs |
| `commissioning_rehearsal_service.py` | Due-stage/operator check, exact predecessor verification, controller-specific facts, fresh envelope and coordinator dispatch |
| `rehearsal_feedback_binding.py` | Full stage-9–11 receipt/assessment/review/evaluation hashes, source/catalog/cell/session/operator and exact memory-controller identity |
| `rehearsal_feedback_stage.py` | Server-owned nominal plan and small raw-free derived report |
| `arm_feedback_rehearsal_campaign.py` | Actual worker adapter, one-use consumed authorization, complete artifact and independent post-worker synthetic observer |
| `rehearsal_arm_feedback_evidence.py` | Bounded lossless request/result/wire/timing contract and pure verification |
| `cell_commissioning_coordinator.py` | Exclusive operation lifecycle, bounded execution, explicit complete-evidence retention path and uncertainty handling |
| `commissioning_m1_persistence.py` | Real original-store leases, qualified immutable private evidence, known-result audit and missing/corrupt-record holds |
| `commissioning_rehearsal_reopen.py` | Exact original-store result/permit/blob verification, dependency reconstruction and report comparison; no replay |
| Browser and terminal | Same cached projection, seven separate checks, safe summaries, synthetic observer and explicit physical holds |

Read the [worker/coordinator contract](ARM_FEEDBACK_REHEARSAL_CAMPAIGN.md),
[lossless evidence API](REHEARSAL_ARM_FEEDBACK_EVIDENCE.md) and
[UI presentation contract](WIZARD_FEEDBACK_PRESENTATION.md) for their detailed
schemas, budgets, test lanes and ownership boundaries.

## Identity and power binding

The transport controller is derived from the independently verified stage-nine
selection baseline, not the camera identity or a submitted port name. Its closed
fixture uses COM42, USB `1234:5678`, unit `INCAPABLE-ARM-001`. These are intentionally
fictional values, never a received-hardware allowlist. Driver and installed
firmware/boot observations remain explicitly unmeasured synthetic placeholders.

All three predecessor trios must have one exact committed PASS review and a
passing substantive report. Hashes cover full canonical payloads, not only an
embedded assessment self-hash. Upstream camera/registration dependencies are
verified again. A changed predecessor/source/controller invalidates the campaign.

Only an explicit campaign creates controller admission facts and a fresh,
30-second synthetic energy envelope. The eight configuration-epoch documents
also bind the selected feedback context. The envelope covers the exact operation
and independently named procedural observer. It is discarded after the attempt;
status, refreshing and reopening cannot recreate it.

The envelope is issued after read-only storage preflight, not before it. The
coordinator checks coverage again immediately before dispatch, after durable
intent and permit consumption: the entire bounded feedback campaign must fit
inside both the permit and envelope. Slow durable writes cannot silently extend
authority. Camera campaigns have no power envelope; their independent capture
budget is distinct from the deadline to begin dispatch.

The observer input is a **fixture specification**, not a preexisting claim of
de-energization. The separate observation is produced only after the worker
returns, and binds the exact permit and retained inner evidence. Serial close
is never used to infer power-off. Missing, energized or unknown final observation
preserves coordinator uncertainty/quarantine even when the packet was valid.

## Retention, assessment and logs

The coordinator's explicit retained path validates consumed authorization exactly
once. It checks evidence cardinality, complete byte accounting and hashes, then
stores the full bounded artifact before known sealing. M1 requires complete
retained evidence for every known `SERIAL_OPEN_OR_WRITE` attempt. A missing blob
cannot silently turn into a legacy non-retained success on restart.

The private record is `CAMPAIGN_EVIDENCE` in the original M1 coordinator records.
It retains lossless canonical bytes in strict base64 envelopes, within a 128 KiB
aggregate raw-campaign cap. Oversize or unavailable evidence is rejected, not
silently truncated. The inner evidence contract separately records any bytes the
worker could not retain; it never invents their content or digest.

The stage receipt contains only the derived safe report, exact attempt result and
retained-blob hash. Its report is regenerated from the audited reservation/result/
evidence records and exact predecessor binding at assessment, review and reopen.
A valid packet prefix alone is insufficient: complete transaction receipt, worker
success, cleanup, separate synthetic power and known retention must all agree.

Normal UI status and exports intentionally exclude private serial bytes. They
include bounded counts, safe lifecycle errors, evidence hashes and the separate
observer summary. The full raw record remains in the original M1 store; normal
diagnostic export is not a full commissioning archive or authority transfer.
The assigned export root is:

`C:\Users\Jack\Desktop\robot-arm-build\software\runs\wizard-exports`

## Failure and restart behavior

- Stop before admission dispatches nothing. Stop after possible effects cannot
  justify an automatic retry or a newly manufactured known result.
- Boot/stale bytes prohibit the feedback write. A short write is not followed
  by a remainder, retry or another command.
- Malformed, wrong-type, extra, missing or late feedback is not nominal success.
- Close failure, missing evidence, uncertain observation and process loss retain
  uncertainty. Fault tests use independent rehearsal cells, not retries in a
  quarantined cell.
- Opening stage 12 without an attempted campaign may be explicitly reopened and
  continued. A prior reserved attempt without its stage receipt is held; no
  campaign is replayed to fill the gap.
- A reopened completed or review-pending stage is pure reconstruction. No arm
  worker, camera campaign, identity fixture or observer is rerun.
- A public-report/export failure is not proof that the underlying campaign did
  not happen. Inspect the original attempt and retained evidence; never repeat a
  completed exchange just to regenerate a report.

## Verification and remaining work

Unit lanes use the actual worker with its exact memory-only backend. Separate
Windows tests exercise real NTFS qualification, leases, publication/readback and
missing/corrupted private records. The full twelve-stage original-store test and
public browser smoke are recorded, with exact outcomes, in the
[implementation record](WIZARD_IMPLEMENTATION_PROGRESS.md). Never count a passing
fixture as received-arm, firmware, driver, force, reach or accuracy qualification.

For a new public-action rehearsal and explicit browser review:

```powershell
.venv\Scripts\python.exe software\scripts\wizard_arm_setup_rehearsal_smoke.py --feedback --serve
```

This smoke also restarts from the stage opening and from the complete feedback
receipt before assessment. After the explicit browser review, independently
verify the exact printed session ID without running any campaign or upstream
evaluator again:

```powershell
.venv\Scripts\python.exe software\scripts\wizard_arm_setup_rehearsal_smoke.py --verify-completed 'rehearsal-EXACT_SESSION_ID'
```

The latter developer-only check installs fail-fast in-process guards against
worker/evaluator replay, reopens the explicitly selected original store, asserts
twelve rehearsal PASS states and all fifteen physical holds, then exports a new
verified diagnostic report. It cannot migrate a session from a different source.

Keep source files fixed for the multi-minute run. Do not alter old session source
headers to reuse earlier evidence. Existing native worker/process and non-purging
serial precursors remain independently held; this increment does not substitute
them for the closed memory backend or introduce physical command execution.
