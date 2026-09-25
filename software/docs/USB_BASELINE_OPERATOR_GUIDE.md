# Guided USB trial baseline

Status: operator draft; public held and modeled-nominal baseline/export/reopen
software paths verified, 2026-09-09. The nominal test uses real original storage
and M1 admission with modeled boot/USB/process observations; no received device
was queried and later stages stay pending. This guide describes the service-
backed sequence, not a declaration that a received
camera or the complete wizard is qualified. See the
[implementation work order](USB_RECONNECT_WIZARD_IMPLEMENTATION.md) for current
verification and the remaining reconnect/restart, capture and arm work.

After an eligible complete baseline the UI can now guide five separate absence
actions: begin/report unplugging, review the boot-check scope, collect the boot
report, review the exact presence query, then explicitly collect. This successor
now has a passing full real-storage software test with modeled hardware facts;
its earlier failed original remains preserved. Do not treat that result or the
visible controls as complete reconnect qualification or a received-hardware
test. See the [absence record](USB_ABSENCE_PHASE_IMPLEMENTATION.md).

The AFTER_RECONNECT successor now has service-backed Begin, Prepare, Review,
host-boot collection and descriptor-collection controls. Fresh public run 06
passed with real storage/logs and modeled observations; use the
[reconnect work order](USB_AFTER_RECONNECT_IMPLEMENTATION.md) for the result.
The new AFTER_REBOOT controls have scoped integration tests, with full public
v13 acceptance pending: the first complete run stopped on a timing hold in its
reconnect predecessor, before the reboot actions. A passing software test or visible button is
not received-hardware qualification.

## Before collecting

The cell remains RoArm-M3 Pro with the purchased static overhead Arducam
B0477/IMX283 camera and nominal 16 mm lens. This increment does not move the
camera onto the arm or change the board build/freeze. USB identity checks do
not calibrate camera height, lens distortion, board coordinates or the tool tip.

Launch from the workspace with `./start-rocell-wizard.ps1`. Rehearsal is the
default. `-Mode physical -Check` checks startup configuration without starting a
hardware action. Physical collection requires a separately reviewed original
setup session, the prior source/build/received-camera stages and an explicitly
declared USB qualification trial. Do not mark an unknown observation as PASS to
make a button available.

For a first, hardware-free visit, open **Guided rehearsal** from Overview.
The **Camera** page separates the last retained image, metadata, settings and
physical-stage records; a connected local web service does not mean the camera
is connected. **Diagnostics & exports** shows the assigned export destination
before any report is written. Opening pages does not run a test or connect a
device. Every executable action has its own preview and explicit execution.

The original trial records the selected cable and port labels. Its baseline
must be newly collected after declaration. A previous standalone USB diagnostic
remains useful history, but it is not this trial's first phase.

## Operator sequence

1. Begin the trial BASELINE. The wizard records a new phase identity and start
   time before collecting metadata. This action is file-only.
2. Use the existing device inventory and camera-selection/review controls, then
   collect native camera inventory and identity and review the exact selected
   endpoint. All three acquisitions must be new, in order, in this phase and
   this application launch. The service records acquisition and completed-log
   times; merely re-reviewing cached metadata is insufficient.
3. Refresh the original setup view if it was invalidated during acquisition.
   Prepare the baseline from the current reviewed metadata and fixed runtime
   file inspection. Preparation records the actual acquisition lineage and
   phase-specific command. It does not execute that command.
4. Review the exact selected camera, original trial, runtime and query scope.
   The separate reviewer label is a procedural acknowledgment, not an
   authenticated second person's identity. Review includes consent to the
   bounded local host-boot metadata check. There is still no camera capture or
   arm access.
5. Explicitly collect. The wizard first commits a boot request, observes the
   reported host UUID and boot epoch using its owned bounded process, and
   retains the result. Only a complete clean physical boot observation can
   proceed to the separately requested and permitted USB descriptor query.
6. Inspect the retained baseline result. The phase joins the plan, fresh native
   metadata, boot observation and exact USB campaign originals. A retained
   baseline is not completion of the four-phase trial and does not enable
   camera capture, arm power, motion or contact.
7. Export the USB diagnostics before troubleshooting or sharing evidence. The
   assigned parent is
   `C:\Users\Jack\Desktop\robot-arm-build\software\runs\wizard-exports`.
   Each export creates a new child folder. Review identifiers, paths and
   operator labels before sharing; credential redaction is not a guarantee
   that every private detail has been removed.

## Stop, restart and incomplete results

Stop cancels acquisition; the software still tries to retain the actual result
and cleanup information. Closing the app is not a clean completion signal.

The restart-before-preparation advice in this baseline table applies to the
BASELINE phase only. AFTER_RECONNECT is launch-bound from Begin; its different
restart rule is described below.

| Situation | Required response |
| --- | --- |
| Old or incomplete acquisition lineage | Before preparation, collect the missing fresh metadata in the displayed order. Do not change hashes or timestamps by hand. |
| Restart before preparation | Reopen and refresh the original session, then reacquire all required metadata in the current launch. |
| Restart after preparation/review | Review/export only for that prepared phase. Do not attach new-launch boot data to old-launch metadata. |
| Boot or USB request exists without complete result | Treat it as incomplete; export the original state. Do not replay the request or edit its journal. |
| Unconfirmed cleanup or uncertain effect | Keep the hold. Review the full cleanup/attempt evidence; do not interpret missing counts as zero. |
| `FULL_USB_LIFETIME_DOES_NOT_FIT` | Export the attempt and its timings for developer review. The remaining original permit window was too short; do not retry the consumed request or increase time limits in configuration. |
| Source or configuration changed | The old subject is stale. Preserve it for diagnosis and follow an explicitly supported new-trial/session workflow; do not relabel it as current. |

