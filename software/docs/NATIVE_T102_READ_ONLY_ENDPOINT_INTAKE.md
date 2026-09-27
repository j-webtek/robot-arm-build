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
