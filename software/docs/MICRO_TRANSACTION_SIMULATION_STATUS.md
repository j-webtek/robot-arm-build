# Integrated micro-transaction simulation

Implemented `application/micro_transaction_simulation.py` with tests in
`tests/unit/test_micro_transaction_simulation.py`. The staged admission exposes
a detached snapshot of its persisted context for offline composition.

## What is integrated

1. Validate scenario timing and obtain the staged admission context.
2. Consume the real durable staged intent exactly once.
3. Recheck freshness at the virtual send boundary after simulated replay/write
   latency. An admission can expire while processing; consumption is not enough.
4. Record at most one virtual command attempt and a bounded synthetic receipt.
5. Replay original-format synthetic feedback through the micro endpoint reviewer.
6. For a settled result only, verify the synthetic passive hold's original bodies,
   ordering, response gaps, duration and unchanged six-joint endpoint.
7. Attempt export of a detached report on success or failure. Export failure
   leaves an in-memory STOPPED result and does not claim saved diagnostics.

There is deliberately no sender callback, network connection or wizard/native
registration. Only export is injected. `native_sends` is always zero. Synthetic
traces and virtual timestamps are not presented as hardware evidence. Predecessor
validation is stubbed in transaction unit tests; the staged durable latch itself,
raw-body reviewer and endpoint verifier execute normally.

## Outcomes and tests

Coverage includes nominal completion, duplicate invocation, expiry during admission
processing, send uncertainty, slow receipt, missing/failed/corrupted feedback,
incomplete/changed hold, cancellation, admission persistence failure, export
failure, process mismatch and unchanged endpoint. No fault triggers retry or return.

`EXPERIMENT_VERIFIED` means the endpoint and hold are documented, not that accuracy
improved. An unchanged settled result can finish with that status while
`desired_band_met=false`; its classification remains UNCHANGED_OR_SUBRESOLUTION.
Export receives the pre-export report (`export_succeeded=false`); the returned
result alone records successful completion of the export callback. An export
must not contain a self-attestation that its own write has already succeeded.

## Remaining work before live use

The simulation is not a production runner: it consumes supplied traces rather
than polling under an enforced real-time deadline, and it does not establish
exclusive control of the physical arm. Future native integration must bind the
predecessor, fresh baseline, command and actual send/receipt times under a
continuous same-session controller; enforce deadlines at blocking I/O; consume
one-use authority at the native boundary; and use real cancellation, passive hold
and durable export behavior. The participating-process mutex alone does not
exclude external clients. These limitations remain explicit.

No live admission guard or compensation setting was modified. Do not connect
this simulation runner to a transport or treat its scenario parameters as permits.

## Reproduce offline

```powershell
.venv\Scripts\python.exe -m pytest software/tests/unit/test_micro_transaction_simulation.py software/tests/unit/test_micro_command_admission.py software/tests/unit/test_micro_endpoint.py software/tests/unit/test_micro_endpoint_review.py -q
```
