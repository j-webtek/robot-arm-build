# Actual-source wizard preflight and scoped native rehearsal

Date: 2026-09-08. Status: **implemented and tested, no physical connection release**.
This is the next checkpoint for the [connection plan](CAMERA_ARM_CONNECTION_INTEGRATION_PLAN.md)
and [developer playbook](CAMERA_ARM_DEVELOPER_PLAYBOOK.md). It supersedes the
[previous checkpoint](NATIVE_CONNECTION_IMPLEMENTATION_CHECKPOINT.md) only for
the joins described here. Freeze 011 and controlled hardware/configuration are unchanged.

## Operator workflow

From the workspace root, with the existing development environment:

```powershell
.\start-rocell-wizard.ps1 -Mode physical
```

1. On **Overview**, preview **Check actual source files (no devices)**. Supply
   a short operator identifier. The preview names the new assigned session
   directory and describes the exact file-only action.
2. Confirm. The action creates a separate Windows/NTFS-qualified M1 store,
   immutable `PHYSICAL_DIAGNOSTIC` header and one consumed file-check permit.
   It does not enumerate, connect, reset or initialize either device.
3. Review **Actual source preflight** and the completed operation. A coherent
   result means the reported local files agree—not that hardware was received,
   power is off, a camera is connected, or a physical stage passed.
4. On **Diagnostics & exports**, preview/execute **Export diagnostic report**.
   The user-selected default is `software/runs/wizard-exports`. Each export is
   a new directory; existing reports are not overwritten. Its attachment includes
   the complete source report, attempt summary, file hashes and physical holds.
5. On failure, export and preserve the original store. Fix the reported cause
   and start a new explicit wizard launch. There is no automatic retry, reopen,
   migration, permit replay or uncertainty clearing.

Operational records stay in `software/runs/physical-source-preflight/<wizard-launch-id>`.
Diagnostic export does **not** copy live M1 ledgers and is not a commissioning
bundle. Never use an export or a successful file check as motion/contact authority.

Default rehearsal launch is unchanged. The new action is physical-diagnostic
mode only, but its effect is strictly `NO_DEVICE_IO`. All fifteen physical stages
stay pending; the durable first stage stays `WAITING_OPERATOR`. Power is `UNKNOWN`.

## Implementation map

| Component | Responsibility | Boundary |
| --- | --- | --- |
| `wizard_actions.py`, `arrival_wizard_service.py`, `ui/static/app.js` | Preview/execute; cached progress/report; completion-log/source publication; assigned-folder export | No browser path, provider, command, permission or stage-PASS input |
| `physical_source_preflight_service.py` | Launch-owned session; actual source-derived facts; M1 initialization; coordinator dispatch; full read-back | Constructor/status inert; no relabeling or promotion |
| `physical_source_preflight.py` | Bounded 59-file closure, semantic foundation validation, separate native build comparisons, immutable report | No synthetic bootstrap/image fallback, inventory, helper execution or hardware claims |
| `commissioning_physical_persistence.py` / M1 runtime | Distinct source/cell/session/record domain, real leases, full retained bytes, audited outcomes | `PHYSICAL_DIAGNOSTIC_NO_DEVICE_IO`; no device leases or energy envelope |
| Coordinator / `consumed_commissioning_scope.py` | One-use permit, scoped acknowledgement, repeated read-only continuity checks | Original leases/deadline/cancellation; no renewal; failure bytes do not grant known completion |
| `incapable_native_admission_campaign.py` | Application/runner join through actual qualified M1 | Separate rehearsal, fixed incapable endpoint/child; not physical camera-stage evidence |
| Owned native runner / evidence | Exact handshake, owned Job/process, independent cleanup, bounded raw evidence and pure verification | Physical dispatch unconditionally held; test child contains no camera/COM/MF implementation |

Contracts: [source worker](PHYSICAL_SOURCE_PREFLIGHT_API.md),
[physical M1 storage](M1_PHYSICAL_DIAGNOSTIC_PREFLIGHT.md),
[native runner](OWNED_NATIVE_CAMERA_RUNNER.md),
[scoped incapable campaign](INCAPABLE_NATIVE_ADMISSION_CAMPAIGN.md).

## Failure and publication rules

- Startup, page visits, polling and preview never create this store or dispatch
  its worker. Only execution reserves the one launch attempt.
- Cancellation is checked before new storage mutations and during file work.
  The 20-second worker timeout is cooperative, not a preemptive filesystem
  supervisor. Diagnostic Stop is not an arm E-stop.
- Full bounded evidence is retained before known sealing, then read back with
  exact M1 evidence hash, source, permit and worker verification.
