# Owned Windows USB identity component

This is a separate native project. It does not replace or repin any historical
camera helper. The real adapter has been compiled, **not executed or qualified**.
The application still needs its separate reviewed runtime, stage-4 admission,
owned process containment and original-store integration before hardware use.

## Ownership and scope

The only production entry is `--owned-usb-identity --request-sha256 <digest>`.
The parent supplies one exact canonical request over inherited pipes. A random
challenge, child PID, request digest and original permit bind READY/RELEASE;
RELEASE must be followed by EOF within the original five-second admission
window. No endpoint, hub or port is accepted as a direct command-line target.
Only after admission is the real Windows adapter constructed.

The resolver authenticates the selected endpoint's CM ancestry, finds the
physical USB devnode immediately below its first hub, and scans every port of
each bounded hub for one matching downstream driver key. It repeats that full
mapping after collecting descriptors. Neither a composite-interface suffix nor
a parent property is substituted for a missing serial or selected endpoint.

The adapter can open USB hub handles and issue only the closed query operations
in `Op`. This is device I/O, not no-device-open OS inventory. It cannot activate
Media Foundation, capture images, set camera controls, reset ports, change USB
configuration, send vendor requests or access serial ports.

`OBSERVED` means the serial identity and before/after mapping were complete and
stable, with all opened hub handles explicitly closed. It is not a stage PASS,
USB3 qualification, received-product approval or permission to capture. Valid
USB2 operation and unavailable EX_V2 may still yield an identity observation;
their independent operating-link qualifications remain unresolved.

## Bounds and retained meaning

- Native window: 10 seconds; admission: 5 seconds, without renewal.
- At most 128 semantic API-seam calls, 32 hub opens, one live hub handle and
  eight retained hub hops. An exhausted bound yields HELD.
- Per-call buffers: 4096 bytes. Device descriptor: 18 bytes; language/string
  descriptor: at most 255 bytes and four advertised languages.
- Native receipt: 64 KiB, ASCII-escaped JSON. Capacity for evidence and one
  cleanup row is reserved before an operation, not recovered by dropping rows.
- Every close is attempted at most once. A failed close remains outstanding;
  process termination does not retroactively establish successful CloseHandle
  or USB completion. The parent must retain missing/late results as uncertain.

Call counts describe the closed adapter seam, not individual kernel calls.
`MAP_ENDPOINT` internally creates an information set, opens the exact interface,
reads its detail and destroys the set once. Hub/host-interface lookup performs
one device-ID read plus one size/read pair for the exact devnode and fixed GUID.
There are no unbounded size retries or global discovery fallbacks. A successful
metadata read followed by failed information-set cleanup remains an ERROR and
may retain the bytes it already observed.

EX retains the complete returned 35-byte header and any reported 11-byte pipe
records, up to the per-call cap. EX_V2 is a separate 16-byte response. Its
operating/capability flags remain independent categories, never invented Mbps.
Descriptor IOCTL byte counts include the 12-byte USB_DESCRIPTOR_REQUEST header;
descriptor subjects retain the returned payload only. Serial calls retain the
actual iSerialNumber index and advertised language ID. Malformed UTF-16 never
becomes a replacement string or inferred identity.

Every successful EX/EX_V2/device/language/serial call also retains
`returned_raw_hex`, including empty or truncated returned payloads. This keeps
malformed PRE/POST port-scan bytes even when no selected link subject exists.
The field is null on other operations and failed IOCTLs. It represents the
successfully returned payload, not the entire allocated OS buffer; descriptor
payloads exclude their 12-byte request header. Selected raw subjects must match
their original OBSERVE call bytes. Duplicated hex is included in the unchanged
64 KiB limit, so large complete responses can exhaust the budget and stay HELD.

## Layout and hardware-free verification

`observation.cpp` owns the bounded resolver; `windows_api.cpp` is the real Windows
adapter; `admission*.cpp` owns request/handshake processing; `serialize.cpp`
retains the receipt. The public API and closed operations are in the headers.

The separately linked `rocell_usb_identity_tests.exe` and
`rocell_usb_identity_entry_tests.exe` contain **no Windows USB adapter**. Their
topology, descriptors, clocks and failures are explicitly modeled. They are the
only executables run by CTest. The production executable has no fixture switch.

Using the already installed MSVC and Windows SDK:

```powershell
cmake -S software/native/windows_usb_identity -B software/native/windows_usb_identity/build -G "Visual Studio 17 2022" -A x64 -DCMAKE_SYSTEM_VERSION=10.0.22621.0
cmake --build software/native/windows_usb_identity/build --config Release --parallel 2
ctest --test-dir software/native/windows_usb_identity/build -C Release --output-on-failure
```

`wire_test.py` consumes original fake-produced JSON through the actual Python
observation parser, including the exact Unicode request. `entry_test.py` runs
the incapable inherited-pipe child through the actual request, READY, release
and owned-result codecs; it tests refusal without EOF, changed bindings and
extra input. The CTest timeouts are test containment, not proof of production
USB cancellation or physical qualification.

The source work order is `software/docs/CAMERA_USB_IDENTITY_IMPLEMENTATION.md`.
The Python decoder is `providers/windows/usb_identity_protocol.py`; changes to
the new wire must be coordinated with that independent strict consumer.
