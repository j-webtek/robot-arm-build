# Held-pair ESP32 memory review

## Current compact-store result

With the new explicit network lifecycle, the coordinator is **184 bytes**,
initial graph **21,448 bytes**, and return graph **20,864 bytes** on ESP32. The
graphs include their gate/operation/network and never coexist. Runtime + handoff
+ coordinator + initial graph = **95,608 bytes**. The analogous return graph plus
temporary bridge = **103,668 bytes**. Do not add the separate gates/connection/
listener again. Dynamic Wi-Fi/JSON, GET buffers, allocator overhead and stacks
remain additional and have not been measured on hardware.

The actual `NetworkServer`/`NetworkClient`/`Esp32StartSocket` operation graph now
compiles and measures **19,624 bytes**, including its connection/listener/wrappers.
Use that figure instead of separately summing the probe connection/listener:
runtime + gates + return bridge + concrete network totals **103,396 bytes**.
Dynamic Wi-Fi allocations, JSON temporaries, GET buffers, task stacks and any
live handoff capsule remain additional. This remains a layout calculation only.

The verified hold handoff adds **1,888 bytes** on ESP32. The integrated simulation
now destroys the old authenticated hold runtime and its full evidence store
before pair allocation, keeping only this noncopyable endpoint/identity capsule.
Production must finish hold evidence export before releasing that graph. The
capsule may be freed after pair admission copies its endpoint; retaining it
through return would add its size to the subtotal below.

The later listener compile probe adds **19,440 bytes** for one request connection
and **56 bytes** for its listener. Runtime + both gates + temporary bridge + one
connection/listener totals **103,268 bytes**. This still excludes concrete Wi-Fi
objects, operation/owner wrappers, GET output buffers, JSON heap allocations,
stacks and overlapping hold state. Initial and return connections should not be
retained together; the one-shot lifecycle does not require that duplication.

The authenticated runtime now uses `HeldCompactEvidenceStore`, retaining all
32 raw snapshots in the owner rather than also keeping 34 full JSON buffers.
It retains each record's publication SHA-256 and capture-time reason text, plus
exact terminal JSON. Each read reconstructs JSON from retained raw evidence and
checks the original hash before returning bytes. A mismatch/hash failure latches
a fault. Returned record pointers refer to one scratch buffer and expire on the
next read/publication; callers must copy bytes before another store access.

Actual ESP32 compile-only probe after integration:

| Component | Current bytes | Previous bytes |
| --- | ---: | ---: |
| Complete runtime | 72,088 | 203,152 |
| Evidence store | 8,748 | 139,816 |
| Runtime + initial/return gates + temporary bridge | 83,772 | 214,836 |

Runtime reduction: 131,064 bytes (about 64.5%). Raw sample capacity and endpoint
rules are unchanged. Full-store/compact-store differential tests match exact
bytes for arrival, non-arrival and partial failed acquisition, including later
owner faults and changed snapshot freshness reasons. Hash failure is fail-closed.
The signed runtime lifecycle passes with the compact store. Twenty-five focused
pytest cases pass; the target methods also compile successfully.

This is still not a measured live heap/stack margin. Reconstruction and hashing
add CPU work; target allocation peaks and sampling/HTTP latency must be measured
in a reviewed candidate. No deployment or hardware access occurred. The original
measurements below are retained as the pre-optimization baseline.

## Measured offline, not deployed

The compile-only probe uses the retained r7 `compile_commands.json` and ESP32
Arduino 3.0.7 flags: `esp32:esp32:esp32:PartitionScheme=default,PSRAM=disabled`.
It explicitly instantiates pair-runtime methods against SMS_STS and inspects
object symbol sizes using the target `xtensa-esp32-elf-nm`. It does not link,
flash, reset, open a serial connection or execute any code on the device.

Run from workspace root:

```powershell
& ./software/scripts/measure_held_pair_memory.ps1
```

Each run creates a separate probe object directory without modifying the retained
r7 build. The JSON result includes source/compiler/build-database and diagnostic
header hashes. Probe arrays are layout markers only; never link them into firmware.

## Target ABI results

| Component | Bytes |
| --- | ---: |
| Complete pair runtime (includes store, owner, publisher) | 203,152 |
| Evidence store | 139,816 |
| Pair owner | 57,192 |
| Single-leg owner | 55,336 |
| One raw snapshot | 1,720 |
| Publisher | 4,368 |
| Temporary return bridge | 8,644 |
| Initial authorization gate | 1,808 |
| Return authorization gate | 1,232 |
| Prior hold owner alone | 14,016 |

Do not sum contained components into the runtime a second time. Runtime plus
both gates and temporary bridge totals **214,836 bytes**. If the old hold owner
alone overlaps that peak, the subtotal becomes **228,852 bytes**. An entire old
hold network/evidence runtime would cost more than its owner alone.

This excludes allocator overhead/fragmentation, ArduinoJson allocations, request
buffers, network objects, Wi-Fi/RTOS allocations, stacks, static firmware state,
and any other live allocation. No free-heap or largest-block measurements were
collected on hardware. Target compilation succeeded; deployment fit is UNPROVEN.

Initial measurement object:
`software/.firmware-tools/pair-memory-probe-811415c81a4d45bd988cb38dff847701/held_pair_memory_probe.o`.
Compiler SHA-256:
`ce72b244e5ea864d014163d229ac15907bb0d221973f8ff57a216da316aa4a9f`.

## Required integration decisions

1. Do not allocate this runtime on a task stack or alongside the entire old hold
   runtime by default. Transfer the verified hold state/identities and release
   exported hold buffers before constructing the pair graph.
2. Keep checked allocation failure non-actuating. Check free bytes and largest
   contiguous block before allocation, with an explicit budget for the complete
   networking/JSON/return peak, not just `sizeof(runtime)`.
3. The 139,816-byte JSON evidence store duplicates data retained in raw snapshots.
   Review reducing that duplication while preserving exact immutable records,
   digest identity and complete raw replay. Do not lower sample coverage or erase
   forward evidence early merely to make allocation succeed.
4. Measure runtime free heap, largest block and task stack margins at idle, after
   hold handoff, during forward capture and during return admission on a reviewed
   candidate. Read-only metrics do not authorize deployment; deployment remains
   separately approved. No movement should begin if allocation fails.
5. Complete concrete transport and host export linkage after the ownership and
   peak-allocation design is established. Target compilation alone is not readiness.
