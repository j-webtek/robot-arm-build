# Received arm USB onboarding — 2026-09-12

Next implementation work is tracked in the [arm wizard plan](ARM_WIZARD_IMPLEMENTATION_PLAN.md).

## Actual outcome

**USB metadata detection is fixed and physically tested. Serial communication
and arm control are not yet released or tested.** Do not interpret a metadata
PASS, a successful export, or Windows device status as a connected robot.

The user confirmed the arm is secured with its working radius clear, then
confirmed that external actuator power was disconnected and USB remained
connected. Both physical wizard acquisitions below were metadata-only. No COM
port was opened, no reset/init/feedback/motion command was sent, and no camera
endpoint was opened. This operator acknowledgement is not an electrical
measurement or a commissioned power-safety receipt.

Observed USB candidate:

- COM6; VID `10c4`, PID `ea60`.
- USB bridge serial `A02C8734397FEF11A7321C1CEDD322A4` (not an arm chassis serial).
- CP210x; driver provider Silicon Laboratories Inc., version `6.7.3.350`.
- Reported network MAC `FC:E8:C0:F8:D5:38`, AP `ROArm-M3`, ST `OFF` remain
  separate user observations. They did not supply the USB identity.

## Defect and fix

The present CP210x COM interface provides a native instance and driver fields,
but omits the serial-interface PortName/VID/PID properties used by our reader.
The original acquisition retained `NATIVE_MAPPING_NOT_PRESENT`.

The reader now obtains missing legacy USB fields from the exact present native
USB instance and its read-only device registry `PortName`. It never fills native
fields from a friendly name, the selected COM string, or generic serial data.
Registry reads use a fixed 2048-byte buffer, a strictly validated native instance,
query-only access, strict REG_SZ/COM validation, and unconditional handle cleanup.
Missing/denied/malformed/conflicting observations cannot silently pass. No
fallback runs against the actual registry from an incapable CM test fixture.
CM/registry observations remain non-atomic and are not device-handle authority.

The existing wizard supplies fresh acquisition, candidate review, native
correlation, supervised metadata worker, completion logging, and verified exports.
The new script is a terminal entry point to those same public service actions;
it does not introduce an alternate serial backend or a new storage system.

## Evidence

- Before: `software/runs/wizard-exports/wizard-20260912T170752004744Z-230fe9f1ab294c1485b3046290095425`
  — HELD, zero native matches.
- After: `software/runs/wizard-exports/wizard-20260912T171057286053Z-b203a0292dc84e7cb35a44af4f4b9ce2`
  — METADATA_CORRELATED, one generic and one native match, no blockers.
- The script verified each export using the existing export verifier.
- Final source verification: `software/runs/wizard-exports/wizard-20260912T171322630694Z-265416e81c2e429eb21b514d0fa19f4c`
  — METADATA_CORRELATED, no blockers, source
  `ef02d2cfd73a2005b461f884416ed192705b8b109d339877b272f97ee5b0bc84`.
- Focused regression: 171 passed (legacy registry, CM metadata, controller
  resolution, public wizard integration, new preflight harness).
- Expanded final regression: **366 passed**, additionally covering feedback
  worker, non-purging serial backend and native arm UI. Scoped Mypy passed for
  both edited/added production metadata modules. No live serial effects.
- These are physical metadata observations plus incapable software tests, not
  successful physical feedback, calibration, or motion tests.

## Repeat the metadata check

Only after the operator confirms external actuator power is disconnected and
USB remains connected, from the workspace root:

```powershell
.\.venv\Scripts\python.exe software/scripts/wizard_arm_usb_preflight.py --vid 10c4 --pid ea60 --usb-serial A02C8734397FEF11A7321C1CEDD322A4 --reviewer Jack --external-power-disconnected
```

This explicitly selects the USB tuple, not the first port. The current COM
mapping is reacquired. The script stops on ambiguity, never retries a device
action, exports known failures once where possible, and starts no further action
when an operation outcome is unknown. A retained HELD correlation exits with
code 2 after exporting. Logs use the assigned workspace wizard-export folder.
Each invocation creates a diagnostic session; it does not restore a live
connection in a separately running browser wizard.

## Remaining path to a working arm

