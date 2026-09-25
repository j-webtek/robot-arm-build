# Calibration registry

Calibration artifacts are immutable, content-addressed evidence tied to the
system manifest, active physical build, exact hardware identities, capture
mode/settings, and parent-artifact hashes.

The registry is intentionally empty. Do not place nominal RC03 geometry,
Waveshare demo intrinsics, a commanded arm pose, or a host image-receipt time
here as if it were commissioned calibration evidence.

Required artifact families are camera intrinsics, measured tag map,
arm-camera extrinsic, arm-board registration, route-specific TCP/compliance,
keyboard pose/key map, and phone screen/target map. Any dependency mismatch
makes an artifact stale; historical evidence is retained rather than edited.

The offline eye-on-arm dataset and numerical candidate solver are documented
in [`../docs/EYE_ON_ARM_CALIBRATION.md`](../docs/EYE_ON_ARM_CALIBRATION.md).
The exact-wire/JPEG pre-exposure-post bundle is documented in
[`../docs/EYE_ON_ARM_CAPTURE_BUNDLE.md`](../docs/EYE_ON_ARM_CAPTURE_BUNDLE.md).
Solver output is always `NOMINAL_ONLY` and has no physical release effect.
There is intentionally no API here that promotes a numerical candidate to a
`VALID` arm-camera extrinsic.

The capture-evidence/FK verifier recomputes every stored `Wv_T_E` from
content-hashed T=1051 fields, explicit joint-reference rules, the pinned URDF,
and supplied `link2_T_E`; only the reviewed repository model digest is
accepted. The current commissioning assessment is deliberately fail-closed:
it does not yet accept the structural capture bundle and still reports
unresolved typed-artifact payloads, qualified clock correlation, raw detector
evidence, active context, and independent validation. It always has physical
release effect `NONE` and cannot create or install a calibration artifact.
