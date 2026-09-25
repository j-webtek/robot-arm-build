# Contained stage-12 arm-feedback rehearsal

The Guided rehearsal offers two distinct stage-12 actions. The existing
`rehearsal_arm_feedback_campaign` remains the proven memory-only path.
`rehearsal_owned_arm_feedback_campaign` explicitly launches one fixed owned
incapable child and exercises its non-purging serial owner against a sealed
in-memory Win32 model. Neither path opens a physical serial port, observes
physical power, qualifies firmware, or permits motion/contact.

## Operator flow

1. Complete and review the preceding rehearsal stages. Collect stage 12 to
   retain its operator and exact reviewed identity/power dependencies; collection
   does not dispatch either feedback worker.
2. Choose one feedback path. For the contained path, select its closed scenario,
   inspect the action preview, then confirm that exact ticket. There are no port,
   command, executable, raw-byte, budget-override, or filesystem-path fields.
3. Package preparation precedes the short-lived synthetic energy envelope and
   coordinator permit. The owned campaign has a 20-second parent budget, at most
   one fixed feedback transaction, a 2048-byte response-line limit, bounded reads
   and one serial close attempt. The normal overall UI action also includes
   storage admission and retained evidence publication.
4. Inspect the retained process card and feedback assessment separately. Complete
   evidence means required records exist, **not** successful serial communication.
   Child tree exit, native handle cleanup, technical packet validity and the
   independent synthetic final-power observation are separate results. The
   worker's final-power state remains `UNKNOWN_REQUIRES_SEPARATE_OBSERVATION`.
5. Assess and have a distinct rehearsal reviewer review the exact retained
   report. A held or uncertain campaign cannot be cleared by the UI. Stop is a
   cancellation request, not an emergency stop or permission to retry. There is
   no automatic restart or fallback to the memory-only action.
6. Export ordinary diagnostics to the launch-assigned export folder. Public
   results contain bounded process/native counts, hashes and error codes. Raw
   serial/child bytes remain in the original immutable M1 campaign evidence,
   not the browser, terminal, or ordinary diagnostic export.

## Retention and reopening

The contained path has its own `rocell.rehearsal_owned_feedback_receipt.v1`.
Its scenario, exact original-store `owned-arm-feedback` directory, process
summary, evaluation and campaign hash are bound to the audited original result,
reservation, permit and retained evidence. The old receipt schema is unchanged.
Reopening performs pure verification using the original server-assigned store;
it does not rebuild a package, reinterpret a receipt path as authority, convert
an owned permit into a memory-only permit, or repeat a transaction.

An owned preparation directory without its exact retained stage receipt is a
read-only hold, including cancellation or admission failure before dispatch.
Reopening never deletes that directory to make a retry possible. A retained
receipt requires the exact original, empty attempt working directory; unexpected
files, links or missing directories are held for investigation.

The handshake's `release_retained` means release bytes were constructed and
retained, not that they were sent or the child was admitted. The final permission
check can prevent sending them. Inspect written-byte counts and verified child
results independently. Late failures retain only cached, bounded process/native
diagnostics in the public failure and export; these historical diagnostics do not
become a current accepted stage result.

Current browser projections are withheld during queued/running publication and
until completion logging persists, and are hidden on source/log/closed-launch
holds. Historical immutable evidence is retained for investigation. Rendering
and status reads do not start discovery, open devices, load files, or run helpers.

## Developer verification

Focused tests live in `test_wizard_owned_arm_feedback_ui.py` and
`test_wizard_owned_arm_feedback_arrival.py`. Pure display/service doubles are
labeled as such. The UI suite also runs the actual incapable owned child and
passes its real retained summary through both renderers. Separate full M1 tests
are required to establish the durable stage/reopen join; none of these tests is
received-hardware acceptance or physical qualification.

The reproducible public-API smoke is:

```powershell
.venv/Scripts/python.exe software/scripts/wizard_arm_setup_rehearsal_smoke.py --owned-feedback
```

Keep source files unchanged for the entire multi-minute run. It creates a new
rehearsal store, exports at checkpoints, reopens stage 12 before the campaign,
after receipt publication, and at pending review, then verifies the completed
original store with worker replay forbidden. Add `--serve` to stop at an explicit
browser review instead. The default and `--feedback` memory-only behavior remain
unchanged. Do not rerun a failed campaign in its old store.
