# Install the camera-v2 runtime and reviewed software policy

10 September 2026. The preceding scoped-campaign checkpoint is verified progress.
The full camera/arm wizard remains the objective. Agents currently report terminal
usage-limit errors; this increment is being implemented locally without device access.

## Implementation sequence

1. Install the previously compiled v2 activation code in a new `activation_v2`
   native source directory. Preserve the legacy worker, manifests, binaries and
   sealed checkpoints. Remove the draft's direct inventory, identity and legacy
   command paths from this new worker.
2. Build separate fixed-purpose probe and capture executables at the paths already
   required by `NativeCameraActivationRuntime`. Both must accept only the exact
   matching v2 flag and hash, followed by REQUEST/READY/RELEASE/EOF. Share the
   established fresh-identity comparison and cleanup code.
3. Compile with the existing MSVC/SDK and warning/error/mitigation policy. Execute
   only incapable tests: identity comparison, protocol, launch selection, gate
   ordering and cleanup. Exercise actual pipe/result codecs with an incapable
   child. Never register a camera-capable worker as a CTest executable.
4. Retain purpose-specific build records: exact native input hashes, compiler and
   SDK, binary sizes/hashes, test evidence, and explicit untested-device limits.
   Verify these inputs independently before committing reviewed pins to the
   application. Runtime file contents must not teach the checker what to trust.
5. Add the application software-policy join: inert creation of exact candidates
   from the reviewed catalog, followed by bounded installed-file/source checks
   that can be called by the original application's current-context guard. This
   is software verification, not physical authority or a UI permission switch.
6. Test wrong purpose, stale application/native source, modified/missing helper
   or record, cancellation, exact factory binding and preserved legacy pins.
   Record verification and the next original-service/UI handoff in this document.

## Qualification boundary

The first supervised diagnostic probe must be allowed by reviewed software while
received-hardware qualification remains false; requiring already successful camera
qualification would create a circular gate. Exact current enrollment, original
stage/epoch facts, capacity admission and a consumed one-use scope are still
required independently. A good executable hash or stored report is not permission
to open a camera. Driver behavior, USB throughput, optics, freshness, cleanup and
calibration need received-hardware evidence. Arm energy/motion/contact remain
separate operations and are not implemented or authorized by this camera change.

Microsoft's [activation documentation](https://learn.microsoft.com/en-us/windows/win32/api/mfobjects/nf-mfobjects-imfactivate-activateobject)
requires ownership/release of returned interfaces and appropriate shutdown. The
existing native cleanup path and parent process supervision are preserved; a
software Stop result does not certify driver cleanup or physical arm power-off.

The assigned diagnostics folder remains
`C:\Users\Jack\Desktop\robot-arm-build\software\runs\wizard-exports`.

## Installed runtime checkpoint

The production v2 worker is now installed under
`software/native/windows_camera/activation_v2`. The legacy worker, old build
records and binaries were not changed. Separate `build-owned-activation-probe`
and `build-owned-activation-capture` builds compile to the fixed paths already
required by the Python preparation layer.

The new worker has no directly executable inventory, identity, self-test or
legacy probe/capture route. Its shared launch predicate checks the exact purpose,
argument count and lowercase request hash before touching pipes or APIs. REQUEST,
fresh READY challenge, bound RELEASE and EOF still precede native startup. The
fresh identity comparison and original five-second native deadline remain intact.
Capture keeps the established exact mode/control and exclusive output-file rules.

`camera_activation_runtime_policy.py` supplies two application APIs:

- `reviewed_activation_runtime_candidate(...)` creates an inert candidate from
  fixed reviewed pins and the current application source. It does not inspect
  files, connect a device or convert the candidate's `dispatch_enabled` field.
- `verify_reviewed_activation_runtime(...)` reads the pinned build record, helper
  and all 24 fixed native source/test inputs. It checks the application source
  before and after those reads, enforces cancellation and the caller's original
  deadline, and returns a diagnostic software observation. The native read budget
  is 16 MiB / 160 calls / at most ten seconds, also capped by the original deadline.
  Existing application source checks retain their separate 128 MiB bound.

The actual `PhysicalCameraActivationCampaign` calls this software checker
internally at each current scoped boundary. A permissive original-context guard
cannot replace the fixed software policy. Tests exercise eight actual installed-
file checks in a full modeled campaign; the original facts and process owner in
those tests remain modeled. The original application still must authenticate its
identity, stage, epoch, runtime-review provenance and capacity facts independently.

No report is a replayable authorization. Candidate construction remains inert;
observations explicitly state `original_context_authenticated=false`,
`hardware_qualified=false`, `connected=false` and zero device operations. File
failures carry a closed workspace-relative filename and error code for actionable
UI diagnostics. The observation is not an atomic filesystem lock: the existing
process owner separately pins executable/build bytes during execution. Synchronous
filesystem calls are not forcibly interruptible; late returns are refused.

