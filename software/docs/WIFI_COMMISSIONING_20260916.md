# Wi-Fi commissioning — 2026-09-16

## Confirmed

- Arm reachable at `http://192.168.0.225` on the local network.
- Windows neighbor observation matches expected MAC `FC:E8:C0:F8:D5:38`.
  This is a local identity check, not cryptographic authentication.
- One HTTP `T=406` request returned HTTP 200 and
  `/wifiConfig.json created.` The returned boot mode was 3 (AP+STA),
  station SSID `littledogs`, and fallback AP SSID `RoArm-M3`.
- Credential-bearing response fields were discarded; no passwords are recorded
  in this document or retained command output.
- One HTTP `T=105` feedback request returned HTTP 200 and valid T=1051 feedback,
  parsed with the existing feedback parser. Host transaction time: about 109 ms.
- No movement command, reboot, torque change or automatic retry was issued.

Reported joint angles in radians, in b/s/e/t/r/g order:

```json
[-0.001533981, 0, 1.593806039, 0.010737866, 0.001533981, 3.149262558]
```

Controller-reported XYZ in millimetres:
`[345.5616805, -0.530085395, 214.0210682]`.
These are not independent physical measurements. Voltage was absent in this
response and remains unknown; do not interpret absent voltage as zero.

## Boundaries and next work

Saving was acknowledged by the device; persistence after reboot has not been
tested. No reboot was requested because startup may move the arm. The IP address
may change after a future DHCP lease; a router reservation is not configured.

The current reported pose differs from the frozen v22 experiment anchor. Do not
reuse the old baseline or silently widen its tolerance. One HTTP response is not
an admitted motion baseline or a 35-second persistence observation.

The production wizard movement path remains USB serial. This was a bounded
manual HTTP commissioning check with proxies and redirects disabled, a five-
second request timeout and a 16-KiB response limit. It is not yet a reusable,
tested wireless wizard transport or raw-provenance campaign export.

Next implement a read-only HTTP feedback provider and wizard diagnostic action:
validate device/address binding, reject redirects, bound response sizes/times,
validate finite feedback, redact configuration responses, and export request/
response timing. Test timeout, malformed response and identity-change behavior.
Then assess feedback cadence before designing a separately gated wireless motion
path. Never automatically retry movement after a timeout: delivery may already
have occurred. Keep USB and HTTP ownership mutually exclusive during campaigns.

## Wizard feedback integration completed

Added the physical-mode wizard action **Read arm positions over Wi-Fi (no
movement)** (`read_arm_wifi_feedback`). Construction, status and action preview
are inert. Explicit execution sends one fixed T=105 request after a local MAC
check and checks the neighbor identity again after the response. Browser input
cannot select arbitrary URLs or commands. The endpoint is pinned to this bench
address; a DHCP address change will require deliberate reconfiguration.

The provider disables proxies by using a direct HTTP connection, does not follow
redirects or retry, bounds body size to 16 KiB, uses a two-second socket inactivity
timeout and checks a five-second elapsed budget while reading the body. This is
not a hard wall-clock deadline against malicious slow headers. Cancellation is
cooperative; it cannot interrupt every blocking socket or metadata call instantly.

Unknown response fields and raw exception text are not exported. Results retain
the response digest, byte count, finite six-joint values, identity observations,
request count and cleanup status. Raw response bytes are intentionally not saved;
this export is not a replayable raw-telemetry positional campaign.

Live wizard test at 13:35 UTC succeeded with one feedback request, zero motion
commands and zero serial opens. Returned joints matched the preceding manual
snapshot. Full diagnostic duration was 1579 ms including two Windows neighbor
lookups; this is not HTTP-only latency or a measured polling cadence.

Export:
`software/runs/wizard-exports/wizard-20260916T133557785189Z-3e25febcb3c746e9beea7cfbebab179c`.
Operation: `operation-e6984219e18d45899869e439d4d965c8`.

62 provider/wizard-service tests passed, covering invalid feedback, redaction,
oversized responses, identity mismatch/change, redirects, timeout, cleanup failure,
inert preview and diagnostic export. JavaScript syntax validation passed; no
interactive browser acceptance test was performed.

To explicitly run one diagnostic and export via the wizard service:

