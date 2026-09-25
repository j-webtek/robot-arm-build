# Dedicated micro transport and deadline runner

Implemented:

- `providers/windows/micro_native_transport.py`: separate exact-binding HTTP
  transport with a one-use native claim, durable send-intent record, pinned-device
  checks, and baseline expiry rechecked after persistence.
- `application/micro_hardware_runner.py`: injected-I/O one-command orchestration,
  actual clock/deadline polling interface, endpoint verification, passive-hold
  verification and export handling. No default transport or automatic invocation.

**140 focused tests passed**, including existing native discrete sender regression
tests. New native tests used fake sockets only. No real arm commands were sent.

## Dispatch and observation behavior

The exact new binding requires a staged admission and continuous cooperative
session. It consumes the session boundary once, verifies the attempt/command
association, persists an exclusive native-send record, and rechecks identity and
freshness before handing bytes to the connection. Failure leaves the attempt
consumed. The connection also checks its absolute HTTP deadline and cancellation.

The old native sender still rejects this binding type. Its admission and >0.5-degree
movement guard were not changed. HTTP receipts, including empty successful bodies,
are retained as receipts only, not endpoint evidence. Original response bytes and
hashes are kept when a receipt is accepted; malformed bodies reject continuation.

The new runner uses an 800-ms command I/O budget, 150-ms observation quiet period,
at most one-second inter-feedback gaps and ten-second endpoint budget from dispatch.
Every feedback request receives an absolute deadline. The adapter enforces it;
the runner additionally checks completion time and pinned identity. No read starts
at/after the active deadline. A separate original-body reviewer evaluates settling.
Only a settled capture proceeds to the injected passive-hold provider. Failed or
changed holds do not qualify the experiment. Export is attempted for failed runs,
and export failure is returned without claiming diagnostics were saved.

## Tested failures

Unconsumed/duplicate binding, wrong identity, expiry during durable write, missing
receipt, malformed receipt, late/corrupt feedback, incomplete hold, cancellation,
export failure, and reuse of a consumed admission. Every path avoids automatic
retry, return or another command. Stable-but-unchanged remains an experiment
classification, not a claim of desired accuracy or physical movement.

## Not yet enabled

The components are deliberately **not registered as a live wizard action**.
Their implementation is not hardware qualification. Tests inject synthetic
predecessor fixtures and clocks; real continuous-session predecessor ownership
has not yet been exercised through this new transport.

Next: create the commissioning coordinator that owns the real Windows lease across
one new predecessor trial, its hold/export, a fresh baseline and—only if the
specified out-of-band starting condition is met—one micro attempt. If the new
predecessor is already in band, stop with “no correction needed,” not a retry.
Use the existing bounded observation provider for the hold and the wizard's
retained-result/export system. Add preview/cancellation/result ownership tests
before exposing that coordinator as an explicit live action.

The cooperative mutex cannot exclude web or SDK clients on other computers.
The coordinator must make that exclusive-controller assumption explicit instead
of claiming it has been proven by these components. Existing old exports alone
cannot be used to invoke a new native micro-command.
