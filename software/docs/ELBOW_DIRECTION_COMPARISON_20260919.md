# Elbow direction comparison — 2026-09-19

Initial comparison was offline; the dated follow-up below records fixed read-only
hardware captures. No tuning or movement is authorized by this document.

## Observations

Both original forward exports were independently replayed before decoding their
feedback blocks with the existing pinned reference decoder. Summaries retain
acquisition timestamps and source hashes. Values below are raw reference units.

| Measurement | Earlier -6 leg | Latest +10 leg |
| --- | --- | --- |
| Position start / target / final | 2903 / 2897 / 2897 | 2897 / 2907 / 2897 |
| Endpoint assessment | Verified arrival | Verified non-arrival |
| Signed endpoint error | 0 | -10 |
| Post-command speed range | -50 to 0 | 0 |
| Post-command load range | 0 to 21 | -85 to -57 |
| Post-command current range | 0 to 1 | 2 to 4 |
| Voltage register | 121 | 121 |
| Temperature register, before / after | 30 / 30 | 29 / 29–35 |
| Final sample after command | 338425us | 2033523us |
| Snapshot count | 6 | 21 |

Successful -6 feedback review:
`wizard-20260919T155029629928Z-924eecc81d68467fb51cc86dc97b78d9`.
Original source: `wizard-20260919T122458244741Z-9b5a28f3770a4b8593c0ef6851b12cf7`.
Failed +10 feedback review:
`wizard-20260919T154934892332Z-20bb7629b0d4452b99d27b825d4fa403`.
Original source: `wizard-20260919T154710417443Z-d47c57ebbdda4ebeb7c1493b5d14da9a`.

## What this narrows down

The earlier negative movement establishes that this diagnostic path can report
changing position and speed. In the positive trial, accepted target readback and
changed effort/status fields argue against a wholly ignored command or wholly
frozen feedback block. Position-specific feedback problems remain possible.
Direction-dependent actuation under the tested conditions is supported; a
particular mechanical, load or controller cause is not established.

This is not a matched experiment: firmware revisions, pose, initial loading,
amplitude and observation duration differ. Do not claim the raw temperature
change was caused by this one command or convert it into a safety threshold.
Do not interpret the current/load values as physical force or current without
verified scaling. Neither successful negative travel nor target acceptance
proves stylus accuracy.

## Retained settings checked

Verified saved configuration assessment
`wizard-20260919T105743948843Z-86a974e2fd4944019f387ace0da0fda6`:
deadbands26/27=0/0, mode33=0, torque40=1, acceleration41=1, speed46=20,
torque limit48=1000, limits9/11=0/4095. Retained gain evidence
`wizard-20260919T130037515734Z-79eaa1fc12d1488089be0dbf31b17ccb`:
P32/D32/I0. These are historical observations, not fresh current settings.
They do not establish a configured five- or ten-count deadband. I=0 alone does
not establish a gain defect, and no gain changes are recommended yet.

## Next decision

### Recommended branch: targeted no-touch inspection before more actuation

The next missing fact is whether the folded forearm/gripper or cabling contacts
the board, base or another link in the failed pose. Request a targeted no-touch
inspection for that question, not routine visual confirmation of every command.
Do not request manual joint rotation, screw adjustment or unplugging the
unsupported arm. If contact is present, stop testing and plan supported clearance
correction. If absent, that does not exclude internal friction or load effects.

`STOPPED` is the diagnostic sequence state, **not torque-off**: the last reads
reported torque1 and the last goal2907 while measured position remained2897.
Do not infer that the servo ceased exerting effort when the sequence stopped.
No automatic torque disable or recovery is authorized; earlier loss of power
allowed the unsupported arm to fall. Any unloading or power-removal procedure
must first provide mechanical support and be explicitly scoped.

After the inspection, the useful experiment is a matched, bounded comparison
under a documented load/pose, with settings fixed and independent displacement
evidence if encoder-only ambiguity persists. It cannot be fully specified from
the present historical photos alone. A load change requires rechecking joint
windows and fresh registration; do not widen limits or invent clearance.
Retain requested/encoded/readback targets, position, speed, raw load/current,
temperature, voltage and timing for both directions. A difference after changing
load would support load sensitivity, not by itself prove a gain or hardware fault.
No new movement is approved or executed by this proposal.

### Fresh read-only follow-up completed

2026-09-19: inspected the immutable installed r21 routes. The configuration/gain
gate admits PairNetworkPhase::Fault only when hold/pair/recovery are not doing
exclusive work; capture handlers perform fixed reads and GET returns saved bytes.
Verified current same boot `0b0e6cbe9e70093fb7be20fe6e117814`, pair STOPPED,
LEG_NOT_ARRIVED and storage_fault=false before each capture. Performed one
configuration and one gain acquisition, each with matching retained GET and
verified exports. No reset, retry, recovery, motion or servo-setting writes.

- Configuration: `wizard-20260919T155259859927Z-2f5e054a3fdd40759d4c0d1787c52e97`.
- Configuration transport: `wizard-20260919T155259929151Z-c8b32f768dcd443ca3eb35655b74c5aa`.
- Gains: `wizard-20260919T155316025837Z-ffc1aabe26234a9bb53c30c53904865d`.
- Gain transport: `wizard-20260919T155316087377Z-38a1787f33ed43fab0ebf38fdf8a2724`.

Fresh configuration matches the historical values above, including deadbands0/0,
mode0, torque1, acceleration1, speed20, torque limit1000 and limits0–4095.
Fresh gains also match P32/D32/I0.
These observations remove a stale-settings uncertainty but do not establish the
cause of the positive-direction non-arrival. Both acquisition allowances are now
consumed for this boot; do not repeat automatically. The next decision is a
discriminating load/mechanical/control experiment, not firmware changes merely
to obtain these already available settings.

1. Preserve the stopped state and all exports; no automatic return or recovery.
2. Review whether installed read-only diagnostics can safely acquire current
   mode/limits/gains after the stopped trial without resetting or taking over
   the bus. If unsupported, report that capability gap before modifying firmware.
3. Before another powered experiment, consider load or mechanical resistance as
   alternatives to software compensation. Do not ask the user to loosen, rotate
   or disconnect an unsupported arm; any physical inspection requires a separate
   supported procedure.
4. Choose one discriminating bounded test only after that review. Do not simply
   increase amplitude, torque limit or gain until motion appears. Separate any
   settings-change authority from test authority and retain existing stop rules.
5. Apply a compensation model only after reproducible actual motion and held-out
   endpoint evidence exist. A goal-register update without displacement is not a
   usable calibration sample for a constant endpoint correction.
