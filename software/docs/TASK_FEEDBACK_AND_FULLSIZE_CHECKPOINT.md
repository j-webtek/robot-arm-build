# Task-result clarity and full-resolution pixel checkpoint

Date: 2026-09-10. Implemented software increment, **not hardware acceptance**.
The complete application goal and the remaining physical camera/arm workflows
are unchanged. See `ONBOARDING_APPLICATION_COMPLETION_MATRIX.md`.

## Delivered

- Task operations now distinguish worker status from the simulation outcome.
  Required-check failure, sampled IK gaps, sampled convergence, incomplete
  execution and unavailable/inconsistent summaries have separate visible text.
  All remain diagnostic-only. The renderer uses the existing single named
  service step; it does not fetch results or rerun a task automatically.
- Tasks explicitly disclose the current legacy arm-mounted-camera calibration
  graph. The selected overhead architecture still needs the versioned task
  migration in `STATIC_TASK_SIMULATION_MIGRATION_WORKORDER.md`; no old artifact
  is renamed or treated as commissioned overhead calibration.
- The native-settings staging form now shares the existing portable operator-ID
  rule at preview and execution, with visible help. Spaces and other invalid
  characters fail early. The redundant late-only regex was removed; accepted
  operator IDs, controls, modes, permissions and stage effects are unchanged.
- A new real-file test handles full-resolution synthetic B0477-sized YUY2
  frames, not only tiny fixtures. It verifies native bytes after ingestion,
  retained hashes, re-verification, bounded preview scale and all four known
  corner values for both top-down and bottom-up row layouts.

The [manufacturer's B0477 specification](https://www.arducam.com/blog/product/arducam-20mp-usb-3-0-camera-module-with-16mm-c-mount-lens-b0477/)
was rechecked on 2026-09-10: its published full mode is 5472×3648 YUY2 at 9 fps;
120 fps is listed at 1280×720. One tightly packed full frame is 39,923,712 bytes,
within the existing 64 MiB frame limit. This arithmetic and the synthetic test
do not prove the received camera's modes, actual USB throughput, freshness,
focus or lens suitability. The live probe must still observe the exact unit.

## Changes and verification

Production files: `ui/static/app.js`, `application/wizard_actions.py`,
`application/physical_camera_acquisition_service.py`.
Test files: `test_wizard_task_simulation_feedback_ui.py`,
`test_wizard_setup_operator_input.py`,
`test_b0477_full_resolution_capture_ingest.py` under `tests/unit`.

Tested application source fingerprint:

    6bc0f27d66424e55518a9233cc227664945df3312b26986c648ba1cf0488d12d

Focused run: **113 passed**, no failures/errors, 5.50 s (JUnit 5.468 s):
36 UI outcome cases, 75 portable-ID cases and two full-resolution byte cases.
Report `.codex-preserved/task-feedback-fullsize-20260910-01.xml`, SHA-256:

    63b75d263412e44029a25889d13a0f3d3b40e90511d917902eb38a5fc0c85382

The separate preceding red reports remain intact: task feedback 33 expected
failures/three passes; additional settings form eight expected failures.
Node syntax validation, Black checks on five touched Python files, and Mypy
on both changed production Python files passed. These are selected checks,
not a whole-repository or physical-acceptance claim.

The selected action/acquisition/configuration/UI regression run is terminal:
**336 passed, one deselected**, no failures/errors/skips, 331.95 s (JUnit
331.885 s). Report `.codex-preserved/task-settings-regression-20260910-01.xml`,
SHA-256:

    a3b322a1aa71b07b576f387e7a3c82800712eff36ba7f71f0d056272bd87637f

Probe-only changes overlapped this run after the browser review closed;
therefore its evidence is scoped to the unchanged UI/settings components,
not an asserted whole-source freeze across that separate optimization.

## Actual browser walkthrough

Launched `start-rocell-wizard.ps1 -Mode rehearsal -NoBrowser` on the source above.
In the real browser, the Tasks page showed the legacy-model limitation before
any action. The keyboard `hi` simulation used separate Preview and Execute.
While running, no feasibility outcome was inferred; after completion the UI
displayed **Worker status: SUCCEEDED** separately from **unresolved reachability
checks**. The yellow warning remained visible outside collapsed evidence and
beside the explicitly opened full report. The hardware-execution form remained
unavailable. Screenshots were inspected using the computer-use skill's
browser-first guidance; no native OS/privacy/device settings were changed.

Session: `wizard-aca6becdfdb048f7adb2e6faed607b84`.
Simulation operation: `operation-6fd779d3b178499abb0df7ae2bd3f9ad`.
Its report still has two of eight sampled IK points converged. This change
exposes the existing result accurately; it does not solve those IK gaps.
The attachment records zero device opens, serial writes, power events, motion
commands and contact commands, and no physical authority.

A separate explicit UI export produced:

    software/runs/wizard-exports/wizard-20260910T202414583794Z-7cbeb8147e3b4d49b3ea62d04055f08d

Independent absolute-path verification returned `VERIFIED_DIAGNOSTIC_EXPORT`:
four indexed payloads, 194,175 bytes, the source above and physical authority
`NONE`. Manifest SHA-256:

    09aaa86943599235d6da6d4d34b732b1a79f5872679adbdebdcbf0b7dc715f9f

The original diagnostic log was also independently verified: five events,
no replay and no physical authority, with final chain head:

    047998a88ece803806364f83dd01fa36dbee68a0cc17480e5dc1e2849069337a

Its final export-completion event follows the snapshot packaged in the export;
that ordering is expected and does not make the snapshot a live session.

The browser tab was closed and its own launcher explicitly interrupted after
export completion (final UI revision 10). No earlier export was overwritten.

## Integration failure is separate and still open

The preceding full-history run 02, on source `70f10a3e...bde902`, terminated at
the probe with `CAMERA_ATTEMPT_NOT_KNOWN`. Its retained result is uncertain
because the final admission window expired before release. Settings capture,
exact attempt export and final original re-read were not reached. The correct
uncertain hold is not relaxed by these UI/input/pixel tests. See
`CAMERA_FULL_HISTORY_INTEGRATION_WORKORDER.md` for that failure and its retained
evidence. The next bounded optimization must preserve the post-disk family
integrity audit, use fresh reads at every boundary and retain existing clocks,
budgets and no-replay behavior.