```powershell
.\.venv\Scripts\python.exe software/scripts/bench_wifi_feedback.py
```

Next: a finite feedback-only sampling diagnostic to measure gaps, failures and
HTTP timing separately from identity lookup overhead. Before any wireless motion,
add cross-session transport ownership, baseline admission, bounded command handling
and original-response provenance suitable for endpoint reconstruction. Do not run
this probe alongside an active USB movement campaign. Wireless movement remains
unimplemented; the production movement path remains serial.

## Finite Wi-Fi sampling — 2026-09-16 13:39 UTC

Implemented the wizard action **Measure Wi-Fi feedback timing (no movement)**,
`sample_arm_wifi_feedback`, and `bench_wifi_feedback.py --sample`. It attempts at
most eight sequential observations, stops on the first failed probe/cancellation,
and checks a 30-second budget between probes. No automatic retry or catch-up
requests. Existing per-probe identity, response, cleanup and privacy checks remain.
The budget is not hard process containment; an in-flight probe can finish after
it expires. Tests cover inert preview, export, finite count, first-fault stop,
cancellation, budget and malformed responses: 68 tests passed. JavaScript syntax
checking passed; no interactive-browser acceptance test was performed.

The live wizard run completed eight of eight requests successfully in 10.437 s:

- HTTP transaction times: minimum 62 ms, maximum 172 ms, mean 115.125 ms.
- Consecutive response-completion gaps: about 1.250–1.359 s.
- All six reported joint spans were zero over these observations.
- Identity checks before/after each response matched; cleanup completed.
- No movement commands, USB opens, configuration changes or retries.

Operation: `operation-4b1e9b88fe37440a8512fa72f778c33c`.
Verified diagnostic export:
`software/runs/wizard-exports/wizard-20260916T133944457205Z-dd97f70899af4322bf336fa89ae66f90`.

Timing uses host monotonic observations, not device timestamps. Identical
responses do not prove freshness. Eight successes are a short connectivity check,
not a reliability guarantee, positional persistence qualification or streaming
benchmark. The observed cadence includes two PowerShell neighbor lookups per
sample and is not the network's maximum polling rate.

Next improve identity-lookup overhead using a bounded native Windows neighbor
query, retain the before/after identity checks, then repeat a finite cadence test.
Before wireless motion, shared transport ownership, admitted baseline/command
handling, and raw telemetry evidence still need integration. The existing USB
campaign's continuous-capture criteria are not automatically satisfied by these
sparse HTTP responses. Wireless movement remains disabled.

## Direct Windows lookup and repeat test — 2026-09-16 13:42 UTC

Replaced PowerShell startup on each identity check with the read-only Windows
`GetIpNetTable` API. The wrapper loads `iphlpapi.dll` from System32 lazily, uses a
fixed 64-KiB buffer and makes one OS query per check. Oversized tables, API errors,
truncated records, invalid target entries and multiple matching records fail
closed. It does not resolve addresses, modify ARP entries or cache a successful
identity decision. Both checks per HTTP sample remain in place. This remains a
neighbor-cache consistency check, not cryptographic authentication or proof of
the device's firmware identity.

Provider timing now uses `perf_counter` for higher-resolution elapsed measures;
the exported `timing_clock` identifies this change. Absolute timestamps from
separate runs or different clock implementations must not be compared.

83 tests passed across ABI/parser cases, API errors, one-call behavior, feedback,
sampling and wizard-service regressions. Direct Windows output matched the
existing PowerShell neighbor lookup for the arm before the live repeat.

Eight of eight live feedback requests succeeded, with all identity checks and
cleanup successful:

- Total sampling time: 510.387 ms (previous diagnostic: 10,437 ms).
- HTTP transaction time: 40.700–108.772 ms, mean 62.842 ms.
- Response-completion gaps: 41.387–109.523 ms.
- All six reported joint spans: zero.
- Motion commands and serial opens: zero.

The total short diagnostic was about 20 times faster. That is not a sustained
polling-rate guarantee; network conditions and timing resolution also changed
between runs. No retry, movement, configuration change or reboot occurred.

Operation: `operation-23a69eb322864ac98ab073b5db2456e5`.
Verified export:
`software/runs/wizard-exports/wizard-20260916T134226516518Z-6b1ff48150e049fb8990e18ff2af11e1`.

