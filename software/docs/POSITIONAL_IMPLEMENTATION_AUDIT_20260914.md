# Positional implementation audit — 2026-09-14 UTC

Overall result: **incomplete**. The goal remains the original attended and
unattended campaign release, not merely simulation completion. This is a scoped
audit, not a claim that every repository test or all plan requirements passed.

## Update after correction-chain HTTP/export validation

The historical table below predates subsequent live repeatability tests and
correction implementation. Current evidence adds:

- Matched zero from above/below and repeated +4/downward-zero tests, documented
  with operation IDs in `WRIST_ACCURACY_INTERNAL_FINDINGS_20260914.md`.
  Directional endpoint bias is repeatable; physical mechanical cause unproven.
- Correction proposal, fresh-start preview, signed review, durable consumption,
  raw nominal-endpoint reconstruction and exclusive publication implemented.
- Closed wizard correction rehearsal now exercises that entire synthetic chain.
  Public HTTP operation `operation-6b2c9c058e7442d98243959b73ad4b15` settled in the
  constant-bias model. `operation-064820c151714095b5460a3c4ef99f9a` and
  `operation-a009c65b3bc14643926ec394f04cdfea` preserved excursion faults.
  Wrong approach/stale baseline held before consumption.
- Export `wizard-20260914T103241388499Z-f22ae15dc56d4f91a729b8f0d8c170de` verified;
  manifest `92399221fb3494b6b5fcf768e406350f47eae1750f8f763541a83c01fb0c8027`.
  Each completed scenario retained ten originals. Reconstructing all three
  from exported bytes reproduced the exact endpoint status. No device access.
- Re-executed the real registered positional worker suite after this integration:
  **283 passed in 22.59 seconds**, 16 closed test files, zero device opens,
  serial writes, power events, motion commands or contact commands. This remains
  a scoped suite, not an all-repository pass or physical qualification.

### Native correction critical path (not another release claim)

1. Separate pre-open reviewed context from exact post-acquisition dispatch
   binding. Current correction review signs an exact normalized baseline; it
   cannot be silently reused with a new owned capture. Existing absolute reader
   accepts only AbsoluteWristIntent, and its permit is deliberately incompatible.
2. Compose pinned current USB/COM/source validation, bounded serial ownership
   and raw baseline acquisition using the existing reviewed Windows lifecycle.
3. Recompute the correction within the reviewed starting-pose, target, direction,
   speed and delta envelope; bind its newly acquired raw evidence explicitly.
   Seal/consume exactly one command after current checks; no widened old permit.
4. Couple consumed receipt to actual command byte accounting and owned worker
   result/cleanup. Current publication proves file consistency, not this coupling.
5. Integrate correction-specific prepare/execute/result/export in physical mode,
   test failure paths without hardware, then one bounded live experiment.
6. Only afterward assess repeatability/optimization and the separate multi-leg
   stop/freshness/clearance requirements. No unattended release follows from a
   successful correction or simulation.

| Work package | Authoritative evidence inspected | Assessment |
|---|---|---|
| P1 contracts and diagnostics | `motion/positional_campaign.py`, absolute wrist contracts, saved absolute attempts | Absolute targets and bounded compilation implemented. Same-target opposite-approach diagnostic unfinished; positioning attempt missed. General path and configuration/expiry coverage not fully audited here. |
| P2 simulated sequencing | `positional_campaign_rehearsal.py`, journal/admission tests, actual wizard suite export | Finite simulation, commit-before-next-leg and fault holds implemented. Full P2 boundary coverage still requires item-by-item reconciliation. |
| P3 native lifecycle/stop | `positional_owned_campaign.py`, native facade rejection tests, pinned stop-source review | Native multi-leg path deliberately unreleased. Synthetic permits cannot establish native ownership, physical stop or host-loss safety. |
| P4 wizard and attended release | Public single-trial operations, result retention, simulation test/export workflow | Machine endpoint reporting/export demonstrated. Qualified two-leg attended native campaign NOT demonstrated; full browser failure coverage not audited here. |
| P5 optimization | Three absolute trial reports and trace diagnostics | Preliminary differing-target samples, not same-route repeated trials or a speed/load matrix. No shortened-tail qualification or unattended pilot. |
| Section 10 | Source freshness review and observed-field inventory; no release record | All physical release gates remain open pending actual evidence. Standing supervision does not satisfy unattended separation/watchdog requirements. |

## Exact live evidence

All listed commands were single wrist-pitch moves at spd 20, acc 1, with a
0.5-degree arrival tolerance. Angles are controller reports, not independently
measured physical accuracy. Original report files are under
`software/runs/wizard-exports/`, with names ending `-absolute-wrist-report.json`.

| Attempt | Target | Reported final | Endpoint |
|---|---:|---:|---|
| operation-f05531b8aa8e4f969af7309d8a26d115 | 4 deg | 3.7793 deg | REPORTED_SETTLED; initial UI retention error subsequently diagnosed/fixed |
| operation-b9fae47e71b8403ca09a916f85f4dcca | 0 deg | 0.9668 deg | TARGET_MISSED; reporting fix verified live |
| operation-1f968b0dfb5d44fa8be8b76c79fcb26a | -4 deg | -3.2520 deg | TARGET_MISSED; trace diagnostic verified live; follow-up withheld |

## Verification scope

- Actual rehearsal wizard operation `operation-6a195c2ee2774e8eba09cd34c0a9f174`:
  205 tests, nine registered files, zero hardware access. Export
  `wizard-20260914T040002496380Z-2eda650ba63a48b39a797498d5113a81` verified.
- Selected absolute integration regression: 308 passed, 17,301 deselected.
  This cannot support an all-repository claim.
- Freshness proposal: 18 synthetic tests. No installed device supports this
  format by evidence currently available; consistent modeled reports grant no
  physical freshness or native execution authority.

## Critical path, without bypasses

1. Determine installed firmware/diagnostic capability through a supported
   read-only method or vendor clarification. Reference archive identity is not
   installed binary identity. Prepare evidence for review; do not guess commands.
2. Resolve repeated reported endpoint misses. Do not use successful transport,
   longer plateaus, new wizard sessions or a wider tolerance as a substitute.
3. Qualify stop/host-loss behavior for already-issued goals and gravity effects.
   This requires physical evidence, not a software queue stop claim.
4. Integrate qualified native ownership and fresh feedback into the two-leg
   campaign, then validate through the wizard with faults and exports.
5. Expand joint/path/speed cells only after that profile passes; complete all
   unattended release gates before an unattended pilot.

Firmware flashing, PID changes, servo-register writes and automatic compensation
are not approved by this audit. Further software models alone cannot close the
installed-firmware and physical-stop evidence gaps.
