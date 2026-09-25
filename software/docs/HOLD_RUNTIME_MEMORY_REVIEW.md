# Hold runtime memory review — 2026-09-18

Compile-only ESP32 review; no linked firmware image, device access or deployment.

## Evidence and measured sizes

`hold_memory_probe.cpp` instantiates the integrated runtime against declaration-only
bus/clock/crypto adapters and `EvidenceStore<12,4096>`. The pinned
`esp-x32/2302/bin/xtensa-esp32-elf-g++` compiled it with `-std=gnu++17 -Os
-fstack-usage`; target `nm -S` reports these object sizes:

| Component | Bytes |
| --- | ---: |
| One raw whole-arm snapshot | 1,720 |
| Staged owner, eight snapshots/two actions | 14,016 |
| Publisher | 4,368 |
| Admission | 1,808 |
| Integrated runtime | 27,168 |
| 12-slot, 4096-byte evidence store | 49,352 |
| Runtime plus store | 76,520 |

The largest emitted individual stack frame is 336 bytes (`start`). This excludes
full nested call chains, concrete crypto/serial/network adapters, interrupt/task
overhead and runtime JSON heap allocations. It is NOT a measured stack high-water
mark or evidence of sufficient live free heap. Probe globals represent each size
independently and must never be linked into production; adding all probe symbols
would double-count components.

Reproduce with:

```powershell
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_hold_memory_probe.py -q
```

The test cross-compiles without linking/uploading, checks combined static object
budget <=80,000 bytes, owner <=16,000 bytes and individual reported frames <=512.
An initial manual compile failed to resolve a relative include argument; the
reproducible test uses absolute include/source paths and passes.

## Store compatibility

Installed r6 uses 16 slots of 2304 bytes. Do not reuse that slot size for hold
records. A separately instantiated `EvidenceStore<12,4096>` works in the integrated
native tests without changing the generic store's existing bounds. A full scan
with maximum-length identity strings, near-INT64_MAX timestamps and both hashes
also serializes into a 4096-byte slot in the dedicated test.

The runtime's 4608-byte enrichment scratch remains larger than the store slot;
the store still rejects any oversized record and that failure stops progression.
No eviction or capacity expansion occurs during a session.

## Deployment implications and remaining work

Concrete hold-only r7 compile (2026-09-18): program usage 1,064,341 bytes;
static RAM 57,232 bytes. Full build export:
`wizard-20260918T174440380311Z-592ae9d2f2484a13b103cc8e8b954407`.
The reported 270,448-byte linker remainder does not subtract live Wi-Fi, JSON,
crypto, network/request/evidence allocations or task stacks. It is not measured
free heap. Board response scratch (4608 bytes) and policy scratch (2048 bytes)
are static, not loop-stack allocations. Only the hold runtime is instantiated;
the prior startup runtime is not simultaneously constructed. No live high-water
or largest-free-block measurements have been collected for r7.

- Keep runtime/store off the control task stack; use one bounded, checked
  allocation after validated policy and before enabling a listener.
- Do not allocate the old startup runtime and new hold runtime concurrently
  without a complete peak-memory review. Prefer one selected diagnostic mode.
- Target firmware integration must measure free heap/largest block and stack
  high-water marks, and account for network, crypto, JSON and request buffers.
- Allocation failure must remain terminal before servo activity; test it in the
  eventual configured-runtime wrapper.
- No memory measurement here authorizes a firmware install or servo engagement.
