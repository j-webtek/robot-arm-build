# Retained local host-boot observations

This is a callable metadata provider and pure evidence codec, not a reboot
command, device authorizer, identity qualification decision or machine
attestation. Actual CIM/host metadata execution is **NOT_RUN**. The implementation
was exercised with injected provider output and sealed incapable child processes.

## API

`rocell.providers.windows.host_boot_observation` provides:

- `HostBootRequest(source_sha256, session_id, launch_session_id, operation_id,
  trial_id, phase, expires_at_ns)`; exact phases are `BASELINE`,
  `RECONNECT_ABSENCE`, `AFTER_RECONNECT`, `AFTER_REBOOT`. Request construction is
  pure. `payload` is canonical ASCII bytes and `sha256` binds every field.
- `WindowsHostBootObserver(executor=None)`, with inert construction, and one-use
  `observe(request, *, cancellation, deadline_ns, admission_check)`.
- Immutable `HostBootObservation(payload)` with `sha256`, detached `to_dict()`
  and `safe_summary()`. Restoration validates the complete canonical record
  without filesystem, process or metadata calls. Invalid provider output remains
  retained in the original execution bytes and cannot supply host/boot keys.
- `compare_boot_observations(before, after)`, returning
  `SAME_HOST_SAME_BOOT`, `SAME_HOST_DIFFERENT_BOOT` or `HELD`. This comparison
  does not authorize a phase transition or make the complete USB series valid.
- `LocalCimHostBootExecutor`, the fixed production composition, and
  `IncapableHostBootExecutor(directory, scenario)`, a separate closed synthetic
  child fixture. A supplied alternate executor is labeled `INJECTED_CIM_EXECUTOR`;
  it is never labeled actual local CIM merely because its bytes look physical.

The external `admission_check` must recheck already-owned application authority,
source and lifetime and return `None` or raise. It is called before system-path
resolution, immediately around process admission (including resume and stdin),
and after cleanup; it must not consume a fresh permit each time. Cancellation,
deadline and immutable command/request checks also bracket these callbacks.
The provider never acquires an M1 lease or creates a device permission itself.

## Fixed acquisition and bounds

An explicit production call resolves the Windows system directory using
`GetSystemDirectoryW`, then selects only its
`WindowsPowerShell/v1.0/powershell.exe`. It does not search PATH or accept an
executable, query, class, property, remote endpoint or working directory from
the operator. The entire fixed script and argv are retained with their hashes.
The executable is byte-hashed, then reopened and held against writes/deletion
with its path components pinned before process creation. Windows servicing hard
links are allowed by this *new* composition because the owned file handle denies
write/delete sharing across aliases; old worker registration rules are unchanged.
This is not a full interpreter/DLL closure or native-release qualification.

The fixed local script reads `Win32_OperatingSystem.LastBootUpTime`, `Version`
and `BuildNumber`, `Win32_ComputerSystemProduct.UUID`, and LastBootUpTime again.
It requires one instance of each result and an unambiguous DateTime kind.
It reads no other inventory, invokes no CIM methods and performs no reboot,
port/device reset, serial operation, camera activation or USB request.

The process is atomically assigned to a kill-on-close Job before its first
instruction, with one active process, 256 MiB process/512 MiB Job committed-memory
caps, a sampled 1,024-handle limit, bounded inherited pipe handles and an exact
stdin request followed by EOF. Run time is at most 10 seconds with a separate
2-second cleanup reservation, both contained by the caller's deadline. Each
stdout/stderr stream retains at most 4,096 bytes; overrun consumes only a bounded
sentinel and holds the observation. The record labels each stream
`COMPLETE_PIPE_EOF`, `BOUNDED_PREFIX_ONLY` or `NO_OUTPUT_RETAINED`. Prefix hashes
are never claims to hash all output the child attempted to emit.

All owned resource cleanup is attempted once. Unresolved process, pipe, pinned
file or pending-I/O ownership is retained in memory and blocks later dispatch;
there is no retry/reset API. The Job bounds the launched process tree, **not**
the pre-existing Windows WMI service. Killing the child cannot prove that
provider activity inside that service was cancelled, nor prove device cleanup.

## Evidence and boot comparison

The canonical record (maximum 32 KiB) includes exact request and command,
execution status/errors/cleanup, start/end monotonic and UTC timestamps,
retained raw stdout/stderr, hash/length/EOF coverage, decoded provider response,
derived keys and fixed limitations. All physical/hardware/device-I/O authority
flags remain false. A safe summary exposes the actual bounded UUID, boot UTC
and OS fields for comparison, without raw pipes or executable paths.

The stable host key hashes the observed SMBIOS UUID and its declared basis.
The stable boot key hashes that host key and the normalized provider-reported
boot UTC. Neither includes PID, app launch, current time nor inferred uptime.
All-zero/all-one UUIDs, missing/invalid fields, changed boot reads, future boot
times, backward wall time, or a wall/monotonic interval disagreement exceeding
one second produce `HELD` and no keys.

Comparisons require the same original source/session/trial, same evidence
origin, same host key, distinct observations and consistent UTC ordering. A
different boot epoch must fall after the previous completed observation and
before the new observation. No monotonic timestamp is compared across boots.
A new app launch with the same boot key remains `SAME_HOST_SAME_BOOT`. The
caller must additionally validate phase order, distinct attempts, manual
transition evidence, selected USB identity/topology, exact received-label
correlation and full original-store retention before any stage decision.

## Official basis

- [Win32_OperatingSystem](https://learn.microsoft.com/en-us/windows/win32/cimwin32prov/win32-operatingsystem)
  defines LastBootUpTime as the operating-system restart time.
- [Win32_ComputerSystemProduct](https://learn.microsoft.com/en-us/windows/win32/cimwin32prov/win32-computersystemproduct)
  identifies UUID as SMBIOS Type 1 data and documents the unavailable zero value.
- [Get-CimInstance](https://learn.microsoft.com/en-us/powershell/module/cimcmdlets/get-ciminstance)
  documents local WMI COM when no ComputerName or CimSession is supplied.
- [GetSystemDirectoryW](https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/nf-sysinfoapi-getsystemdirectoryw)
  supplies the bounded explicit system-directory lookup.
- [Fast Startup](https://learn.microsoft.com/en-us/troubleshoot/windows-client/setup-upgrade-and-drivers/updates-not-install-with-fast-startup)
  can preserve the kernel session across shutdown/power-on. An operator should
  follow the approved manual Restart procedure; the application never invokes it.

The UUID is not authenticated or clone-proof and LastBootUpTime is a provider
report, not a cryptographic boot nonce. Neither establishes camera connection,
camera/arm qualification, firmware identity, power state or motion authority.

## Executed checks

`test_host_boot_observation.py` covers strict codecs, exact source/request/
command/response hashes, missing and ambiguous fields, same/new launch versus
same/new boot, replay, changed host, clock discontinuities, Stop/admission
changes, cleanup quarantine, and actual owned incapable child nominal/flood/
timeout/descendant/error paths. No test invokes CIM or observes a real device.