Next: implement a bounded longer observation with timestamped original feedback
evidence and exclusive transport ownership, then test reconstruction and failure
handling. This is needed before routing a reviewed movement through HTTP. The
eight-sample diagnostic is not a substitute for the existing 35-second positional
campaign or a fresh admitted six-joint starting pose.

## Retained 35-second observation — 2026-09-16 13:49 UTC

Added `observe_arm_wifi_feedback` to the wizard and `--observe` to the bench
diagnostic launcher. It collects for approximately 35 seconds, at most 200
samples, paced to at most five request starts per second, with first-fault stop
and cooperative cancellation. An in-flight request can finish after the nominal
deadline; this is not hard process containment.

Successful original HTTP bodies are retained as base64 with SHA-256, byte count,
host request/response timestamps and derived joint values. Original retention
accepts only known numeric T=1051 fields, rejects duplicate fields and caps each
body at 2048 bytes. Unknown/malformed bodies are not retained to avoid credential
leakage; their failure metadata remains. Offline reconstruction checks original
digests, parsed values, ordering and derived joint spans. Digests do not prove
device authenticity, sensor freshness or the truth of host timestamps.

A named Windows mutex now excludes concurrent **participating wizard Wi-Fi
actions and owned USB positional campaigns** across processes. Busy/unavailable
or abandoned locks reject access. This is not universal ownership: the arm's
web page, other computers, direct provider calls and legacy USB entry points do
not participate. No physical stop guarantee follows from the lock. All other
controllers must remain idle during these experiments.

Validation: 139 tests passed, including pacing, cancellation, retention privacy,
tamper rejection, real cross-process lock contention/release, wizard export and
USB positional regressions. JavaScript syntax checking passed.

Live result:

- 172 requests succeeded in 35.010 seconds; no retry or movement command.
- Successful response endpoints span 34.787 seconds.
- Maximum response-completion gap: 361.847 ms; 61 gaps exceeded 250 ms.
- Maximum HTTP transaction: 226.157 ms; mean 107.853 ms.
- All six reported joint spans were zero. This is not proof of freshness.
- No USB ports opened; all accepted originals reconstructed consistently.

Operation: `operation-4eb4e4384b39470d80112953c6450f6e`.
Export (also independently verified from its absolute path):
`software/runs/wizard-exports/wizard-20260916T134947260157Z-ee2a78ec396245f18819ff6820e8bb09`.
Manifest SHA-256:
`6649b716a91d7a0764c8d4ff5749e3d345ac43ddb3677d5f4648b0798c988e28`.

Collection succeeded; **movement readiness remains false**. At five request
starts per second, variable response latency naturally stretches some response
gaps beyond 250 ms. This result does not isolate a network defect. It also does
not satisfy the existing USB campaign's continuous-feedback gap criterion.

Next compare a bounded, faster feedback-only polling schedule using these same
retention, identity and ownership controls. Keep the older gap criterion intact
and report achieved coverage. A wireless motion path still needs its own reviewed
command admission, uncertain-delivery handling without retries, current-pose
checks and endpoint reconstruction before the first physical test.

## Separate 10-Hz-ceiling experiment — 2026-09-16 13:53 UTC

Implemented `rocell.arm_wifi_observation.v2`, exposed as the wizard action
`observe_arm_wifi_feedback_fast` and launcher flag `--observe-fast`. v1 remains
the unchanged five-Hz profile. v2 is a separate 35-second diagnostic, at most
400 samples, with a 100-ms minimum start interval and a retained-sample budget
of 512,000 serialized bytes checked after each sample. The last retained sample
can cross that budget; no subsequent request is dispatched. No overlap, catch-up
burst, retry, movement command or change to the 250-ms gap diagnostic was added.

The live test **failed and stopped on its first fault**:

- 83 request attempts, 82 successful original responses, 9.866 seconds elapsed.
- Successful response span: 9.683 seconds.
- Maximum response-completion gap: 430.117 ms; two gaps exceeded 250 ms.
- All six reported joint spans within this run were zero.
- Last request passed its initial identity check but recorded no HTTP status.
  Failure reason was `REQUEST_OR_FEEDBACK_FAILED`; cleanup succeeded.
