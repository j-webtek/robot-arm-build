# Single-micro commissioning wizard action

Current state: implemented and registered in source. **First live wizard-service
run completed on 2026-09-17 with NO_CORRECTION_NEEDED.** The predecessor and hold
passed; the optional micro command was not sent. See
`MICRO_COMMISSIONING_FIRST_LIVE_RESULT_20260917.md`. Earlier status documents saying the native entry
point is unregistered describe their earlier implementation stage; this guide
supersedes that statement.

## Where and what

In physical mode, the Arm section now includes:

**LIVE: predecessor and optional single micro-command**

Action ID: `run_micro_commissioning`. Timeout budget: 180 seconds, passed into the
coordinator cancellation predicate. Preview and construction are inert. Execution
can move the arm and must not be confused with the adjacent simulation action.

The action requires an unchecked-by-default declaration that no other web UI,
SDK, task or computer will command the arm during this test. It is a stated
operating assumption, not something the cooperative mutex proves. The preview
also states secured/powered/clear bench conditions and that cancellation is not
a physical emergency stop.

## Sequence

1. From an already admissible pose, attempt one descending 0.95-degree predecessor.
   Existing >0.5 and <=1.5-degree delta and other native checks remain unchanged.
   There is no automatic high-position move to make the starting pose admissible.
2. Verify the reported endpoint, observe the bounded passive hold and export.
3. If already within the illustrative target band, report NO_CORRECTION_NEEDED.
   No second command is sent, and no repeated predecessor searches for an error.
4. Only the specified 1.35–1.45-degree reported starting result permits the staged
   single 0.90-degree micro-command, after fresh matching feedback and all claims.
5. Verify that endpoint and passive hold, and retain per-stage and final exports.

At most two commands; no retry, return, reversal or automatic repositioning.
The UI displays status, reason, final-export confirmation and the retained report.
EXPERIMENT_VERIFIED means documented endpoint/hold, not necessarily improved
accuracy. Check classification and `desired_band_met` within the micro result.
Neither joint telemetry nor this action proves independent physical tip accuracy.

## Compact result summary

New coordinator results include `summary` in the final diagnostic attachment and
enclosing wizard result. The UI shows each available leg's command, desired
endpoint, reported endpoint, both signed errors, hold status, reading count and
maximum response gap. Missing values display as unavailable, not zero. The full
report remains available beneath the summary, including failures after settling.

`micro_result_summary.py` is a pure display projection, not a verifier or admission
source. It changes no commands, limits, calibration or progression decisions.
For the first live run it reproduces command 0.95, desired 1.25, reported
1.230468748 degrees, command error +0.280468748 and desired error -0.019531252.
The original historical exports are unchanged; only new runs include this field.

Validation: 195 related tests passed, JavaScript syntax passed, and the projection
was checked against the manifest-verified first live coordinator attachment.
The summary was subsequently checked in the actual in-app browser using the saved
first-run coordinator export: angles, signed errors and hold count rendered
correctly, with no overlap in the inspected desktop layout. The full report is now
collapsed by default and timing is displayed to three decimal places. Another 43
UI/activity tests passed, including historical-file integrity rejection and
read-only renderer checks. No hardware commands were issued during this work.

### Reproduce a hardware-free historical browser check

From the workspace, run:

```powershell
.venv\Scripts\python.exe software/scripts/camera_ui_preview.py --micro-export software/runs/wizard-exports/wizard-20260917T114136516460Z-ad0f09d93525419daad94412344c50ad
```

Open the printed loopback URL and choose **Load latest full result**. This is a
separate historical preview, not a running hardware wizard. All actions are absent
and POST requests return 405. The script verifies the selected export manifest,
computes a display summary in memory, and never rewrites the original export.
Stop the preview server with Ctrl+C after inspection.

The coordinator attachment predates completion of its own export, so its stored
`final_export_succeeded` may be false even when the manifest verifies. The preview
preserves that field, explains the distinction, and does not invent completion-log
evidence. Use the enclosing wizard operation for the later export receipt.

## Tested integration

Seven wizard-specific tests passed with the native entry point replaced: absent,
false and non-Boolean declaration rejection; inert preview; successful/no-correction/
failed result handling; diagnostic export; rejection of a non-service-owned result;
and cancellation reaching the coordinator. No fake result was injected into a
real hardware run. JavaScript syntax validation passed. Browser inspection on
2026-09-17 confirmed the rendered Arm card, its two-command description and the
unchecked declaration blocking Preview action. The accepted preview and live
execution were not exercised in that inspection. See
`MICRO_COMMISSIONING_READINESS_20260917.md` for fresh hardware diagnostics.

## Using the updated source

An existing wizard server may need restart to load the new action. Restart only
while idle; no server was restarted by this change. Confirm the initial arm pose
is suitable for the predecessor before execution. A source change, rejected
baseline or failed observation is a stop—not a reason to bypass admission.
Use the assigned workspace export folder to review reports. The existing Export
logs action also retains the service-owned coordinator outcome.

Next: retain this successful in-band branch as a live regression reference. The
optional micro branch remains untested on hardware; do not repeat predecessors
merely to obtain an out-of-band result. The final reported pose was near 1.23
degrees, which does not permit a direct descending 0.95-degree predecessor under
the existing minimum-step guard. Any positioning move needs its own bounded action.
