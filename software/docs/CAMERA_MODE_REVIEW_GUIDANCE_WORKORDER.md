# Camera operating-mode review integration

Date: 2026-09-12. Scope: software-only, camera-only. Status: first guidance slice implemented and tested.

## Existing facts and constraints

The prior bench report recorded 5472 x 3648 YUY2 at 8 fps and rejected a 9 fps
request. That is historical evidence, not today's observation. The frozen B0477
purchase profile and diagnostic UVC prototype retain a 9 fps reference. Neither
record should be rewritten. Device-reported support, selected intent, matching
readback, reviewed operating policy and physical qualification are different.

The current native configuration code already authenticates probe/settings/capture
joins and compares readback. The older `assess_uvc_inventory` is a separate
diagnostic prototype with float fps, USB and reopen inputs. Do not convert native
rational modes into that format or duplicate its physical acceptance claims.

## Delivery plan

1. Implement a small, pure, versioned review-guidance module. Compare exact
   rational frame rates against the workspace's 9 fps target; distinguish the
   full-resolution 8 fps review candidate from other modes. Preserve raw numerator,
   denominator and stride. No default selection, rounding, fallback or device I/O.
2. Summarize required exposure and white-balance support separately from selected
   intent and actual readback. Missing, auto-only, ambiguous flags and readback
   mismatch must remain visible. A reported manual mode is not settings stability.
3. Reuse the existing configuration objects and bounded `meaning` presentation
   fields for this first guidance slice. Keep evidence schemas, payloads, digests,
   action IDs, stage transitions, budgets and all admission checks unchanged.
   Show guidance in both camera frontends and mode labels in the settings form.
   Modify only the camera-specific portions of shared frontend files.
4. Align frontend rational mode comparison with the existing native comparator.
   Equivalent fractions must render, but 8 fps versus 9 fps must still mismatch.
   This affects display only; original evidence authentication is unchanged.
5. Test pure 8/9/other/unknown cases, equivalent fractions, pixel-format mismatch,
   required controls, detached outputs, unchanged original bytes, inert render,
   source/service integration and frontend parity. Use modeled hardware only.
   Retain exact test selections and source hashes; preserve previous acceptance.
6. Export a readable result and next-stage contract to the workspace export folder.

## Acceptance boundary

This first slice delivers **review guidance**, not an operator review decision or
canonical stage-5 acceptance. Its version/digest identifies the guidance rules,
not an approved 8 fps operating profile, current unit identity or authenticated
original evidence. Guidance never authorizes capture, stage completion or motion.
The earlier full-history run is not relabeled as verification of this change.

## Next slice: original-bound stage-5 assessment and review

Before implementing an approval action, define a separately versioned operating
profile with target tuple, rationale, source/purchase bindings and explicit review
state. Bind an assessment to original setup/header/identity, probe capabilities,
settings epoch, capture/readback pair, USB-speed evidence and reopen subjects.
Unknown serial/speed/control/freshness facts cannot become defaults. Any accepted
exception to the 9 fps reference must be explicit and cannot repair a failed
9 fps attempt or silently select 8 fps. Operator review must be a separate event
after the assessment is published and read back; source/settings changes
invalidate it. Test full original-store publication/export/restart before enabling
that action. Keep sustained freshness and installed optics/calibration separate.

No arm implementation, hardware profile, native helper, original store or prior
export will be changed by this slice. No physical device is opened.

## Implemented wiring

`camera_operating_mode_guidance.py` owns the pure reference classification and
required-control messages. `PhysicalCameraCapabilities.view`,
`StagedPhysicalCameraConfiguration.view` and `PhysicalCameraReadback.view` put
those messages into their existing bounded `meaning` fields. Their canonical
payloads, identifiers, schemas and digests are unchanged. The camera acquisition
service adds the same classification to each existing reported mode option;
it does not introduce an option or default.

The browser and terminal render the three messages only after their existing
projection checks. Both now compare observed frame-rate fractions by integer
cross multiplication, matching the native `same_format` behavior. Requested
mode identity, dimensions, pixel format and explicit stride checks remain intact.
Only these camera-specific portions of shared UI files were patched; no arm
logic, shared routes, native implementation or hardware profile was edited.

The guidance rule ID is `b0477-mode-review-v1`; canonical rule digest:
`04eda8da6dc101f95d6133c122267de8aa8e7710ad3a0d2dc1a80eef7f171e43`.
The digest identifies display rules only, not approved operating policy. USB
identity/speed, sustained freshness, reopen stability, pixels and power are not
qualified by these messages. Structured examples explicitly mark themselves as
unauthenticated, unqualified and without stage or device authority.

## Verification ledger

Initial focused run: **118 PASS / 12.43 s**, including 36 new cases, recorded in
`.codex-preserved/camera-mode-guidance-20260912-01.xml`. This is a development
selection, not an additional 118 unique cases beyond the successor below.
Black checks all six Python files, Node syntax-checks the browser script, and
Mypy passes the guidance and physical configuration modules. No whole-repository
static-analysis claim is made.

New frozen input:
`.codex-preserved/camera-mode-guidance-isolated-20260912-01/input`, copied at
20:32:25 UTC. All **3,885 files / 899,507,588 bytes** matched before/copy/after.
Input roster digest:
`1bf1c4815767d52293b41854ff00a8ba748cd6e45e030cf8b3cdb83c3a80cf62`.

The broader **242-case selection passed in 30.05 s**, with zero failures, errors
or skips. Explicit `python -I` imports used the copied application and runner;
plugin autoload, bytecode and pytest cache writes were disabled. A new external
`tests-01/pytest` basetemp preserved all earlier test directories. Complete input
inventories and actual application source matched again after execution:
`3fd50951f5f89f8c37132a522c053df1730949745723ba267fb1c033f6dbbb5d`.

`tests-01/junit.xml` SHA-256:
`cdfe59768b902a007aa4ae2394c840f762b7f4a30c88c7770d58296104820329`.
The adjacent execution audit transcribes the inline invocation's structured
stdout, not a signed certificate. Python 3.10.10, pytest 8.4.2, Node and installed
dependencies were shared, not newly installed or separately frozen.

| Test family | Passing cases |
| --- | ---: |
| New guidance and frontend coverage | 36 |
| Existing native configuration and frontend coverage | 82 |
| Camera acquisition service | 28 |
| Small-file capture workflow | 35 |
| Settings retention, export and attempt UI | 24 |
| Unchanged purchase profile and UVC prototype | 37 |

Native observations are modeled; browser tests use a finite Node DOM harness.
Some capture-workflow tests verify real tiny YUY2/PNG files, not camera throughput
or complete M1 history. The earlier 31-minute full-history acceptance is preserved
and **was not rerun or reattributed to this new source**. Formal original-bound
stage-5 assessment, policy approval and current live hardware remain untested by
this slice. No physical camera, USB query, arm, serial, power or motion action ran.

Handoff and selected reports:
`software/runs/wizard-exports/camera-mode-guidance-20260912-01/README.md`.
The bundle contains review copies, examples and unsigned hash bookkeeping, not
an importable commissioned setup. Continue with the next-slice contract above;
do not turn guidance text into an approval decision or force stage 5 to PASS.

Successor: `CAMERA_OPERATING_EVIDENCE_PREFLIGHT_WORKORDER.md` now records the
implemented pure operating-proposal and native-evidence preflight layer. It has
82 new tests within a 474-case scoped contract run. Original-owner retention,
separate operator review and UI approval remain deferred; guidance itself is
still presentation-only and the original 242-case ledger above is unchanged.
