# USB-only entry: vendor design review

Date: 2026-09-12. Parent: [arm integration plan](ARM_WIZARD_IMPLEMENTATION_PLAN.md), A2/A3.
Status: **document review, not received-unit electrical qualification or serial release**.

## Source and scope

The official [RoArm-M3 resources page](https://docs.waveshare.net/RoArm-M3/Resources-And-Documents/)
links the General Driver for Robots schematic. Its one page was rendered and
visually reviewed, including enlarged power and reset circuit sections.
The primary download stalled; the same-named source on Waveshare's files host
downloaded successfully. No firmware/demo program or embedded PDF JavaScript
was executed.

- [Vendor schematic link](https://www.waveshare.net/w/upload/3/37/General_Driver_for_Robots.pdf).
- Download: `https://files.waveshare.com/upload/3/37/General_Driver_for_Robots.pdf`.
- [Preserved source](reference/General_Driver_for_Robots-20260912.pdf), 1,008,991 bytes.
- SHA-256: `dab698578c1b75bdf72a5ade4bada2d9f5a5da54f37737e1f41b0b2c59b9ce8a`.

The operator has confirmed the expected arm and USB-only setup. This review uses
the vendor-linked design for that product; it does not claim inspection of its
installed board revision, modification history or component condition. No repeat
model-photo request is made here.

## Findings from the drawing

The USB inputs feed the logic supply through D1/D2. Servo headers H5/H6 use
`DC_IN`, not the USB net. The drawing includes the external-input converter and
M1/Q1/Q2 power circuitry. These are different nominal supply paths, not galvanic
isolation: grounds are shared. A schematic alone does not establish measured
reverse leakage, transient behavior or a received board's condition.

U11's DTR/RTS outputs drive the two-transistor automatic-programming circuit.
Its printed logic-level table is:

| DTR level | RTS level | RST level | GPIO0 level |
| --- | --- | --- | --- |
| 1 | 1 | 1 | 1 |
| 0 | 0 | 1 | 1 |
| 1 | 0 | 0 | 1 |
| 0 | 1 | 1 | 0 |

This is a circuit logic table, not a mapping from Python Boolean values to
observed pins, and not proof of transition timing. The review therefore supports
USB-only qualification as a distinct engineering task while retaining reset and
power-state uncertainties.

## Consequences for our code

`DcbSettings` requests 115200/8N1, RTS/DTR disabled and no flow control. The
existing backend applies those settings **after** `CreateFileW`, then reads them
back. That ordering leaves initial driver/control-line behavior outside the
verified settings interval. Settings readback cannot become a no-reset claim.

Do not toggle lines, purge startup bytes, flash firmware, send a feedback query
to force a response, or restore power merely to make a passive test pass.
Preserve startup input and distinguish these observations:

1. USB metadata matched (already observed through the wizard).
2. Handle opened and settings read back (not yet physically observed).
3. Startup/reset behavior (not established by silent serial input).
4. Servo supply state (operator attestation and any independent evidence remain
   separately labeled; no software-derived electrical certification).

## Remaining release work, not another identification loop

The remaining software requirements are a versioned capable passive registration,
authenticated entry references, physical original intent/outcome storage and
qualification of the native API/owner combination. The current rehearsal record
format and checksums are not that admission. The native API intentionally still
holds before DLL loading.

An accepted physical-entry policy must specify what evidence is sufficient for
the USB-only supply review and what startup observations are required. If that
policy requires independent electrical confirmation, vendor design inference
cannot silently replace it. Do not ask the operator to probe energized circuitry
or disassemble the arm merely to complete an application checkbox.

The first eventual physical attempt remains a separately started, one-open,
zero-write observation with bounded supervision and retained cleanup evidence.
External power restoration, feedback, calibration and contact remain later steps.

No code gates, device settings, firmware, physical stage status or historical
evidence were changed by this review. No serial/camera access occurred.