1. **Serial backend qualification (not yet implemented as a released workflow):**
   reuse the existing non-purging Win32 API and owned process supervisor. Add a
   reviewed bench-qualification protocol with its own explicit power-disconnected
   entry, current native identity, bounded one-use lifecycle and retained result.
   Do not remove unconditional holds or manufacture commissioning receipts just
   to open COM6. Verify driver/control-line and boot behavior with external
   actuator power disconnected before contemplating a powered session.
2. **Lifecycle tests:** exclusive ownership, device disappearance or changed
   mapping, startup bytes/reset banners, failed open/configuration/readback,
   partial writes, timeout/cancellation, and confirmed handle/process cleanup.
   Preserve startup input; no hidden purge, automatic retry, initialization,
   firmware flashing or arbitrary command interface.
3. **Feedback-only physical test:** after that qualification and the required
   power/identity review, allow one fixed T=105 request and validate T=1051 with
   the shared parser. Retain full result and independent observations; close
   explicitly. The actual received firmware and boot policy remain unknown.
4. **Wizard integration:** expose the same qualified owner and lifecycle results
   in the existing Arm page. A metadata pass must not auto-connect or transition
   to powered operation. Original stages 9–12 and their predecessors are still
   incomplete; this preflight is not a substitute for them.
5. **Motion later:** tool mounting, limits, reference pose, placemat registration,
   camera-to-board and arm-to-board calibration, noncontact path testing, and
   separate controlled contact validation before keyboard/phone tasks.

## Official references

- [Waveshare RoArm-M3](https://www.waveshare.com/wiki/RoArm-M3): USB serial
  communication, 115200 baud, and the correct USB interface.
- [Microsoft USB identifiers](https://learn.microsoft.com/en-us/windows-hardware/drivers/install/identifiers-for-usb-devices): native USB VID/PID components.
- [Microsoft serial driver example](https://github.com/microsoft/Windows-driver-samples/blob/main/serial/VirtualSerial2/device.c): device registry PortName assigned by the ports class installer.

## Fresh USB-only check after operator confirmation, 2026-09-12

The operator explicitly confirmed the expected arm is attached and that only USB
power is connected; the external power adapter remains disconnected. Treat the
model/setup statements as operator-confirmed. Do not repeat the model-photo
request as a prerequisite to metadata checks. This does not independently prove
electrical isolation, installed firmware or serial communication.

The existing public wizard metadata preflight completed successfully:

- Status: `METADATA_CORRELATED`, no metadata blockers.
- Five serial candidates; exactly one generic and one native match for the
  explicitly selected `10c4:ea60` bridge serial
  `A02C8734397FEF11A7321C1CEDD322A4`. No first-port selection or fallback.
- Session: `wizard-d7cfdddacbb64726acaa1a9630046b73`.
- Native operation: `operation-55e968c87f674dfd80d87a540ce431be`.
- Source: `fe10bbb1730feace73145a905022bc14d914e2ad240139a6a07951880c6ccb79`.
- Verified export:
  `software/runs/wizard-exports/wizard-20260912T180846056837Z-23b9d541a6ed41a6b9377e67182f4ee2`.
- No serial port opening, outbound JSON, initialization, power switching, motion
  or camera access. The wizard still reports connected/qualified false because
  this checks Windows metadata, not communication with the controller.

The immediate remaining implementation gap is qualified physical serial
dispatch/admission, not evidence that the USB adapter is attached.

## Camera history (not changed by the USB check)

The earlier camera full-history run 06 ended **FAILED**, not in progress:
1 failed, 7 deselected in 2053.84 seconds. Probe and settings staging passed;
capture later encountered a missing `rocell.ps1` in its partial test workspace.
The omitted capture-workflow source-fingerprint fixture seam has since been
corrected in the isolated fixture. Run 07 completed its workflow, but its source
audit rejected concurrent checkout changes; it is not fixed-source acceptance.
See [the current camera source audit](STORAGE_EXISTING_ROOT_OBSERVATION_WORKORDER.md)
for retained paths, checksums and the terminal source guard. Older documents
saying run 06 is in progress or that its fixture correction remains pending are
superseded. No camera full-workflow release PASS is claimed by this arm work.
