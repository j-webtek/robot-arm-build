# Camera attempt failure diagnostics

## Scope — 2026-09-12 UTC

Continue the pre-build wizard work without received-device IO. The metadata-only
successor identifies the B0477; persistent-unit identity, negotiated speed and
capture commissioning remain separate. This increment makes failed camera
startup attempts understandable in the wizard, using already retained evidence.

The preserved full-history run 03 is terminal, not still running: the public
probe returned `CAMERA_ATTEMPT_NOT_KNOWN`. Its retained attempt is
`SEALED_UNCERTAIN`, with `NATIVE_ACCOUNTING_UNAVAILABLE`. The original supervision
reports `ADMISSION_DEADLINE_EXPIRED` and `release_check_passed=false`. This is a
modeled-process software failure, not a received-camera observation. Constructed
release bytes do not prove delivery; unavailable accounting does not mean zero
hardware effects. The original store and JUnit must remain unchanged.

## Implementation plan

1. Preserve the stable dispatch error code and every existing hold. After a
   successful original readback and lease exit, attach a small diagnostic summary
   to the uncertain-attempt error: exact attempt/state, retained supervision
   error, release-check observation and accounting availability. No raw pipes,
   endpoint paths, guessed counters or automatic retry instructions.
2. Add a clear error message for an observed admission deadline, with a bounded
   generic fallback for other/absent causes. Original-readback failures must
   remain their own errors; no worker-memory data may replace missing originals.
3. Carry this summary through the public wizard failure result and both ordinary
   and exact-attempt exports. Reuse the existing error/details UI instead of a
   second state machine. The complete original remains in the dedicated export.
4. Reproduce deadline and other failures with incapable process peers. Test
   original validation and lease-exit failures, unchanged no-replay/quarantine,
   success behavior, one-use tickets and public log/export retention. Never
   launch the camera/USB/serial workers or change production deadlines/clocks.
5. Update the full-history record and developer playbook with measured outcomes.
   Keep the admission-performance defect explicitly open: clearer diagnostics
   are not a timing fix or a passing full-history capture test.

## Completion criteria

The public failure shows the retained startup cause while remaining FAILED,
disconnected and non-replayable; a verified export preserves that summary and
the full uncertain attempt. Missing native accounting remains unknown. No
physical camera action, control write, USB descriptor query or arm operation.

## Implemented contract

`PhysicalCameraDispatchError` keeps its existing `.code` and adds an optional,
detached `.diagnostic`. The new summary schema is
`rocell.camera_attempt_failure_summary.v1`. It is constructed only after the
sealed original permit/result/native evidence are checked and the readback
transaction exits. It carries the exact attempt/state, operation, readback scope,
bounded reported primary error, nullable release-check observation, receipt
availability and quarantine state. Authority, qualification and automatic replay
remain false. No native wire buffers, paths or effect counts enter this summary.

An observed `ADMISSION_DEADLINE_EXPIRED` now appears in the main error message,
not only deep in the native supervision export. Other safe reported error labels
are retained, including mixed-case exception-class labels. Missing primary causes
remain unavailable. A release check is not a release-delivery observation.
No summary is attached when original validation or lease exit itself fails.

Arrival includes the summary as `camera_attempt_failure` in the failed action's
retained result. Its existing operation renderer displays the error and export
remediation without another action. Normal diagnostic export retains the small
result; probe/settings exact-attempt exports retain both that completion and the
complete native/admission evidence. No second acquisition or status state machine
was introduced. Full-history timing remains a separate failed acceptance result.

## Verification scope and retained development failures

Deadline tests slow only the incapable transport before its release callback:
the actual fixed 2-second probe and 5-second capture admission limits expire
against the real monotonic clock. No production clock, budget, permit, result or
native validation is replaced for this fault. Parent/core/store/Arrival behavior
and exact export reconstruction are exercised, while predecessor semantic facts
and process owners are explicitly modeled. This is not received-hardware proof.

