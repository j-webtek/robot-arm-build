# First physical smoke test: deployable-source review

2026-09-20. Offline source inspection and compile only; no device connection.

## Finding

The actual staged r31 application compiles with the default 4 MB/no-PSRAM
profile. It is not the new campaign/recovery implementation. A passing campaign
probe did not make that implementation deployable. Do not install the no-op probe
or reinstall r31 on the assumption that it contains the recovery-read endpoint.

Compile evidence:
`runs/wizard-exports/wizard-20260920T141911297986Z-959068ada58d4e37bedcec4e80dc9e5a`.

Application SHA-256:
`e8400d1c302a70bed3283c4102fa6b202785c1ea35826de2e98754a09b80fae3`.
This identifies the compiled baseline, not an approved installation candidate.

## Actual existing single-step behavior

- `diagnostic_boot.h` mounts existing settings without formatting, connects using
  saved Wi-Fi configuration and initializes the servo UART. Its setup contains
  no explicit servo acquisition, target write or torque command. This is a source
  finding, not a fresh observed startup result.
- `run_r31_local_step.py` requires a revision-31 startup binding and unused boot
  reservations. It does not implement restart, retry or return.
- `LocalShoulderStepContract` requires all seven measured positions within two
  counts of `[2047,2429,1688,2904,1591,2041,2047]` and exact goals
  `[2047,2419,1695,2907,1589,2040,2047]`. This is a historical envelope, not an
  arbitrary current-pose control path.
- The one paired write uses servo IDs 12/13, speed 20, acceleration 1; requested
  step is 12–24 counts with at most 32 counts actual planned travel. Do not force
  the arm back into that old envelope just to satisfy the code.
- New campaign composition currently exists in native fixtures and the compile
  probe. Its trusted patterns are twelve legs; recovery authentication cannot be
  grafted onto the unrelated r31 session without adapting the evidence contract.

## Smallest forward implementation

1. Add a trusted **single-leg smoke pattern** to the existing campaign preparation
   and matching host manifest draft. Preserve legacy/matched patterns unchanged.
   Sign exactly one leg; do not merely stop a host loop after authorizing twelve.
2. Anchor the smoke target to fresh capture, preserve paired-servo constraints and
   reviewed travel/joint bounds. Validate direction against measured positions,
   not just the previous goal. Fresh feedback alone does not establish clearance.
3. Test one target packet maximum, export completion, lost receipt ACK at the final
   leg and recovery snapshot with no successor movement possible.
4. Wire the existing campaign services/composition into a new opt-in board build,
   replacing rather than competing with the old shoulder owner. Reuse diagnostic
   startup, settings/key access and reservation flags; add no provisioning.
5. Compile the actual staged application, record hashes/diff and check allocation
   and startup behavior. Only then review installation and a read-only startup.
6. Use current pose and clearance for one outbound physical test with endpoint
   export. A return is separately admitted after the result, not automatic.

Camera, contact, larger campaigns, compensation tuning and wizard polish remain
outside this first smoke test. No new firmware or physical test is claimed here.
