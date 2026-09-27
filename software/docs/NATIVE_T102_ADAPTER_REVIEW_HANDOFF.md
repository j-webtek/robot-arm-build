# Native T=102 adapter review handoff

ARM-055 prepares the exact merged ARM-054 Windows serial adapter for an
independent source and composition review. It does not perform that review,
open a serial endpoint, grant physical authority, or qualify movement.

## Bound candidate

The retained verification record is
`software/native/review/arm054-offline-verification.json`. It binds commit
`9bd17ac21d7fd00d18f3dd4378b9bea529b5b681` and the exact bytes of:

- `software/src/rocell/providers/windows/native_t102_serial_transport_v1.py`;
- `software/tests/unit/test_windows_native_t102_serial_transport_v1.py`; and
- `software/docs/WINDOWS_NATIVE_T102_SERIAL_ADAPTER.md`.

Any change to those files fails packet construction until a new candidate is
reviewed and a truthful verification record is deliberately issued.

## Build and inspect

From the repository root, with `software/src` on `PYTHONPATH`, run:

```powershell
python software/scripts/build_arm054_adapter_review_packet.py
```

The builder writes a content-addressed archive beneath the ignored
`software/runs/review-packets/` evidence directory. It uses exclusive creation
and will not overwrite a different archive. Rebuilding the same candidate
produces the same bytes and SHA-256.

The archive contains only the three candidate files, the retained offline
verification record, review instructions, and a canonical manifest. The
fail-closed inspector requires exact membership, paths, sizes, hashes, commit,
offline test counts, and review-only authority flags.

For the bound ARM-054 candidate, the deterministic packet SHA-256 is
`65749a9f122fd4f685375652b6e52a101038a88b0fed1c1b921aea6c4b059f0d` and its
canonical manifest SHA-256 is
`0aff3af9a167e82b792fd55ff6bdd544c6ee2b961109c1dac6d7cb34c17bba4b`.

## Composition evidence

The offline integration test composes the actual ARM-054 adapter class with
ARM-053's production-shaped lifecycle while replacing only the serial endpoint
and Windows inventory with memory fixtures. It proves:

- the successful path preserves ARM-053's durable `started.json` and
  `terminal.json` no-replay lifecycle;
- one canonical T=102 movement write and exactly two T=105 evidence requests
  cross the adapter boundary;
- settled scripted T=1021/T=1051 evidence remains explicitly unqualified; and
- crossed external authority creates a durable start record but is rejected
  before the adapter can open.

This is composition evidence, not hardware evidence. The fixtures cannot
authenticate a controller, establish response provenance, observe movement,
or verify a device outcome.

## External-review boundary

The packet status is `AWAITING_EXTERNAL_INDEPENDENT_REVIEW`. A reviewer must
receive the archive unchanged, verify its manifest, inspect the source and
ARM-053 composition, and publish a separately authenticated decision bound to
the packet SHA-256. The repository must not self-assert reviewer independence.

Even a passing decision would not authorize endpoint opening or movement. A
separate read-only endpoint qualification and, later, a separately authorized
bounded physical test remain required.