- No retry, movement command or USB open occurred.

The broad historical error does not identify whether request sending or response
header acquisition failed. Do not retroactively label it a timeout, disconnect,
rate-limit or firmware failure. One failed run does not establish a safe maximum
polling rate. The faster profile has **not** been qualified for movement.

The successful samples reported wrist pitch t=0.007669904 rad, versus
0.010737866 in the prior observation. No movement was commanded by these
diagnostics. The difference occurred between observations; its cause is not
established. Never substitute either snapshot for a fresh motion baseline.

Operation: `operation-98fed3926e3d429793a5fecbefa01975`.
Verified export:
`software/runs/wizard-exports/wizard-20260916T135351222192Z-8b89c8da204845fa851395d2e822d559`.
Manifest SHA-256:
`3cc7394f0185e3e39100a704bac8094335820216c3e89d3b07ade03ba187e641`.
Offline reconstruction matched the saved summary and verified all 82 originals.

Following this result, added fixed error categories and failure phases to future
probe results: identity, connection creation, send, headers, body and parsing.
Numeric OS error codes are retained where available; exception text, response
fragments and credential-bearing fields remain excluded. Unit tests cover timeout
and remote-disconnection classification without leaking error text. No live retry
was performed after adding this instrumentation. Final suite: 104 tests passed.

Next run a deliberately bounded diagnostic with the new failure details, then
use the evidence to choose polling/connection handling. Do not raise rates again
or relax endpoint criteria to mask this failed experiment. Wireless motion and
compensation remain disabled pending their distinct transport/admission work.

### Instrumented repeat and five-Hz control comparison

The instrumented ten-Hz-ceiling repeat stopped on request 139 after 138
successful originals (16.003 seconds). Windows reported CONNECTION_RESET,
errno/winerror 10054, during RESPONSE_HEADERS. The failed request passed its
initial MAC check, returned no HTTP status and completed cleanup. Maximum
successful completion gap was 334.153 ms, with four gaps over 250 ms.

Operation: `operation-d5933b51ca7d476a891828885ae6cf2f`.
Export: `software/runs/wizard-exports/wizard-20260916T140529205394Z-4a533e8c66f1467f896b04793b71b129`.
Verified manifest SHA-256:
`04aeff3a8c7d7879efca728f38ea56d5faf8e32ef866730fc65aab6cc9f046de`.

A separate unchanged five-Hz-ceiling control then stopped on request 19 after
18 successful originals (4.149 seconds), also CONNECTION_RESET/10054 during
RESPONSE_HEADERS. Maximum completion gap was 713.567 ms, with five gaps over
250 ms. This contradicts treating five Hz as already reliable based on its
earlier single successful observation; lowering the rate alone is not a proven fix.

Operation: `operation-79687278f88443e5991a42f86c70f8e8`.
Export: `software/runs/wizard-exports/wizard-20260916T140906592400Z-872dadc4682247749d2c3d1436f4f1ed`.
Verified manifest SHA-256:
`d8ec2a26b4e34d5e6d8d1a3f298e4d1bdec78edb2d705567814fd6ca676f7b29`.

Both exports independently passed verification and exact offline summary
reconstruction. Within each run all six reported joint spans were zero. Neither
run sent movement commands, opened USB, retried a request, or changed firmware.
The reset identifies a transport failure, not its root cause or originating
network component. No source-code change was made during these observations.

### Official firmware compatibility finding and next experiment

