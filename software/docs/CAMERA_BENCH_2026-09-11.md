# Received-camera bench results — 2026-09-11

## Outcome and scope

The received Arducam B0477 works for camera-only Windows capture. Five reported
YUY2 modes completed their requested frame counts. Full resolution sustained
240 frames over 30 seconds at approximately 8 fps, with no FFmpeg frame-drop or
buffer-overflow reports in that throughput test. The full-resolution sample
shows readable can-label text on visual inspection; this is not an OCR accuracy
benchmark, lens-resolution measurement, or placemat calibration.

These were explicit, local DirectShow bench checks, **not execution of the
production onboarding wizard or acceptance of its commissioning stages**.
The arm was never accessed. No camera exposure/gain/white-balance Set calls,
driver installations, firmware updates, policy changes, or release-gate changes
were made. All test camera processes exited. Images and logs remain local.

## Observed device

- Windows name: `Arducam B0477 (USB3 20MP)`.
- Camera instance: `USB\VID_04B4&PID_0477&MI_00\7&257B140A&0&0000`.
- Parent: `USB\VID_04B4&PID_0477\Arducam_20250915_0001`.
- Windows status OK; device problem code 0.
- Microsoft `usbvideo.inf`, driver version `10.0.26100.9444`.
- Exact DirectShow name and symbolic path were matched before capture, then
  checked again after each sequence. No guessed numeric camera index was used.
- Negotiated USB link speed was **not independently measured**. The name and
  advertised capabilities alone are not proof of the negotiated link speed.

The PnP details above are a human-readable summary of local read-only PowerShell
observations. Original DirectShow inventory, mode and control logs are retained
in the export directories below.

## Throughput observations

Run `camera-bench-20260911-02`; YUY2 packets copied to a null sink, without PNG
encoding or disk recording in the throughput loop:

| Resolution | Requested fps | Completed frames | Duration target | Final FFmpeg fps |
| --- | ---: | ---: | ---: | ---: |
| 1280 × 720 | 120 | 600 | 5 s | 119.53 |
| 1920 × 1080 | 60 | 300 | 5 s | 59.97 |
| 2720 × 1536 | 30 | 150 | 5 s | 29.97 |
| 3840 × 2160 | 20 | 100 | 5 s | 19.98 |
| 5472 × 3648 | 8 | 240 | 30 s | 8.00 |

All five completed without timeout. No buffer-overflow/frame-drop warnings
were found in these five throughput stderr logs. FFmpeg's final drop/duplicate
counters were zero. These are short observations, not proof of indefinite
stability, sensor-level losslessness, or throughput while running vision.

