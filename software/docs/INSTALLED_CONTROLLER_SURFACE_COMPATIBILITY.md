# Installed-controller command-surface compatibility

This offline gate answers one narrow question before a controller application
may be bound to the zero-write Waveshare profile:

> Does the exact passively observed installed app expose the generic command
> and feedback surface required by the production boundary?

It does not send commands, open serial, access the network, restart the
controller, install firmware, or grant execution authority.

## Required production surface

The reviewed app must satisfy all of these requirements:

1. its reviewed application hash matches the passively observed installed app;
2. the running app attests that same hash;
3. it has a bounded generic command dispatcher rather than a fixed diagnostic
   routine;
4. it accepts the qualified Waveshare `T=102` joint-command shape;
5. it can issue the qualified `T=105` feedback request;
6. it parses the corresponding `T=1051` feedback response; and
7. its source and linked image have independent approval.

Any missing requirement creates an explicit blocker. A result with no blockers
is only `COMPATIBLE_FOR_ZERO_WRITE_BINDING`: it still has zero hardware access,
zero generated commands, and no transport, execution, or physical authority.

## r96 result

r96 is a deliberately finite registration-ladder diagnostic. Linked-image and
source review confirm that it has one precompiled base-joint leg, no startup
motion, no automatic progression, no gripper writes, no retry, and no return.
The linked image excludes the generic serial/web command handlers. It therefore
cannot accept arbitrary `T=102` targets or provide the production `T=105` /
`T=1051` feedback exchange.

The exact installed-app hash does match the retained r96 review, so
`APP_HASH_MISMATCH` is not a blocker. The actual assessment is nevertheless
`BLOCKED` by:

- `RUNTIME_APP_HASH_NOT_ATTESTED`;
- `GENERIC_COMMAND_DISPATCH_ABSENT`;
- `T102_COMMAND_UNAVAILABLE`;
- `T105_FEEDBACK_REQUEST_UNAVAILABLE`;
- `T1051_FEEDBACK_RESPONSE_UNAVAILABLE`; and
- `INDEPENDENT_REVIEW_INCOMPLETE`.

This is a useful design conclusion, not a failed physical test. r96 remains a
historical diagnostic landmark and must not be expanded or relabeled as the
production command runtime.

## Reproduce the offline assessment

With the ignored passive evidence record already present:

```powershell
$env:PYTHONPATH='software/src;software/scripts'
python software/scripts/assess_r96_controller_surface.py `
  --passive-evidence software/runs/installed-controller-qualification/r96-passive-20260926.json `
  --output software/runs/installed-controller-qualification/r96-surface-compatibility-20260926.json
```

The output is intentionally local and ignored because it embeds the passive
record's physical USB identity. It binds the passive evidence hash, source and
linked-image review hash, surface evidence hash, controller session, and all
blockers. The assessor contains no live-controller code path.

## Next implementation boundary

Build a separate production runtime candidate with:

- no startup movement and an explicit safe idle state;
- a bounded parser for only the reviewed command contract;
- exact `T=102` field, unit, joint-order, range, and gripper semantics;
- correlated `T=105` request and `T=1051` response handling;
- runtime app-hash and configuration-epoch attestation;
- sole-writer ownership, monotonic sequence IDs, deadlines, cancellation, and
  no automatic retry; and
- independent source and linked-image review before any installation proposal.

That candidate must first pass this gate offline. Installation, startup, and
physical qualification remain separate, explicitly authorized stages.
