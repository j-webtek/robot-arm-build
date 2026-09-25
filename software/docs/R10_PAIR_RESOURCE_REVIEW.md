# R10 pair preparation resource review

Status: subsequently installed with explicit powered-update approval. Full app
readback and protected-region checks passed; one startup completed. See the latest
hardware checkpoint in `COMMAND_TO_SERVO_DIAGNOSTICS_PLAN.md`. The offline review
below remains historical evidence, not powered movement qualification.

## Change and evidence

Prepare-path parsers and file/canonical buffers now use one checked temporary
heap allocation. Its lifetime covers parsing and runtime initialization, ending
before the initial network challenge is issued. Key material remains separate
and is wiped after initialization. Allocation failure precedes file/key access
and hold retirement; a native fault-injection test covers that boundary.

- Compile export: `wizard-20260919T012312312556Z-dd795d7c04f14f68ba11fbc96b7059a0`.
- Review export: `wizard-20260919T012725080913Z-5b946c1dd7eb44e6b8e09626ccb27d32`.
- App SHA-256: `b07fd9a442bfeb58a9b846828a5b6cedf25441fd9ce322be9f8f72f32ef9389d`.
- App size: 1,103,808 bytes; app-slot headroom: 206,912 bytes.
- Largest relevant individual compiled frame: 432 bytes, versus r9's 3,808.
- Pair parser frame: 320 bytes, versus r9's 1,328.
- Source/artifact hashes, retained original backup pair/recovery slot, retained
  r7 app, diagnostic startup wiring and partition/bootloader profiles verified.

The optimized compiler can inline functions; these frame comparisons do not
prove a total nested stack bound. Temporary heap demand increases during prepare.
Runtime free/largest-block heap and stack high-water evidence remain outstanding.
The review does not verify current device bytes or physical accuracy.

## Next steps

Installer checkpoint: the exact r7-to-r10 edge is now implemented. Local
`--revision 10 --preflight-only` passed against the retained real artifacts,
including both supported-pose provisioning receipts and the private DPAPI image
SHA-256 `4524696545583513b283348789b2e1f92ed37e178efcb10edf32dcbd639ec4bf`.
No plaintext image was written or mounted. Fourteen offline installer tests pass,
including mismatched receipts/images, prewrite mismatch stops and device-library
exclusion from preflight. No deployment journal was reserved or hardware opened.
Device contents remain unverified until a separately authorized installation.

1. Completed offline: exact installer edge and latest filesystem expectations.
2. Complete explicit live trial admission in the wizard; preserve one-use
   receipts, export gates and fail-closed progression.
3. Request separate approval for the exact app-only installation/startup and
   any pair-settings provisioning. Existing powered-hold approval is consumed;
   it is not authorization for new firmware or a movement pair.
4. After approved deployment, measure resources and obtain fresh same-boot hold
   evidence before a separately authorized bounded forward/return trial.

Support the arm before removing external power: loss of torque previously
allowed it to fall. No power, serial, network, flash or servo action occurred
during this review. Installed r7 remains unchanged.