No reboot, driver install, device disable/remove, automatic hardware retry or
implicit camera/arm activation belongs in this baseline workflow. The later
unplug, reconnect and Windows Restart phases are separate guided operations.

## AFTER_RECONNECT: separate guided sequence

This sequence has passing joined public software acceptance with modeled
observations. It starts only from an eligible, complete original physical-node ABSENCE result.
The selected camera, cable and port remain those declared by the trial.

1. After reconnecting manually, choose **Begin** and confirm the operator
   report. The report records what the operator says happened; it does not
   independently prove that a cable was moved.
2. Collect/review the generic camera inventory, then collect native inventory
   and exact endpoint identity and review that endpoint. All three acquisitions
   need new successful completion logs after this Begin in this launch.
3. Choose **Verify original camera setup records**. Metadata acquisition
   deliberately withdraws the old Setup publication; this file-only Refresh
   verifies the same original before Prepare. The next-step guidance offers
   it only for an unused same-launch phase with all three logged acquisitions.
   It must preserve the current phase and acquisition ledger.
4. **Prepare**, then separately **Review** the exact operation, policy, runtime,
   target and host-boot scope. These steps do not execute a USB query.
5. Explicitly **Collect host boot**. Inspect its result before continuing. This
   action never automatically starts descriptor collection.
6. Separately **Collect USB descriptors**, inspect the retained result and
   export the complete USB diagnostics to the displayed destination. A locally
   retained result still does not enable camera capture or arm access.

If the app closes after reconnect Begin, preserve and export that original;
do not resume it in a new launch, change its report, or relabel new metadata as
old-launch evidence. An attempted preparation, partial write, consumed query,
uncertain cleanup or changed source also stays held. Refresh is not a retry or
a way to clear those conditions. AFTER_REBOOT and final independent trial
qualification remain separate work, not something an application restart proves.

## AFTER_REBOOT: new-launch developer sequence

The controls and scoped tests are installed; full public v13 acceptance is
still pending. This is not approval to commission received hardware. The
[reboot work order](USB_AFTER_REBOOT_IMPLEMENTATION.md) records current evidence.

1. Complete and export an eligible clean AFTER_RECONNECT. Close the wizard.
   For eventual received-hardware testing, Windows Restart is a manual operator
   step; the wizard never issues a restart command.
2. Open a new wizard launch, **Discover saved camera setup records**, choose the
   exact source-matching original, then **Open selected original camera setup**.
   This reads history; it does not reconnect devices, restore live permissions
   or replay an old query. Changed source/configuration stays held.
3. Choose **Begin reported host-restart interval** and confirm the report.
   Merely closing/reopening the app does not prove Windows restarted.
4. Collect and review fresh generic camera inventory, native inventory and
   exact native identity, in that order. All three acquisitions need new
   completion logs after the new report. Then explicitly **Verify original
   camera setup records**, preserving this interval and its acquisition ledger.
5. **Prepare fresh after-reboot metadata and files**, then **Review exact
   after-reboot subjects**. These are file/review steps, not USB queries.
6. **Observe after-reboot host boot once**. The separate result must establish
   the same reported host, a different boot, and a reported boot epoch after
   reconnect completion and no later than Begin. Missing or inconsistent
   observations remain held. Boot metadata is provider-reported, not attestation.
7. Only after a clean retained boot result, separately **Collect after-reboot USB
   descriptors once**. Inspect the literal values/comparisons and export USB
   diagnostics. Four retained phases still require independent final assessment;
   they do not enable live images, arm access, motion or contact.

Closing the app during this new interval, partial writes, unknown cleanup and
already-attempted requests remain export-only. Refresh does not renew them.
Missing process/device counters remain unknown, not zero. Use issue notes to
describe investigation; marking a note resolved does not qualify a device or
remove a physical safety hold.

## Development verification versus received hardware

Real local-storage baseline tests cover both a held boot result and a nominal
modeled boot-to-USB result. They run the public actions, retain complete original
evidence, verify export/restore and reopen without replay. Boot, USB and process
observations are explicitly modeled; neither test queries received hardware.
The separate absence increment also passes full public software acceptance;
follow its implementation record for the preserved failed run and fresh-session
result. AFTER_RECONNECT public integration also passed; AFTER_REBOOT has scoped
tests while its complete new-launch public acceptance remains pending.
A previous real-browser check also recorded a hardware-free note and exported
it in the assigned folder. These checks validate only the tested software paths;
they do not establish a clean physical baseline or full reconnect qualification.

Software tests may use real local files and owned incapable processes with
MODELED camera/host facts. Those results prove the tested software behavior,
not that your camera enumerates correctly, is operating at USB 3 speed, keeps
the same identity after reconnect, or sees the whole placemat. Received-unit
checks and optical/board/arm calibration remain necessary before typing or
phone tapping.
