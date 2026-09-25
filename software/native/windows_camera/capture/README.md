# Guarded native capture development build

This separate build compiles the existing Media Foundation capture implementation
behind a mandatory inherited-pipe admission gate. The helper is **compiled, not
executed or registered**. Camera/driver behavior, physical admission, output-path
race containment and power-loss cleanup remain unqualified. Historical metadata
and probe binaries, build manifests, source files for the old gate, and the
original `CMakeLists.txt` are unchanged. The small compile-defined additions to
`camera_worker.cpp` mean its current hash differs from both historical records;
neither record is rewritten or relabeled as current approval.

## Wire and effect ordering

Only `--owned-capture --request-sha256 <lowercase-sha256>` selects the new gate.
No endpoint, output path, settings or authorization Boolean is accepted on this
command line. Direct `capture`/`probe` arguments still fail before COM/MF.

The canonical request schema is
`rocell.native_camera_capture_admission_request.v1`. Its 15 exact flat fields are
the original probe's 14 fields plus the string `capture_json`. That string holds
an independently canonical 11-field flat object:

- `width`, `height`, `fps_numerator`, `fps_denominator`, `subtype` (`YUY2`);
- `frame_count`, `max_frame_bytes`, `max_total_bytes`;
- `output_directory`, `controls`, `requested_stride_bytes`.

The old flat parser still has its original 16-field limit. Control encoding is
sorted `name,value,mode` entries separated by semicolons, at most the existing six
IDs; empty means no control change. Signed integers have no plus sign, leading
zeros or negative zero. Empty stride is unspecified; otherwise its nonzero
signed value and row span must fit the frame budget.

Capture binds a 5,000 ms admission budget and 5,000 ms native campaign. The old
probe remains separately fixed at 2,000 ms admission. The capture entry starts
one original deadline covering request read, READY write, RELEASE read and EOF;
no parse or grant renews it. The shared READY/RELEASE schemas bind the exact
capture request hash, actual PID, random challenge and permit hash. The child
protocol does not independently verify M1 authority: the parent must perform
its current consumed-scope checks and enforce the original full lifetime.

After RELEASE and EOF, the native helper reconstructs the closed logical capture
arguments. Output must equal `current_path()/('capture-'+attempt_id)` exactly.
Local absolute Windows paths use backslashes, with no root, UNC, ADS, traversal,
dot/space aliases or reserved device names. The existing empty-directory and
non-reparse ancestor check runs before COM/MF, and again before source discovery.
No output directory is created by this gate. Parent-owned path handles and
received-unit qualification remain required; stat checks are not a race proof.

When a requested stride is present, the negotiated mode must report that exact
stride before controls are applied; each sample must also match before file
creation. The original sample format, native timestamps and cleanup receipt are
unchanged. No file hash, sensor timing, identity or camera capability is invented.
The parent must validate/hash actual files separately before dataset ingestion.

## Isolated build and tests

```powershell
cmake -S software/native/windows_camera/capture -B software/native/windows_camera/build-owned-capture -G "Visual Studio 17 2022" -A x64
cmake --build software/native/windows_camera/build-owned-capture --config Release --parallel 2
ctest --test-dir software/native/windows_camera/build-owned-capture -C Release --output-on-failure
```

CTest registers only two hardware-incapable tests, never the real helper:

1. `rocell_camera_capture_admission_tests.exe` links the pure parser/hash library.
2. `rocell_camera_capture_admission_entry_tests.exe` links only the real capture
   pipe gate and parser, without `camera_worker`, identity, MF or COM code. Its
   fixed harness exercises actual PID/challenge/EOF, Unicode JSON, delayed grant,
   missing grant/EOF timeout, wrong permit, trailing input and schema/path faults.
   It creates no camera output directory or frame. The harness is not a substitute
   for the application's separately tested owned-process coordinator.

The entry target emits `rocell.native_camera_capture_admission_only_test.v1`,
explicitly not a native capture receipt. The real helper and a capture-disabled
probe compile-check binary are built but never executed. A separate
`owned_capture_build_manifest.json` records exact source/artifact hashes and the
limited development evidence; it grants no registration or physical authority.
