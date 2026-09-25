# Campaign HTTP failure and timing tests

2026-09-20. Localhost-only tests with ephemeral ports and a synthetic test key.
No controller address, device connection, firmware change or physical movement.

## What was tested

The existing `CharacterizationHTTP` adapter runs through real TCP sockets against
a local server. The server verifies the request signature and records a POST
before deliberately losing or damaging its acknowledgement. This tests uncertain
delivery, not merely rejection before sending.

| Scenario | Observed client result |
| --- | --- |
| Server closes after receiving POST | Session stops; no resend |
| Response body truncated | Session stops; no resend |
| Response headers arrive after deadline | Session stops; no resend |
| Response body arrives after deadline | Session stops; no resend |
| Signed body is altered | Authentication fails; session stops |
| Header and body delays cumulatively exceed budget | Total deadline enforced; no reset of budget per read |
| Valid reply delayed 350 ms, budget 2 s | Accepted; next request uses next sequence |

Each failure case checks that a repeated POST and a different follow-on GET are
both rejected locally: the server receives exactly one request. This does not
mean an arm would not have executed an uncertain command; it means this client
does not issue another command based on an unverified response.

Existing tests additionally cover duplicate/missing auth headers, redirect,
tampering, request overlap, replay, incorrect sequence and authenticated error
status. Production transport code required no change in this increment.

## Validation

28 tests passed across loopback failures, existing HTTP adapter/session tests and
native composition campaigns. Reproduce from `software`:

```powershell
..\.venv\Scripts\python.exe -m pytest tests/unit/test_characterization_http_failures.py tests/unit/test_characterization_http.py tests/unit/test_characterization_http_session.py tests/unit/test_characterization_composition.py -q
```

Timeouts in negative tests are deliberately short test inputs, not new operating
requirements. The accepted 350 ms response explicitly checks that no arbitrary
250 ms limit is introduced. Scheduling on a heavily loaded host can affect timing
tests; failures must be inspected, not treated as physical-arm findings.

## Combined integration checkpoint

The native campaign route bridge and real-socket transport are now connected by
`tests/unit/test_characterization_socket_campaign.py`. Both legacy and matched
12-leg campaigns pass through the production HTTP client, authenticated native
routes, chunk verification, verified disk exports and signed receipts. The native
controller uses a fake servo bus. Three integrated tests pass.

The receipt-acknowledgement-loss test exposes an important limitation: after the
controller accepts the first receipt, losing its HTTP reply stops the host, but
the controller can execute the second admitted leg. The test observes two fake-bus
writes and only one exported result. A host session fault is NOT a controller
stop. The receipt is continuation permission, not merely an archival confirmation.

## Next release requirement

Represent this state explicitly as delivery uncertain / possible next-leg motion.
Do not resend the receipt or resume from the host's last acknowledged endpoint.
Design authenticated read-only reconciliation of controller campaign identity,
leg, phase and retained evidence before any fresh admission. Keep the finite
controller-side export barrier: no further receipt means no further progression
beyond the already permitted leg. Test this bound and reconciliation failure cases
before exposing the combined workflow as a live wizard action.

These tests do not measure real Wi-Fi latency, controller runtime resources,
servo behavior or physical clearance. No firmware was deployed or arm moved.