- Initial run 01 retained two development failures: the new display filter was
  too restrictive for `JSONDecodeError`, and the test-only delay bound omitted
  the existing 5-second capture allowance. Both were corrected; no production
  admission limit changed.
- Runs 02/04 found that the scoped public fixture's manually modeled metadata
  operations omitted `result_retention`. The fixture now explicitly labels those
  missing predecessor results `OMITTED_MODELED_METADATA_RESULT`. The exporter
  and production completeness checks were not relaxed. Run 06 verified both
  failed-probe export paths: **2 passed**, 10 deselected, 28.25 s.
- Run 03: **43 passed**, 84.98 s, covering M1 handoff, original-probe service,
  export codec, shipped renderer/polling and metadata-successor compatibility.
- Run 05: **2 passed**, 11 deselected, 110.67 s. Public settings capture preserves
  nominal repeated-request/probe history and handles the injected admission
  deadline with no preview, a retained uncertain attempt and verified export.
  JUnit `.codex-preserved/camera-failure-details-20260912-05.xml`, SHA-256
  `b142f2223c72aaf65ba53a9993c634c2d61baabdf58374c8615f03e1e9ed0503`.

The selected runs overlap; do not add all historical counts as unique coverage.
Every run uses a new `software/runs/pytest-camera-failure-details-20260912-*`
directory and `.codex-preserved/camera-failure-details-20260912-*.xml` report.
Earlier stores, partial outcomes and exports remain retained unchanged.

Six edited Python files pass Black checks; the shipped JavaScript passes Node
syntax checking. Targeted mypy passes for the dispatch module. A separate Arrival
check reports two Optional-action-ID typing errors at `_recheck_source` calls in
the existing observation-publication method, outside the new failure handler;
they were not suppressed and this is not a clean whole-application typing claim.

Both launcher `-Check` modes report `READY_FOR_DIAGNOSTICS`, revision 0, no
operations and disconnected camera/arm. The physical check confirms zero events
and the selected `software/runs/wizard-exports` destination. Check mode did not
start a web server, connect devices or create a commissioning pass.

## Final checkpoint

The combined run 07 is terminal: **102 passed, no failures/errors/skips**,
209.23 s. JUnit `.codex-preserved/camera-failure-details-20260912-07.xml`, SHA-256
`b162a2009891bd8c93cc3033f7c39e90fd36bdffd1310d7c807aa0f576b5c7a1`.
Together with the two distinct settings-capture cases in run 05, this gives
**104 selected passing test cases**, not a whole-repository acceptance claim.

The final application source fingerprint is
`ca3114a5b49859f88344382d4d6339114022f3f7e381f38da4e89f6b03700c13`.
The metadata-only successor binary/build record retain their earlier hashes;
source-bound registrations still need a fresh session and explicit review.

Example deadline-failure exports from run 07 (MODELED hardware facts):

- Exact attempt:
  `software/runs/pytest-camera-failure-details-20260912-07/test_public_probe_runs_once_an2/exports/wizard-20260912T014402796741Z-6d33b7f2c37b4708ae4d7c782ff0d156`.
- Ordinary diagnostic report:
  `software/runs/pytest-camera-failure-details-20260912-07/test_public_probe_runs_once_an2/exports/wizard-20260912T014402959286Z-ba5050d1729541afbd98eddb8d131280`.

Both passed the production export verifier during the public workflow test. The
exact-attempt export also reconstructed the complete cached attempt byte-for-byte.
These test exports use isolated assigned folders; the operator's workspace
export preference remains unchanged. No actual camera query/activation, USB
descriptor request, control change, serial access or arm action was performed.

This diagnostic increment is complete. The next substantive camera work remains
the measured admission-performance repair and a fresh full-history acceptance
run, followed by separately admitted received-unit identity/speed/activation
checks. No deadlines were loosened and no physical milestone was advanced.
