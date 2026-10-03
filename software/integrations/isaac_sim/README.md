# Isaac Sim integration boundary

- **Document status:** Active implementation reference
- **Audience:** Runtime and simulation contributors
- **Authority:** Software-test guidance only; this integration grants no
  hardware, motion, contact, or release authority.

This directory documents the optional NVIDIA Isaac Sim runner. Executable,
packaged contracts live in
`software/src/rocell/integrations/isaac_sim/`; versioned JSON schemas live in
`software/schemas/`.

The current WP0 implementation provides:

- canonical v1 request and receipt envelopes;
- exact-field, unit, frame, joint-order, timing, digest, and zero-authority
  validation;
- a hardware-free fake adapter for lifecycle and evidence tests;
- a fail-closed external toolchain lock; and
- compact valid and invalid fixtures.

It does **not** import Isaac Sim, load a USD scene, use a GPU, run physics, or
produce clearance/contact evidence. A fake-adapter `PASS` has evidence class
`CONTRACT_TEST_ONLY` and expressly establishes only contract behavior.

## Verify WP0

From `software/`:

```powershell
python -m pytest tests/unit/test_isaac_sim_contracts.py -q
```

From the repository root:

```powershell
python scripts/ci/check_docs.py
```

## Select the external runner

The committed
[`isaac_sim_toolchain_lock.json`](../../config/isaac_sim_toolchain_lock.json)
is deliberately `UNSELECTED`. Do not replace its null fields with guessed
values. On the designated compute runner:

1. install or pull one exact Isaac Sim release using an NVIDIA-supported path;
2. retain the exact installer/container identity and calculate its SHA-256;
3. export the enabled extension set and settings profile as canonical files;
4. hash both files;
5. record the runner platform and deterministic launch method;
6. review the exact selected version's license terms for the intended internal
   integration; and
7. change `selection_status` to `SELECTED` only in the same reviewed change
   that supplies all required identities.

`IsaacSimToolchainLock.load(...)` rejects the repository placeholder, partial
selections, unreviewed licensing, invalid digests, added fields, or any attempt
to add hardware authority.

## Next implementation boundary

The real adapter may begin only after the exact lock is selected. Its first
operation is asset import and kinematic parity (WP1), not trajectory execution:

1. start the locked application in standalone/headless mode;
2. confirm the live version and enabled extensions against the lock;
3. import the governed RoArm-M3 source;
4. emit the complete joint/link/axis/unit mapping report;
5. run the fixed FK parity corpus; and
6. stop without creating controller commands or hardware access.

See the full [integration plan](../../docs/ISAAC_SIM_INTEGRATION_PLAN.md) for
work packages, acceptance gates, ownership, evidence, and limitations.

