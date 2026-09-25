# Reuse the bounded campaign owner, not a second executor

2026-09-20. Offline decision; no deployment or current device identity claim.

## Selected path

Keep official JSON for normal arm integration. For paired-shoulder experiments,
reuse the existing offline bounded campaign owner, diagnostics and export workflow.
Do not create another runner, substitute SDK feedback for raw paired diagnostics,
or send stock movements around a reserved diagnostic owner.

The host selects reviewed experiments, presents intent, orchestrates a finite
session, verifies/exports observations and analyzes outcomes. The controller owns
fresh acquisition, bounded target dispatch, one writer and fault latching. A
stable bounded miss is a measurement under reviewed policy, not accurate arrival.

## Source findings

- Documented r31 local-step operation is fixed-envelope and single-write; its
  sticky reservation prevents a host loop from becoming a reusable campaign.
- `ShoulderCharacterizationOwner` already supports up to 12 legs, fresh baselines
  and export-gated progression. It is offline code, not established as installed.
- `CharacterizationController`, preparation, admission, evidence and authenticated
  routes already exist. Reuse these components, not new route families.
- `CharacterizationPrepare` currently hardcodes the legacy pattern. Host-side
  support for another pattern does not change that controller behavior.

## Minimum remaining work

| Gap | Necessary change / verification |
| --- | --- |
| Real platform compatibility | Resolve the previously observed `int` versus `HTTPMethod` facade compile error; test with actual ESP32 WebServer headers |
| Matched-target pattern | Add a reviewed pattern selection in existing preparation, with host/native agreement tests; not an unrestricted target API |
| Board composition | Verify reservation, key/boot binding, evidence memory and real route registration in one pinned build |
| Host integration | Exercise existing authentication, result transfer, independent review and export receipt through one finite workflow |
| Timing | Check acquisition/export budgets against evidence; no arbitrary 250 ms requirement or unbounded waits |
| Release | Review pinned candidate and settings preservation before installation; retain current installed firmware throughout offline work |

The freeze on unrelated firmware expansion remains. Evaluate only narrow
compatibility, pattern and composition changes needed by this path. No new
installation, restart or movement is part of this decision.

## Better test design implemented offline

Legacy offsets `[-8, 0, -16, 0]` repeated three times move both ways, but do not
approach the same target from both directions. They do not isolate directional
endpoint error.

New optional synthetic offsets:
`[-8, 0, -16, -8, 0, -8, -16, -8, 0, -8, -16, -8]`.

The anchor-8 target receives three approaches from each direction. The partner
servo mirrors the targets, preserving the pair sum. All 12 legs, including
repositioning, are measured and checked. Speed/acceleration remain unchanged.
The sequence ends at anchor-8; there is no automatic return command.

The existing simulator and batch review now support this pattern. Default legacy
behavior is unchanged. Native preparation does not yet support it. Simulation
proves neither clearance nor physical accuracy.

From `software`:

```powershell
..\.venv\Scripts\python.exe -m rocell.application.characterization_batch_review --simulate --pattern matched --exports runs/wizard-exports
```

## Acceptance criteria for the next increment

1. Real ESP32 compile probe passes, with no installation.
2. Host/native plans agree for each reviewed pattern.
3. Native owner tests cover both directions and export-before-next-write.
4. Invalid feedback, wrong goals, uncertain delivery and failed export prevent
   further writes; misses retain their actual classification.
5. One offline end-to-end workflow produces independently reviewable evidence.

37 focused simulator/classifier/batch-review tests passed for this increment.
Compensation, larger workspace, contact and camera work remain outside this scope.

## Compile and preparation checkpoint — 2026-09-20

- Fixed the authenticated WebServer facade's int-to-HTTPMethod mismatch. The
  desktop fake now uses an enum method parameter so this regression is visible.
- Existing native preparation accepts a trusted `CharacterizationPattern` choice,
  defaulting to Legacy. Matched produces exactly the same 12 paired targets as
  the host draft. Invalid pattern values fail before reservation/acquisition.
- 50 focused native tests passed across preparation, authenticated web,
  composition, controller, capture and owner. Two compare host/native target lists.
- ESP32 core 3.0.7 compile/link probe passed with real WebServer/SCServo headers.
  The build command must retain platform `compiler.cpp.extra_flags=-MMD -c` when
  adding the include directory; dropping `-c` caused premature-link errors.
- Reproducible compile-only script: `scripts/compile_characterization_probe.ps1`.
  The probe has empty setup/loop and must never be flashed. Linker pruning means
  its reported image/RAM size is NOT a full controller resource measurement.

Matched selection is supported in the preparation helper only. The top-level
controller/composition still uses the legacy default; no network pattern selection
or release is implied. Next: thread a trusted pattern through existing composition,
test full signed challenge/host agreement, and complete offline workflow integration.

### Follow-up: composition selection and first-leg barrier

Composition and controller now carry a trusted pattern parameter, default Legacy.
Both patterns pass native signed-challenge -> Python verification/signing -> native
authenticated start integration. One simulated leg reaches AWAITING_EXPORT and
cannot advance without a receipt. 30 focused tests passed. Full transfer/export/
receipt multi-leg bridge coverage remains the next task; no firmware was installed.
