# First r23 powered shoulder initialization: stopped before enable

## Execution and evidence

The user approved proceeding with live movement testing. The first bounded
stage was shoulder initialization, not a lift. It ran once with no retry,
restart, firmware update, settings provisioning or automatic torque-off.

- Boot: `6053f8c5292f9b6b4d59f2f690241314`.
- Command: `r23-shoulder-hold`.
- Run export: `wizard-20260919T185232175443Z-7e43cb9dbdc34a71bcd945761fba2cea`.
- Outcome: STOPPED, controller FAULT / STATE_CHANGED, sequence 3.
- Controller counters: one preload write, shoulder enable NOT_ATTEMPTED.

Fresh initial positions IDs11–17 were
`2047,2455,1659,2906,1589,2040,2047`.
Targets were `0,0,0,2907,0,0,0`; torque readbacks were `0,0,0,1,0,0,0`.
Thus the baseline agreed with the historical readings, but it was acquired
fresh during this attempt rather than assumed.

The baseline and servo12 preload intent were exported and acknowledged. The
controller issued one WritePosEx for servo12, target2455, speed20, acceleration1.
It returned result1/device_error0. Its command timestamps were 257676919 to
257677316 microseconds. The exported joint snapshot attached to this result is
explicitly PRE_ACTION, not target readback or evidence of arrival.

After the host exported that result and sent its receipt, the controller's
fresh verification scan failed its consistency check. No servo13 preload,
pair-enable broadcast or recovery trajectory followed. No visible movement or
current shoulder torque state is claimed from the PRE_ACTION snapshot.

## What remains unknown

The predicate checks seven positions, target registers and torque states. r23
discarded the offending scan and exposed only STATE_CHANGED. Consequently the
saved evidence cannot distinguish a target-register mismatch, joint drift or
torque-state change, nor identify the joint. A successful write acknowledgement
does not settle that question. Do not tune compensation or push farther based
on this record.

## Correction prepared offline, not installed

The native session now retains a STATE_MISMATCH record containing the complete,
already-acquired failing scan before latching FAULT. This adds no servo reads,
writes, retry or rollback, and does not relax the consistency check. Synthetic
cases cover target mismatch, shoulder drift, torque change and neighbor drift
after the first preload, retaining exact values and preventing further writes.
Installed r23 and its pinned source stage are unchanged.

The spent session must not be restarted or bypassed. A reviewed diagnostic
firmware update/startup requires explicit approval; no such approval was inferred
from the movement-test request. The next test should expose the specific mismatch
before any coupled enable or upright lift is attempted.
