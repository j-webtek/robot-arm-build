# Storage admission performance checkpoint

Date: 2026-09-09. This supports the [onboarding completion matrix](ONBOARDING_APPLICATION_COMPLETION_MATRIX.md),
not a camera/arm release. Full public AFTER_REBOOT acceptance subsequently
passed in fresh run 07; received-hardware performance remains unverified.

## Change and boundaries

`require_effect_durability_pair` checks the qualification anchor and startup
receipt against **one fresh root/volume observation per gate**. The existing
single-receipt verifier supplies that observation, including canonical safe
root, current source, NTFS/fixed-volume identity and qualification checks. The
companion must independently match the source, root and current volume and be
qualified. The publication adapter still compares the complete stable check
identity and rejects a startup receipt older than its anchor.

Previously the adapter sampled the same root and volume twice in succession.
The new contract is explicitly one coherent point-in-time sample, not continuous
filesystem monitoring. A change occurring only between those former two samples
is not equivalent temporal coverage. Every subsequent gate samples afresh;
there is no cross-call approval cache, supplied observation or skipped original
audit. Existing before/after mutation guards, path/link checks, opened-handle
checks, durable writes, independent ledgers and evidence reads remain in place.

The 30-second permit, 20-second lifecycle reserve, five-second READY limit and
outer action deadline are unchanged. A depleted window still refuses dispatch
and retains its failure; a consumed attempt is never renewed or replayed.

Source fingerprint after the change:
`b9170ade0d1e77d7bd5eb22e52045412af9cb32841b20b3eef5238368780e32e`.
No old store was rebound to this source.

## Measured evidence

Both profiles constructed a fresh NTFS store with 64 original references and
three prior campaigns. All device facts, stage reviews and in-process workers
were explicitly modeled. Actual leases, storage qualification, reads, audits,
publication and clocks ran. Only the fourth `core.execute` was profiled.

| Measurement | Before | After |
| --- | ---: | ---: |
| Profiled execute elapsed | 12.770 s | 10.445 s |
| Report-pair gates | 1,069 | 1,069 |
| Cumulative time in those gates | 2.957 s | 1.435 s |
| V2 snapshot loads | 17 | 17 |
| Evidence-directory validations | 1,088 | 1,088 |
| Original regular-file reads | 3,546 | 3,546 |
| Family audits | 6 | 6 |

The approximately 18% reduction is a two-run profiling observation, not a
hard real-time guarantee or a passing public onboarding workflow. Complete
fixture runs passed in 117.63 s and 93.46 s. A newly published original still
changed the admission inventory and challenge after each profiled campaign.

Evidence under `.codex-preserved/`:

- `usb-history-admission-profile-20260909-01` and `-02`: fresh stores and
  `test_fresh_history_admission_p0/admission-execution.pstats`; corresponding
  `-results.xml` files are retained.
- `durability-pair-20260909-01`: **49 passed in 6.16 s**, covering both receipts,
  uncached observation, changed volume/path, qualification failure, stable
  anchor/timestamp rules and no publication after a failed gate.
- `durability-pair-admission-regression-20260909-01`: **107 passed in 54.87 s**.
  Includes original-admission freshness, changed-inventory rejection, permit
  issuance/expiry, lifecycle and cleanup faults, an actual fixed incapable
  child, M1 storage and export verification. This preceded the retained-history
  parameter added to the owned-child test below.
- `durability-pair-component-regression-20260909-01`: **21 passed in 0.51 s**,
  preserving fresh component/link/hardlink/error checks.

Black and scoped mypy passed. Both launcher `-Check` modes returned
`READY_FOR_DIAGNOSTICS`, camera/arm `NOT_CONNECTED`, zero operations/events,
false physical authority and the confirmed export directory:
`C:\Users\Jack\Desktop\robot-arm-build\software\runs\wizard-exports`.

## Repeatable heavier worker check

`test_commissioning_usb_identity_owned_m1.py` now has fresh and retained-history
parameters. The latter seeds 64 explicitly modeled file-only originals, then
executes three prior campaigns and a fourth new campaign using the separately
linked **incapable** child. It checks all five real scope boundaries, original
result/evidence readback, cleanup, accounting, exact permit reuse without new
dispatch and retained global history. Native USB/camera/serial access is denied.
Neither the modeled source binding nor the fake child's descriptors qualify
hardware. This is a lower-level test, not a replacement for public UI acceptance.

The first run passed the fresh case but failed in the new fixture before any
history publication because it referenced a nonexistent `snapshot.current_stage`
property. The fixture now uses the existing explicit camera-identity stage;
the failed directory is preserved. Fresh rerun
`durability-pair-owned-history-20260909-02` **passed both cases in 114.23 s**.
The fourth campaign in the heavier case performed all five scope checks in
0.922 / 0.953 / 0.828 / 0.844 / 0.844 seconds. Its fixed incapable child was
created, released and cleaned up; runner elapsed was 4.656 s with 20.328 s
remaining at completion. Those are observed fake-child timings, not real
descriptor-query duration or hardware qualification. All 20 campaign events
remained available and a repeated execute returned the same result without
another dispatch.

Run the test with a **new, unused** temporary directory, because pytest clears
an existing `--basetemp`:

```powershell
.\.venv\Scripts\python.exe -m pytest `
  software/tests/unit/test_commissioning_usb_identity_owned_m1.py `
  -q -s -x --tb=short --basetemp=.codex-preserved/YOUR-NEW-RUN-NAME
```

## Full public follow-up and remaining work

Full public run 06 remains a preserved failure: the final USB campaign was
refused with 18.578 seconds against a 20-second reserve, and quarantine stayed
latched. Its completed diagnostic action did not establish nominal timing.
Do not reuse that store. Fresh run 07 rebuilt the complete prefix and passed
all actions, complete export/restore and fresh original reopening without
replay. See the [reboot work order](USB_AFTER_REBOOT_IMPLEMENTATION.md) for the
full evidence and the preserved failure exports.

Full public run 07 **passed in 1,735.50 s**, using fresh directory
`reboot-root-public-20260909-07`,
the source above and unchanged public test SHA-256
`0726b75836df94fd23518f37ce4c80f46279aae152df591cacb55beb489649d3`.
The process is closed. Its final original campaign was `SEALED_KNOWN` with
quarantine false and all reboot checks passing. Post-pin lifetime was 20.782 s,
only 0.782 s above the unchanged reserve. The 182.734-s public collect timing
includes dispatch/completion/idempotent-return work; it is not an inner-worker
deadline measurement. This one pass does not establish reliable timing on every
host. Final series review, stage-5 entry and live camera/arm paths remain open.
