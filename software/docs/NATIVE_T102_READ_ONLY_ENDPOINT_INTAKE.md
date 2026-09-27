# Native T102 read-only endpoint intake

ARM-060 defines the hardware-incapable record that must exist before anyone
may separately authorize a passive qualification of the ARM-054 Windows serial
adapter. It turns the owner-accepted ARM-059 review into a precise proposed
procedure without opening a port or communicating with a controller.

## Required bindings

An intake binds all of the following:

- the exact ARM-059 acceptance ID and SHA-256;
- one declared host identity;
- one `PinnedNativeT102EndpointV1`, including COM name, USB VID, USB PID, USB
  serial number, and fixed 115200/8/N/1/no-flow-control settings;
- one creation timestamp that cannot predate owner acceptance; and
- finite passive-read limits: timeout, maximum line count, and maximum bytes
  per line.

The endpoint is embedded and independently content-addressed. Parsing requires
the closed field set, reconstructs the endpoint, and recomputes both endpoint
and intake hashes. A crossed port, device identity, review acceptance, policy,
or content digest is rejected.

## Closed observation procedure

The proposed operation order is fixed:

1. verify the pinned USB identity before open;
2. open only that exact endpoint, at most once;
3. verify the pinned USB identity again after open;
4. passively read only the bounded number and size of lines; and
5. close the exact endpoint, at most once.

The plan permits zero transport writes and zero active requests. It also
forbids buffer purges, endpoint fallback, automatic retry, and DTR or RTS
assertion. Movement and torque command limits are both zero.

## Authority boundary

The successful intake status is
`READY_FOR_SEPARATE_READ_ONLY_AUTHORIZATION`. That wording is deliberate. The
record fixes all of the following false:

- read-only endpoint authorization;
- endpoint-open authorization;
- controller-start authorization;
- transport-write authorization;
- execution authorization;
- hardware access; and
- physical authority.

Consequently ARM-060 can be built, parsed, tested, and reviewed entirely
offline. A later operator authorization must name the exact retained intake
before a distinct hardware-capable tool may perform the bounded passive run.
That later run is not part of ARM-060, and movement remains out of scope.

## Retained ARM-061 intake

ARM-061 used Windows Plug-and-Play metadata without opening the serial endpoint.
It found the already documented CP210x identity at COM7 and excluded the
separate Bluetooth serial ports. The retained intake binds that endpoint to a
pseudonymous SHA-256 host identity rather than publishing the Windows hostname.

The retained file is
`software/ai/eval/arm061_read_only_endpoint_intake.json`, with intake SHA-256
`2d88fa8874088ce47b778343ea0ed07994bafb64267b8cd121765c52536ce1d9`.
It remains non-authorizing. Creating and validating this record did not open
COM7, start the controller, send bytes, or perform movement.

## ARM-062 passive qualification result

The owner separately authorized the exact retained intake for one COM7 open,
one close, at most four passive lines, and one overall second of passive read
time. The dedicated runner passed its non-opening preflight and then executed
once, with no retry.

The retained receipt is
`software/ai/eval/arm062_passive_read_only_qualification_20260927.json`.
Its normalized retained-file SHA-256 is
`ac84722855d43e66e07d512bd60c3d19b2c468c0defe1505303f233bc4148aea`.
The direct PowerShell output used CRLF formatting and had raw SHA-256
`5e3beac11908bef4c310ff599e86d44dc6dae407c2cd57e0f3bdc4dca6886ed9`;
only JSON whitespace was normalized for repository retention.
The exact PnP identity matched before and after the open, open and close each
occurred once, close was confirmed, and all outbound/request/movement/torque,
retry, purge, and DTR/RTS assertion counters remained zero. No unsolicited line
arrived during the window.

An empty passive window is not a controller protocol test. It establishes only
that the pinned endpoint can complete this narrow zero-write lifecycle without
an observed identity change or lifecycle failure. Active protocol queries,
controller startup, firmware provenance, telemetry validity, and movement
remain unqualified and require later, separate authority.

## ARM-063 active-feedback intake

ARM-063 freezes the next proposed diagnostic without executing it. The retained
`software/ai/eval/arm063_active_feedback_intake.json` has intake SHA-256
`3b44d5e011d8c44afda1bb6deb1cc479b1fc0c45e59e39308d285cde416b8fcc`.
It binds the ARM-061 intake and ARM-062 retained receipt to the exact canonical
ten-byte request `{"T":105}\n` (SHA-256
`2cace64403a9db92d57acd8814d55c833529c0341468529900bd89f089e1fa3c`).

The proposed later operation permits one identity-bound open, one exact write,
one bounded T=1051 line, and one close. It requires an empty receive buffer
before the write and complete numeric `b/s/e/t/r/g` feedback. It permits no
T=102, movement, torque command, retry, purge, fallback, controller startup, or
DTR/RTS assertion. The fake-only rehearsal validates these invariants and
terminal cleanup but cannot accept pyserial or any arbitrary transport object.

ARM-063 grants no endpoint-open or transport-write authority. No COM7 access
occurred while creating it. A live exchange requires separate explicit owner
authorization naming the exact ARM-063 intake hash and remains non-moving.
