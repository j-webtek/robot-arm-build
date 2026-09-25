# Local shoulder offset: offline prediction and next test

## Finding

Freeze r29's settled actual-minus-goal offsets at **+10/-7 counts**. Without
refitting them to r31, the model predicts r31's positions as **2415/1702**;
observed settling was **2414/1702**, an actual-minus-prediction error of **-1/0**.

This is a retrospective later-trial check: the hypothesis was selected after we
saw both trials. It is not an independent prospective experiment, broad training
dataset, bidirectional validation, or demonstrated physical-tip compensation.
r29 settling also required a diagnostic restart; r31 settling did not.

## Implemented model

`application/local_pair_offset.py` implements `position = goal + frozen offset`.
It has no hardware, signing or firmware interface. Proposed integer goals must
retain sum **4114**, remain within 32 counts of the training goals, move in the
tested direction with bounded travel, and predict the desired pair within two
counts. A current residual inconsistent with the model is rejected. This is a
candidate analysis envelope, not a proven collision-free operating envelope.

Independent correction would generally change the goal sum. Instead the model
searches the small integer candidate range, minimizing maximum predicted error,
then squared error, then goal travel. This accommodates the fact that desired
encoder sums and the coupled command sum need not coincide.

Historical-only example from r31's final observation:

- Starting actual positions: 2414/1702; existing goals: 2405/1709.
- Desired next positions: 2400/1716 (14 counts of travel each).
- Constrained proposed goals: **2391/1723**, sum 4114.
- Predicted positions: **2401/1716**, predicted error +1/0.

**No proposal was sent to the arm.** It must not be passed through r31's existing
contract: that contract neither admits this starting pose nor distinguishes
desired measured endpoints from offset command goals.

## Reproduction and evidence

Run `software/scripts/analyze_local_pair_offset.py`. It verifies retained r29
source receipts and the referenced r31 movement/settling exports, applies the
frozen model, and exports its analysis without accessing hardware.

Analysis export: `wizard-20260919T234619664348Z-6c4204fac10a443e975241c707c5c763`
under `software/runs/wizard-exports/`, attachment `local-pair-offset-analysis.json`.
Model tests cover prediction, preserved coupling, count types/ranges, local
neighborhood, reverse/large/incompatible requests, self-evaluation rejection,
excessive offsets and contradiction by the current observation.

## Next bounded implementation

Update: independent host/native typed contracts are implemented and tested;
see [compensated shoulder contract](COMPENSATED_SHOULDER_CONTRACT.md). They keep
desired and commanded endpoints separate and pass 72 combined tests. Signed
capture binding and finite-session integration remain pending. No live change.

1. Freeze this hypothesis before the next physical trial. Keep r31's original
   endpoint failure visible; do not retrospectively relabel it a successful move.
2. Introduce a reviewed contract carrying separate **desired actual endpoint**,
   **command goals**, **frozen offsets**, and prediction envelope. Native and host
   checks must independently reconstruct the coupled command and enforce fresh
   baseline/prewrite checks and existing neighbor/fault/export limits.
3. Test unsupported offsets, altered goal sum, stale or changed pose, overshoot,
   shortfall, and incorrect predicted-success flags in simulation.
4. Review the candidate and its nominal clearance trajectory, then acquire fresh
   state for one prospective bounded trial. No reuse of the consumed r31 command.
5. Compare actual endpoint against the desired endpoint AND raw goal registers;
   export both errors. Only extend to further poses/directions after this local
   trial produces evidence. Camera/board/stylus accuracy claims remain deferred.