### Build and test evidence

- Both fixed-purpose workers compile with MSVC 19.42.34435.0 / Windows SDK
  10.0.22621.0, Release x64, `/W4 /WX /permissive- /utf-8 /guard:cf`, and the
  existing `/DYNAMICBASE /NXCOMPAT /guard:cf` linker policy. Neither capable
  camera executable was run.
- Each build passes five incapable CTests: 83 identity comparisons, 106 gate
  assertions, 39 launch assertions, 99 protocol assertions and 148 cleanup
  assertions. The two runs took 0.20 s and 0.19 s, respectively.
- Installed native interop: **25 passed, 1.98 s**, covering both incapable result
  helpers, both purposes, six modeled outcomes and exact serializer extraction.
  The result helper links no COM/MF or metadata resolver/device adapter.
- Build records are `owned_activation_probe_build_manifest.json` and
  `owned_activation_capture_build_manifest.json`. They retain exact native
  inputs, artifact hashes/lengths and the initial native/interop report hashes.
  The application pins those records independently instead of trusting hashes
  learned from whichever files an operator points it at.
- Initial policy tests passed 30 checks; two additional cases check changed
  in-flight file bytes and Stop during a native-file read. The actual scoped
  composition adds installed-file checks and refusal before owner creation.
- Targeted mypy passes all three changed production modules; Black passes ten
  changed production/test files.

Final application fingerprint:
`9d9a3f15f4ffbba54fd745a09b373e227cf8d776f7a1cdf6494d31f35601008a`.
On these final sources, `activation-runtime-final-20260910-01.xml` passes
**382 checks in 59.98 s**, and `activation-runtime-legacy-20260910-03.xml`
passes **378 checks in 39.33 s**. Those are **760 passing Python checks**, including
the 25 native interop cases; the ten incapable CTests are counted separately.
They are selected regression/composition tests, not full-public-wizard acceptance
or proof that a camera-capable executable has run. Historical public acceptance
continues to belong to its recorded earlier source fingerprint.

A regression run preserved at
`.codex-preserved/activation-runtime-legacy-20260910-01.xml` failed 37 cases
(231 passed). A cold `platform.system()` cache on this Python/Windows runtime
invoked a `ver` shell subprocess during an otherwise inert status projection.
The production status check now uses process-local `sys.platform`; the file-only
fixture deliberately clears the old platform cache so this cannot hide behind
test order. The affected rerun, including enrollment/arm display regressions,
passed **378 checks in 37.63 s**. No subprocess prohibition was relaxed.

### Rebuilding for developers

Do not overwrite this reviewed runtime or automatically replace its trust pins.
For a source change, configure a **fresh** build directory with the explicit
`ROCELL_ACTIVATION_PURPOSE=probe` or `capture`, using this new CMake project.
Compile it, run only its incapable CTests and the separately pinned incapable
interop tests, then review new source/binary/record hashes before updating the
application catalog. Changed build bytes should fail the old policy until that
review is complete. Never use the capable camera executable as a build self-test.

### Exact next service/UI work

The native build and independently enforced software gate now exist. The next
work is the original stage-5 acquisition successor and public application join,
not another arbitrary physical-enable flag:

1. Authenticate the accepted original v15 entry and current enrollment, review,
   epochs and source; create the v2 candidate from this catalog. Record the exact
   selected runtime/review context without interpreting software agreement as
   driver or hardware qualification.
2. Admit private output-parent and metadata/frame/disk capacity before effects.
   Bind substantive original facts to the existing M1 coordinator and mandatory
   guard. Its consumed scope remains the sole execution context.
3. Implement the additive original acquisition/readback record and service action,
   then connect existing browser/terminal controls to one-use probe/capture and
   Stop, bounded pixel verification/preview and original/private export/reopen.
4. Continue optics/placemat calibration and the independent original arm
   identity/startup/feedback services. Later motion/contact remains separately
   commissioned work. Neither hardware arrival nor this runtime installation
   by itself completes those software integrations.

## Preserved checkpoint

The [developer checkpoint](../runs/wizard-exports/developer-checkpoint-camera-v2-runtime-20260910-01/README.md)
contains 1,028 verified copies / 21,804,556 bytes, including 379 application inputs,
46 native files and 97 final original M1 test files. Independent rehashing found
zero mismatches and the copied application fingerprint matches. Both launch modes
start disconnected with zero operations and the assigned export folder. Separate
read-only installed-software observations match all 26 required files per purpose;
they grant no physical authority. This navigation section was added after copying
the work order, leaving the archived pre-copy document unchanged.
