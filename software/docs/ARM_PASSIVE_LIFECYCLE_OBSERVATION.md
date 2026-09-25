# Passive serial observation: lifecycle implementation checkpoint

Date: 2026-09-12. Parent:
[arm integration plan](ARM_WIZARD_IMPLEMENTATION_PLAN.md), A3.

## What changed

`providers/windows/passive_serial_observation.py` now executes the existing
`NonPurgingSerialConnection` open/configure/readback/read/close implementation
against its sealed hardware-incapable Win32 provider. This differs from the
existing contained IPC fixture, which constructs synthetic lifecycle results
without exercising those methods. Both remain explicitly synthetic.

The routine accepts only a rehearsal request, synthetic reviewed binding, exact
memory provider and cancellation event. Physical requests/native providers are
rejected before open. It does not change any native release hold, register a
physical worker or authorize a serial endpoint.

## Behavior

1. Validate exact inputs and remaining request lifetime before constructing the
   connection. Pre-cancellation performs no API calls.
2. Attempt one open using existing exclusive-open/settings/readback code.
3. Observe for four seconds within the contract's five-second upper bound.
   Poll at up to 10 ms intervals while quiet; read available input in at most
   1 KiB chunks with at most 100 ms per-read allowance. Retain at most 64 KiB.
4. Apply a separate 1,024-poll bound so modeled or nonadvancing time cannot make
   the loop unbounded. An exhausted quota is incomplete, never successful.
5. Preserve exact startup bytes and late cancellation-completed read bytes.
   Keep unread counts when observed; use unknown when accounting cannot be
   established. Never purge input or send a feedback query to solicit data.
6. Attempt cleanup in `finally`; retain unresolved handles/pending I/O, primary
   failure and cleanup failure separately through the existing lifecycle report.
7. Encode the result with the exact-request passive result codec. Return its
   summary alongside the detailed lifecycle. An opened port whose configuration
   failed is not mislabeled as never opened.

Four seconds is an implementation observation interval, not a requirement that
firmware emits data or a guarantee of driver responsiveness. Quiet input does
not establish firmware identity, absence of reset, power isolation or readiness.
The five-second/cleanup/parent bounds remain checked by the result summary.
Native open/configuration/close stalls still require external process containment;
this routine's timing alone is not sufficient.

## Verification

**186 selected tests passed in 6.53 seconds** in
`software/runs/pytest-passive-lifecycle-20260912-02`.

Coverage includes nominal quiet/banner/full-buffer observation, overflow,
open/event/configuration/read/close failures, readback mismatches, stuck pending
read, late completed read preservation, pre-cancellation, exhausted poll quota,
expired request and rejection of physical inputs. Existing backend, codecs and
owned-process regressions also passed.

One test used the real monotonic clock for a four-second observation. All device
calls still used the memory provider. Other timing tests explicitly modeled the
clock. No DLL/device access is allowed by the fixture. No actual arm or camera
was opened and no physical qualification is claimed.

## Next integration boundary

The routine is now available in a **contained wizard rehearsal child** using
`lifecycle-nominal`, `lifecycle-open-failed` and `lifecycle-cleanup-unknown` on the
existing Arm action. The older IPC-only scenarios remain distinct and available.
The smoke script now selects `lifecycle-nominal` explicitly. The dropdown's old
`nominal` default still means the simpler IPC fixture; choose a `lifecycle-` item
to exercise the serial algorithm.

`passive_arm_lifecycle_package.py` reuses the closed existing arm dependency
roster/archive builder, adding only the passive request/result and observation
modules. No historical package roster is mutated. Namespace stubs suppress
application initialization. The fixed child runs under `-I -S`; the parent
checks the archive against the current exact source roster and pins the child,
archive and interpreter through the existing process owner. A supplied archive
digest alone is not accepted as source approval.

The lifecycle scenarios have an eight-second process budget, two-second cleanup
budget and the existing 128 KiB output bound. Source/runtime/attempt binding,
one attempt per launch, durable diagnostic checkpoint, raw-output export and
physical-mode exclusion remain in place. Known API cleanup failure is retained
even when the process exits cleanly. A killed/timed-out process cannot report
device cleanup merely because its process tree exited.

No routine runs on a physical device or in the UI process. Original physical
entry references, durable original intent/outcome, capable registration and
received-unit qualification remain unfinished. Do not remove the native-provider
rejection to shortcut those requirements.

### Contained wizard verification

- **361 selected tests passed in 45.39 seconds**, retained at
  `software/runs/pytest-passive-lifecycle-child-20260912-03`.
- Real contained-child scenarios exercised through public wizard actions and
  export/checkpoint readback. Includes process timeout, altered archive rejection,
  arbitrary digest rejection and existing backend/codec/UI/service regressions.
- Actual application smoke: `REHEARSAL_AND_EXPORT_VERIFIED`, operation
  `operation-625b16c452bd4ce09042849e2f54809c`.
- Source: `fff537cfae9b9aeef38ae4ac70a78f268d8a7babdb5276ec132455ec12265b14`.
- Export:
  `software/runs/wizard-exports/wizard-20260912T181854094263Z-4c758e97ce224006b8da1137b218efaf`.
- Attached result independently inspected for lifecycle/API call evidence.
  Process execution and clock are real; all serial observations remain synthetic.
  No attached arm/camera was opened and no hardware commands were sent.