Important discrepancy: the camera advertises full resolution at **8 fps**, and
an explicit 9 fps request was rejected with `Could not set video options`.
It also advertises 2720 × 1536 at 30 fps, rather than the 40 fps in the vendor
table. The [B0477 datasheet](https://www.arducam.com/downloads/datasheet/B0477_20MP_IMX283_USB3.0_Camera_Datasheet.pdf)
lists 9 fps and 40 fps respectively. Do not silently change the frozen camera
profile, fabricate a 9 fps pass, or conclude the camera is defective from this
alone. Driver/firmware/interface differences remain uninvestigated. An 8 fps
qualification profile requires explicit review and tests before integration.

## Controls and image acquisition

The corrected read-only control reader completed before and after runs 02/03.
Reported values/modes were unchanged across those checks:

| Control | Current driver-reported value | Mode | Advertised capability |
| --- | ---: | --- | --- |
| Exposure | -11 | Auto | Auto and manual, range -11 to -3 |
| White balance | 4500 | Auto | Auto and manual, range 2300 to 6500 |
| Gain | 100 | Manual | Manual, range 100 to 2239 |
| Brightness | 0 | Manual | Manual, range -64 to 64 |
| Contrast | 10 | Manual | Manual, range 0 to 20 |
| Saturation | 10 | Manual | Manual, range 0 to 15 |

Values above are native driver integers, not measured exposure/light levels.
In particular, a reported value while Auto is enabled must not be treated as
a locked physical exposure. Focus and iris Get/GetRange returned unsupported;
there is no demonstrated software focus/iris control. Plan for manual lens
adjustment at the final overhead working distance. Control write/readback,
manual locking and power-cycle persistence have not been tested.

Two bench-utility issues were found and corrected:

1. Run 01's control helper over-released a shared COM wrapper. Balanced release
   fixed the helper; subsequent read-only queries succeeded. The failed logs
   are preserved, not reclassified as camera failure.
2. Encoding a full-size PNG while the camera kept streaming filled FFmpeg's
   queue in runs 01/02. Run 03 captured one raw YUY2 frame after warm-up, exited
   the camera process, then encoded the PNG offline. Both resolutions completed
   with zero reported frame-drop warnings. The full-size raw frame is exactly
   **39,923,712 bytes**; the 1080p frame is **4,147,200 bytes**.

The offline PNG is a visual aid, not a calibrated colorimetric original. Raw
YUY2 files and capture logs are retained. The capture-first/release/encode
pattern is proven here in the bench utility, not automatically integrated or
qualified in the production wizard.

## Files and verification

Assigned export parent: `software/runs/wizard-exports`.

- `camera-bench-20260911-01`: first run, including the control-helper failure
  and original streaming PNG observations.
- `camera-bench-20260911-02`: successful control reads, five throughput checks,
  30-second full-resolution observation and explicit 9 fps rejection.
- `camera-bench-20260911-03`: corrected capture/release/offline-encode check;
  `sample-5472x3648.png` and `.yuy2` are the final full-size sample pair.

Each directory contains `bench-report.json`, per-command stdout/stderr and
arguments, and `bench-file-hashes.json`. Runs 02/03 also record utility source
hashes. These are bench records, not signed/original commissioning exports.
Run 03's 32 listed artifacts were independently hash-checked with zero
mismatches. Later readable summary files are outside that original file list.

Utility: `scripts/camera_bench_check.py`, with a read-only PowerShell/C# control
helper. Every subprocess is bounded and owned; output must be a new direct
child of the assigned export folder. Existing outputs are not overwritten.
Fourteen hardware-free guard tests passed in 0.24 s:
`.codex-preserved/camera-bench-guards-20260911-01.xml` (workspace-relative).
Black formatting passed; the C# helper compiled and ran on this machine.

To repeat, first enumerate the current exact camera alias with the installed
FFmpeg, close other camera applications, then use a **new** export directory:

```powershell
ffmpeg -hide_banner -list_devices true -f dshow -i dummy
.\.venv\Scripts\python.exe software/scripts/camera_bench_check.py `
  --device-alias '<exact observed B0477 alternative name>' `
  --output-directory '<new absolute child of software/runs/wizard-exports>' `
  --confirm-camera-only-tests --full-resolution-seconds 30
```

`--samples-only` skips throughput and the catalog mismatch check. The utility
requires already-installed FFmpeg and PowerShell; it does not install anything.
DirectShow enumeration/list-options may intentionally exit without a stream;
read the listing rather than treating its exit status as a capture result.

## Supervised reconnect follow-up

The operator-confirmed connected baseline, unplug detection, and same-port
reconnect capture were completed later on 2026-09-11. Evidence is retained in
`software/runs/wizard-exports/camera-reconnect-baseline-20260911-01`,
`camera-disconnected-20260911-01`, and `camera-reconnected-20260911-01`
(the latter two share the same export parent). The reconnected directory's
README records the phase comparisons and their limits.

Windows identity and DirectShow alias returned unchanged, reported modes and
control readouts matched, and new 1080p/20MP samples completed without reported
drops. The new image's framing shifted and text looks softer than baseline.
The operator subsequently confirmed slight movement; the moved object and
cause of softness are not established. See `operator-movement-confirmation.md`
in the reconnected export directory. After the operator confirmed `stable`,
fresh samples were captured in `camera-stationary-20260911-01` under the same
export parent. Capture checks passed and reported controls matched baseline,
but label fine text still appears softer on qualitative comparison. Different
framing and unmeasured working distance prevent a controlled sharpness verdict.
The operator then supplied side photos identifying the front NEAR/FAR focus
ring and the separate aperture ring; see `lens-identification.md` in the
stationary export directory. The operator reports approximately 10 inches
(25 cm) from the lens front to the can label, recorded in `working-distance.md`.
This is a temporary bench distance, not the final overhead camera height, and
the exact installed lens's minimum focus distance is still unverified. The
operator confirmed live preview, then reported having already tried the manual
adjustments and obtaining clarity by changing distance. The operator clarified
that approximately 10 inches was the best observed distance; see
`best-distance-confirmation.md` alongside `operator-distance-focus-report.md`.
Do not repeat the close-up checklist. The operator subsequently deferred all
distance/focus work until the mount, board and arm build are available. The
proposed one-metre bench check is canceled for now; no readiness confirmation
or capture is pending for it. Final working-distance focus, coverage and lens
calibration remain unverified, not passed or assumed compatible.
The camera's current manual lens position is
operator-controlled and unmeasured; no remote setting writes were made.
These checks demonstrate bench capture
and one connection-recovery cycle, not optical repeatability, frame-freshness
qualification, manual-setting persistence, or production wizard recovery.

## Follow-up checklist

1. Supervised physical unplug/replug: **completed for one bench cycle** as above.
   Optical investigation is deferred at the operator's request. No port
   disable/reboot was attempted; production wizard recovery remains unqualified.
2. Independently inspect negotiated USB speed; preserve the working cable/port.
3. Review actual 8 fps/30 fps capabilities against the frozen software profile.
   Add explicit, tested capability negotiation without silently lowering gates.
4. Test reversible exposure/gain/white-balance writes with before/after readback
   and restoration, then design repeatable manual settings for the final light.
5. Integrate the received camera facts through the wizard's original-bound
   workflow; bench JSON must never be imported as commissioning authority.
6. Once the rigid overhead mount and board exist: set working height and manual
   focus/iris, verify entire-board coverage and sharpness across the field, then
   lens/board calibration, target registration, and repeatability testing.
7. Keep arm power/motion/contact separate until assembly, mounting and its own
   onboarding/safety checks are complete. These tests authorize no arm motion.

Reference interfaces: [Arducam Windows guide](https://docs.arducam.com/UVC-Camera/USB3-UVC-Camera-Kit/Quick-Start-Guide-for-Windows/),
[FFmpeg DirectShow](https://ffmpeg.org/ffmpeg-devices.html#dshow),
[Microsoft IAMCameraControl](https://learn.microsoft.com/en-us/windows/win32/api/strmif/nn-strmif-iamcameracontrol),
[Microsoft IAMVideoProcAmp](https://learn.microsoft.com/en-us/windows/win32/api/strmif/nn-strmif-iamvideoprocamp).
