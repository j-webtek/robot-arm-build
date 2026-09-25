# Four-leg comparison auditor

Implemented `software/scripts/review_roll_comparison_block.py`. This is offline
evidence analysis, not a movement scheduler. No hardware was accessed or moved.

The auditor accepts exactly four explicit export directories, in order:
high positioning, uncorrected descending 1.25, high positioning, frozen descending
0.95 command for desired 1.25. It checks:

- Export integrity and original endpoint/hold replay through the existing reviewer.
- Distinct export IDs, one command attempt each, exact target/speed/acceleration.
- Correct frozen candidate hash on the lookup and no compensation on other legs.
- Predecessor manifest hashes and matching hold-final/fresh-baseline readings.
- Conditional host-monotonic inter-leg intervals; no inferred shared boot identity.
- Paired endpoint errors, without fitting or enabling a candidate.

Every report explicitly denies motion authority and controlled-block qualification.
Historical files cannot establish a shared clock epoch or absence of intervening
commands. CLI exit 1 means the block is not qualified as a controlled experiment,
not that the individual movements necessarily failed. The proposed 18–22 second
window is an experimental comparison parameter, NOT a live movement requirement.
It has not been added to dispatch or wizard safeguards.

## Existing block replay

Under `software/runs/wizard-exports`, supplied in this order:

1. `wizard-20260917T023425816059Z-6a5822d1d71c4decade99177cb7655eb`
2. `wizard-20260917T023527668617Z-9d6dd7e612e04a6eb2bb1d47d0b717a8`
3. `wizard-20260917T023739179740Z-cb144bbb5c0549519688d24e7b673522`
4. `wizard-20260917T023838302816Z-82abe10cb761414ea7106beb29373733`

All individual legs, commands, candidate checks and predecessor-baseline matches
passed. Inter-leg intervals were 25.063992, 94.380295 and 22.117787 seconds.
None meets the proposed window; those historical results are retained unchanged.
The timing difference is not proven to cause the endpoint difference.

Uncorrected error: +0.244140602 degrees. Compensated error: +0.156250023 degrees.
Observed absolute-error reduction: 0.087890580 degrees. This remains a descriptive
comparison, not a controlled causal estimate or an accuracy guarantee.

## Tests and remaining implementation

28 focused tests passed across the new block auditor and existing export reviewer.
Tests cover duplicate evidence, wrong command/candidate, failed endpoint/hold,
baseline mismatch, missing hold, timing misses and reversed timestamps. The real
four-export block was separately replayed.

Still needed before claiming the planned controlled experiment is implemented:
an explicitly launched finite session runner that records common clock identity,
chains predecessor hashes, completes evidence review before each next admission,
measures dispatch timing, and stops on failures. It must not reuse consumed
reservations or silently treat a missed scheduling window as matched timing.
Do not restrict ordinary single-leg tests merely because this experimental
timing protocol has not yet been implemented.

Next implement and simulate that finite runner, then execute the two planned
blocks. No automatic live sequence is enabled by this auditor.

The finite scheduling core is now implemented and simulated. See
`CONTROLLED_COMPARISON_SESSION.md` for its state/progression checks and remaining
wizard-adapter and durable-log integration. Live execution is not enabled yet.