- Late source drift, cancellation or completion-log failure cannot publish a
  coherent report as current. Already read-verified reports remain historical
  evidence, including in failed-action exports.
- Failed scoped revalidation may retain returned bounded failure bytes while
  acknowledged storage ownership remains valid. It cannot grant known acceptance;
  the scope stays revoked and uncertainty is retained.
- Missing files produce a held report naming a fixed relative source. A local
  development manifest/binary match is not release signing, reproducible-build
  proof, installed-driver qualification or permission to execute a helper.

The software fingerprint covers Python/web source, software JSON, pyproject and
`rocell.ps1`; it excludes native/hardware trees, dependencies, docs/tests and runs.
The worker separately lists checked native/hardware files. Neither scope covers
the entire computer. Windows pins protect the fixed closure; broader source
before/after hashes do not establish hostile-writer isolation.

## Executed verification

Current software fingerprint:
`7a1eb515d06d60019264314abd2742e475f0479a00e471e0d5a51b8adcb60b6d`.

- Broad non-slow integration selection: **2,693 passed, 2,962 deselected**,
  192.23 seconds. This is not the entire repository suite.
- Follow-up UI/CLI/scoped/core: **144 passed**, 2.93 seconds.
- Actual source service/public export and late-failure tests: **2 passed**,
  47.43 seconds, using isolated actual-source copies and qualified NTFS.
  Three additional inert/cancel tests passed.
- Storage: **40 combined physical and legacy M1 tests passed**, 204.75 seconds.
- New source worker: **49 passed**. New UI/service presentation: **30 passed**.
- Native runner related lane: **195 passed**. Scoped application bridge:
  **6 passed**, rerun 15.86 seconds, including actual M1 → scoped checks → fixed
  incapable C++ child → full retained evidence. Smaller selections overlap;
  do not add them as unique totals.
- Mypy passed for root and agent integration modules. Black and JS syntax passed.

### Live local wizard and chosen-folder export

The actual workspace action ran through the live loopback HTTP preview/execute
API. Browser startup/accessibility content was inspected; no new screenshot-based
pixel/layout certification is claimed.

- Launch: `wizard-23b848231db24ee19f4c729ccc3152e3`.
- Session: `physical-diagnostic-08456fedc97c4d0ab4a165553c515ad5`.
- Attempt: `attempt-675ae0cde2b24819874ecd70fc6ec6b2`, `SEALED_KNOWN`.
- Six coherent checks; 59 files / 1,504,683 logical source bytes.
- Retained source report: 16,785 bytes, SHA-256
  `239c3f37f7b3e85839a0827c1b8621a11b5db550867ba0e1935caaa2c6987809`.
- Both hardware states `NOT_CONNECTED`; all physical stages pending;
  device counts zero, power `UNKNOWN`.
- Export: `software/runs/wizard-exports/wizard-20260908T062325936105Z-63f08be5eb2d4824b49e8847d7f7e64c`.
  Four payload files / 95,765 bytes; diagnostic-verifier manifest hash
  `7cc9075315d2dea7faea97f1b56bf8468029d075a0cc6d1b64bf29af19b9feab`.
  Source-result attachment SHA-256
  `4f737869a9dffd5284759e4c30ae0bbf70e317157bcb425658696194fa81ec45`.

Offline no-dependency wheel:
`software/runs/wizard-package-check-7a1eb515/rocell-0.1.0-py3-none-any.whl`,
1,667,281 bytes, SHA-256
`44b9c8fbfa328922510d3f1e8b0173ccf41a222371fc4b3260ab960e147590e1`.
This is a packaging smoke artifact, not a standalone installed-device release;
the source/native/configuration tree is still required.
Eight relevant wheel entries (source service/worker, physical persistence, scope,
incapable bridge, native runner/evidence and browser JavaScript) were byte-compared
against the checkout and matched. The assigned export was independently reverified.

## Required next work—not completed here

1. Close independently reviewed physical provider/driver admission and historical
   metadata-source drift. Do not refresh hashes merely to approve the old catalog.
   Add real camera probe and capture only through qualified ownership/evidence.
2. Finish contained non-purging serial IPC and physical arm coordinator/evidence
   integration. Preserve the exact one-request feedback allowlist; startup must
   not home, torque-enable or issue motion.
3. Add received-unit identity, actual power observations and progressive installed
   optics/board/reference qualification. Purchased profiles are not measured units.
4. Finish the remaining rehearsal stages and separately authorized physical
   keyboard/Android execution UI. This source session cannot authorize either task.

No physical helper, serial endpoint, firmware, driver installation, arm power,
motion or contact was exercised. No Git repository is present; these are saved
workspace files, not a Git commit.
