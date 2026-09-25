# RoArm-M3-Pro simulation model contract

> **Camera architecture notice — 2026-09-05:** Phase 1 now uses a rigid static
> overhead Arducam B0477 with the included 16 mm lens, so its source-locked
> nominal support, lighting, and cable belong to the static workcell model
> rather than the robot-link model. Receipt, installed geometry, calibration,
> and qualification remain open. The bundled upper-arm holder and
> attached-camera geometry are retained for optional Phase 2 research only,
> never automatic fallback. This model grants zero physical authority.

This directory is the source-controlled, simulation-only model boundary for the
RoCell arm. The received product is a Waveshare RoArm-M3-Pro. Waveshare does not
publish a separate Pro kinematic model, so the common M3 ROS model is used only
as a nominal kinematic seed. Nothing here releases power, motion, or contact.

## Pinned sources

| Source | Pin | Purpose |
| --- | --- | --- |
| [Official ROS workspace](https://github.com/waveshareteam/roarm_ws) | commit `40dbd84b553695212fab713e8465f817ba95454d`; raw Xacro SHA-256 `b6333849d0e377008eee0a87a5b8cdcf44f7a73edf3d7600e95506a023a234b6` | link/joint graph, transforms, nominal limits, FK |
| Local kinematic projection | [`roarm_m3_kinematic_40dbd84.urdf`](roarm_m3_kinematic_40dbd84.urdf); SHA-256 `a565718e7d74b07702802cf41eb9549a6e38e50b5e80aa9b887ab1ae3d0d8190` | dependency-free runtime parsing and deterministic tests |
| [Official Python SDK](https://github.com/waveshareteam/waveshare_roarm_sdk) | commit `d9893632aa7f5a9cb283136ab024faf3143ea7db` | joint order, gripper convention, transport/API comparison |
| [Official firmware archive](https://files.waveshare.com/wiki/RoArm-M3/RoArm-M3_example_20260701.zip) | SHA-256 `a28247fee0bbb65cc034ff206031b8700d2b1ec8e3a1fa4b1a5a7365c55f1a57` | controller FK and T=104/T=1051 behavior |
| [Official assembly STEP](https://files.waveshare.com/wiki/RoArm-M3/RoArm-M3_STEP_260310.zip) | SHA-256 `1e2111145276aac14e521f47990fc41de87e2e735623d115a39cc176c9762da2` | future reduced collision geometry |
| [Official 2D drawing](https://files.waveshare.com/wiki/RoArm-M3/RoArm-M3_2Dsize.zip) | SHA-256 `edd125e39f43d8d8722b7207668c176e75aca866735829be19c98ddd1dba99d0` | envelope/correlation evidence |
| [Official camera-holder drawing](https://files.waveshare.com/wiki/common/Camera%20mounting%20bracket%20drawing.zip) | SHA-256 `da64a8e053f392a8f9f81b933a864ba9166bf7378f8e820bda1f398b0d4c4e81` | holder interface evidence |

The canonical raw Xacro hash is byte-sensitive. Do not replace it with a Git
checkout hash produced after automatic Windows line-ending conversion.

## Kinematic contract

All revolute axes in the pinned model are joint-local +Z. Linear origins below
are metres and angular values are radians.

| Joint | Parent to child | Origin xyz | Origin rpy | Model limit |
| --- | --- | --- | --- | --- |
| `world_to_base_link` | `world` to `base_link` | `0,0,0.0701` | `0,0,0` | fixed |
| `base_link_to_link1` | `base_link` to `link1` | `0,0,0` | `0,0,0` | `[-pi,pi]` |
| `link1_to_link2` | `link1` to `link2` | `0,0,0.051959` | `[-pi/2,-pi/2,0]` | `[-pi/2,pi/2]` |
| `link2_to_link3` | `link2` to `link3` | `0.236815,0.030002,0` | `0,0,pi/2` | `[-1,2.95]` |
| `link3_to_link4` | `link3` to `link4` | `0,-0.144586,0` | `0,0,0` | `[-pi/2,pi/2]` |
| `link4_to_link5` | `link4` to `link5` | `0.015147,-0.053653,0` | `pi/2,pi/2,0` | `[-pi,pi]` |
| `link5_to_gripper_link` | `link5` to `gripper_link` | `0,0.018821,0.052035` | `-pi/2,-pi/2,0` | `[0,1.5]` |
| `link5_to_hand_tcp` | `link5` to `hand_tcp` | `0,0,0.115428` | `pi/2,-pi/2,0` | fixed |

Logical order is base, shoulder, elbow, wrist pitch, wrist roll, then gripper.
Golden `world_T_hand_tcp` translations in millimetres are:

| State | Arm joint vector | Translation mm |
| --- | --- | --- |
| zero | `[0,0,0,0,0]` | `(45.147706,-0.000166,672.541110)` |
| home | `[0,0,pi/2,0,0]` | `(343.668130,-0.001262,343.727534)` |
| ready | `[0,0,2.618,-1.0472,0]` | `(271.374308,-0.000997,218.511322)` |

These values and the local file hash are regression-tested.

## Frames that must remain separate

- `Wv`: vendor URDF `world` planning root.
- `R_u`: vendor URDF `base_link`.
- `R_ctrl`: firmware/T=104 Cartesian frame.
- `E`: optional Phase-2 camera carrier rigidly attached to vendor `link2`.
- `holder`: optional Phase-2 physical bundled-bracket frame.
- `C_arm`: optional Phase-2 installed arm-camera optical frame.
- `G`: planning tool-holder/`hand_tcp` frame.
- `T`: physical keyboard or phone contact tip.

The audited controller FK does not cleanly equal the vendor URDF FK after a
single frame offset; configuration-dependent endpoint residuals remain. T=1051
Cartesian fields are therefore `R_ctrl` diagnostics, not `world`, `base_link`,
or `hand_tcp` poses. A measured/controller-correlation artifact is required
before any T=104 command can be derived from a URDF plan.

The camera holder is on the moving upper-arm rails. Its derived vendor carrier
link is `link2`, but these transforms remain intentionally unset:

```text
link2_T_holder
holder_T_C_arm
```

## Controller model

Logical servo IDs are base 11, mirrored shoulder 12/13, elbow 14, wrist pitch
15, wrist roll 16, and gripper 17. The simulator preserves model and controller
gripper conventions explicitly:

```text
q_gripper_model = 0 closed, 1.5 open
g_controller_raw = pi - q_gripper_model
```

The provisional simulation intersection of the URDF and current controller
documentation is base `[-pi,pi]`, shoulder `[-pi/2,pi/2]`, elbow `[0,2.95]`,
wrist pitch `[-pi/2,pi/2]`, wrist roll `[-pi,pi]`, and model gripper `[0,1.5]`.
This is a rejection-test domain, not a live-safe envelope. Product-page and
controller/URDF angle claims conflict and require received-arm hard-stop and
self-interference characterization.

`rocell.simulation.controller` implements the separate controller FK, gripper
conversion, and a bounded deterministic T=104 cosine-easing trace. It labels
`spd` as an opaque mixed-unit firmware coefficient and never encodes or sends a
command.

## Historical optional Phase-2 arm-camera contract

The arm includes the holder but not camera electronics and does not name an
exact supported camera SKU. The Waveshare IMX335 5MP USB Camera (B), SKU 26719,
was the Freeze-009 arm-camera candidate. Its official 21.0 x 13.5 mm
mounting-hole pattern geometrically matches the holder drawing, but it is not
the selected Phase-1 camera. Active Freeze 011 retains these legacy fields
under `CAMERA_ARCHITECTURE_ALIGNMENT_HOLD`; they are not B0477 evidence. The
IMX335 is a USB/UVC camera, not an ESP camera. Any future Phase-2 use still
requires receipt identity, USB descriptors/modes, installed rail position,
intrinsics, rolling-shutter/timing behavior, cable route, mass/CG, and
`holder_T_C_arm` qualification. The selected Phase-1 B0477 and static support
are modeled by the separate workcell contracts.

## Model limitations

The upstream ROS model is not a validated dynamic Pro twin:

- its modeled inertial mass is about 0.449 kg versus the published Pro mass of
  about 1.021 kg;
- its effort and velocity limits are zero placeholders;
- it has no accepted camera, holder, cable, clamp, board, tool, compliance, or
  complete gripper collision geometry; and
- no separate Pro geometry/inertia profile is published.

Use it for nominal link graph, FK/IK, visualization, and collision-seed work.
Do not use it for gravity, torque, impact, contact-force, payload, timing, or
physical safety claims.