Inspected the official [20260701 example archive](https://files.waveshare.com/wiki/RoArm-M3/RoArm-M3_example_20260701.zip)
linked from Waveshare's RoArm-M3 page, in memory without installing or flashing it.
Archive SHA-256: `a28247fee0bbb65cc034ff206031b8700d2b1ec8e3a1fa4b1a5a7365c55f1a57`.
Its `http_server.h` uses ESPAsyncWebServer, queues `/js` commands, returns
an HTTP acknowledgment (or queue-full error), and provides `/ws` WebSocket.
Its main loop sends command feedback through that WebSocket. This differs from
our observed direct HTTP T105/1051 responses. The downloaded example is therefore
not established as the installed firmware, and cannot establish this reset's cause.

Next steps, in order:

1. Read-only fingerprint the installed root page/available protocol metadata with
   bounded response sizes; do not invoke configuration, reboot, or motion commands.
   Keep raw page content out of exports because it may contain network settings.
2. Record only allowlisted HTTP framing details (version, close/keep-alive behavior,
   numeric content length), then decide whether a persistent-connection experiment
   is supported. Current probes deliberately create and close a connection per GET.
3. Add offline tests for acknowledgment-only responses and transport variants;
   acknowledgments must never count as joint feedback or movement completion.
4. Run a separate finite feedback-only comparison of the supported variant. Keep
   failed attempts visible, preserve original successful responses, and stop on
   the first fault. Do not hide instability with automatic retries.
5. Only after repeatable transport observations, integrate a fresh-baseline,
   bounded movement command plus explicit endpoint feedback verification. Do not
   reuse an old USB pose or interpret controller feedback as external XYZ accuracy.

No firmware update, WebSocket command path, persistent connection, or wireless
movement has been enabled by this investigation. Network interference, firmware
behavior and connection churn remain hypotheses, not diagnosed causes.

### Installed HTTP fingerprint and connection-cooldown mitigation

Read-only inspection on September 16 found HTTP/1.1, a 54,153-byte root page
(SHA-256 `2f93fdc878a0ecc24d8e6e3a3c5803184165a6d2ec3cf265d86c41e2408e75e8`),
XMLHttpRequest usage, and no literal WebSocket or `/ws` references in that page.
This is a protocol fingerprint, not a firmware version identification. Raw page
contents were neither printed nor saved. A separate T105 request explicitly
asking for keep-alive received HTTP 200 / T1051, 201 bytes, `will_close=True`,
and no retained socket. Persistent reuse is not supported by this observation.
Both checks held the cooperative transport lock and checked the neighbor MAC.

Added a distinct v3 diagnostic with 500 ms quiet **after** each completed request,
including slow responses. Existing v1/v2 profiles remain unchanged. It runs for
35 seconds with at most 70 requests, stops on the first fault and retains original
successful numeric responses. No automatic retry, reboot, configuration command,
firmware installation, or movement is involved.

Available in the wizard as **Observe Wi-Fi with connection cooldown (no movement)**,
or via `software/scripts/bench_wifi_feedback.py --observe-spaced` using the workspace
Python environment. Preview is inert; execution and export use the existing wizard
service and transport lock. The UI explicitly warns that this cadence is not fast
motion-monitoring qualification.

Two separately initiated live runs completed:

| Run | Responses | Elapsed | Maximum completion gap | Outcome |
| --- | ---: | ---: | ---: | --- |
| 1 | 57/57 | 35.005 s | 687.998 ms | Completed, no reset |
| 2 | 56/56 | 35.003 s | 814.197 ms | Completed, no reset |

Within both runs, all six reported joint spans were zero. Successful responses
total 113 across the two sessions; this is not one continuous 70-second session.
Every inter-response gap exceeded 250 ms, as expected for this deliberately slow
profile. Both exports independently passed integrity verification and exact
offline summary reconstruction.

Run 1: `operation-397fa78a5a524f91b70317307b370652`;
`software/runs/wizard-exports/wizard-20260916T141433785910Z-be1fa11550794677a1f82cf93f9f7362`.
Manifest SHA-256: `b74272cb4c887d0906dfc686b13af0d83f8065be915332a5c25d8fb9f1638c73`.

Run 2: `operation-0d7b35bdfeb8400b99809693f5ed0744`;
`software/runs/wizard-exports/wizard-20260916T141519900799Z-242c548f3bc6478da2434e8d87c59415`.

Validation: 109 unit/service tests passed, including completion-based cooldown,
slow response pacing, first-fault stop, cancellation, inert preview, export and
rejection of acknowledgment-only responses as feedback. JavaScript syntax checked.

Conclusion: request spacing is a promising, twice-demonstrated mitigation for
stationary status reads, not a proven root-cause fix or a reliability guarantee.
The experiment changed both connection cadence and idle time; it cannot distinguish
connection cleanup, network variability, and firmware scheduling effects.

Next: characterize an intermediate post-completion cooldown in a separate bounded
profile, preserving these controls. If faster feedback remains unreliable, keep
Wi-Fi for low-rate status/configuration and retain USB for tight movement telemetry,
or separately qualify a supported streaming transport. Do not automatically change
firmware, relax the 250-ms criterion, or retry uncertain movement commands.

### 150-ms post-completion cooldown: two successful observations

Implemented separate v4 (`observe_arm_wifi_feedback_intermediate` in the wizard,
`--observe-intermediate` in the bench script). The finite diagnostic waits 150 ms
after each completed probe, runs for 35 seconds with at most 234 requests, and
preserves all previous profiles. Requests never overlap or retry. The normal
identity checks, cooperative transport lock, numeric originals and export path
remain in effect. The duration is checked between requests; a final in-flight
request may finish after the nominal duration, as with the older profiles.

Offline validation: **112 tests passed** plus JavaScript syntax validation.
Coverage includes slow responses followed by the full cooldown, cancellation,
first-fault stop, inert wizard preview, retained export and acknowledgment rejection.

| Run | Valid responses | Elapsed | Mean completion gap | Maximum gap | Gaps >250 ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 117/117 | 35.005 s | 300.034 ms | 426.889 ms | 105/116 |
| 2 | 118/118 | 35.015 s | 297.394 ms | 429.418 ms | 102/117 |

Both runs completed without reset, with zero reported within-run joint spans,
zero motion commands and zero USB opens. Both diagnostic exports independently
verified, and their exact original-response reconstruction matched the stored
summary. Host timestamps confirmed at least the configured 150-ms gap from each
response completion to the next request start. This is 235 successful readings
across two separate sessions, not one continuous session.

Run 1: `operation-84fcb6d4d1ec487ebb6c4ee25f89ffa3`.
Export: `software/runs/wizard-exports/wizard-20260916T142622962207Z-be62821521d64796b6cb4cab2505eaee`.
Manifest SHA-256: `ed3fb90113e1ca77bd6b27185d6e0221ad368c276b79341758af69d23a1b2713`.

Run 2: `operation-130dac8fd822485996963845ca1371fb`.
Export: `software/runs/wizard-exports/wizard-20260916T142718951598Z-906bc07155ba48f8a2282d4cb658077a`.

Decision: 150-ms cooldown is a promising faster stationary-read diagnostic,
roughly doubling the sample count of the 500-ms observations. It is NOT a
qualified fast movement-feedback transport: most measured completion gaps exceed
250 ms. No criteria were relaxed and wireless motion remains disabled. Two
successful trials do not prove a permanent reset fix or establish its root cause.

Superseded by the user-approved discrete policy below. Previous proposed experiment:
a distinct 75-ms completion cooldown, first offline then
one live run and a repeat only if that run succeeds. Stop at a fault; do not
automatically fall back/retry or increase the request rate after failure. Compare
reset frequency and actual timing separately. If reliable sub-250-ms feedback
cannot be demonstrated, retain these Wi-Fi modes for status and pursue USB or a
separately qualified streaming transport for tight movement monitoring.

### User-approved discrete movement policy

The 250-ms criterion is not a hard requirement for discrete endpoint tests.
Implemented the provisional one-second gap allowance with 150-ms cooldown and
unchanged endpoint accuracy checks. See [discrete Wi-Fi endpoint policy](DISCRETE_WIFI_ENDPOINT_POLICY.md)
for implementation, retrospective timing assessment, and remaining single-command
runtime work. The 75-ms experiment is no longer the next step. No live Wi-Fi
movement was performed for this policy change.

### Official sources

- [Windows mutex wait semantics](https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-waitforsingleobject)

- [Windows GetIpNetTable](https://learn.microsoft.com/en-us/windows/win32/api/iphlpapi/nf-iphlpapi-getipnettable)
- [Windows MIB_IPNETTABLE layout](https://learn.microsoft.com/en-us/windows/win32/api/ipmib/ns-ipmib-mib_ipnettable)

- [Wi-Fi configuration and save command](https://www.waveshare.com/wiki/RoArm-M3-S_WIFI_Configuration)
- [RoArm-M3 HTTP communication](https://www.waveshare.com/wiki/RoArm-M3)
- [Feedback command](https://www.waveshare.net/wiki/RoArm-M3-S_%E6%9C%BA%E6%A2%B0%E8%87%82%E6%8E%A7%E5%88%B6)
