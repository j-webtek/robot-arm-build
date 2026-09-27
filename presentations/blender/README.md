# Tactevra workcell explainer

This package builds a reproducible Blender scene and short informational film of
the current Tactevra RC03 workcell concept.

The scene deliberately separates four evidence classes:

- **Measured** — RC03 board and device envelopes copied from
  `active-project/RoCell_v0_3/config/workcell_layout.json`.
- **Designed** — repository-owned portal and station STL geometry.
- **Vendor surface authority** — the arm's visible base, links, servo housings,
  wrist, fasteners, and gripper tessellated locally from Waveshare's
  hash-verified official assembly STEP.
- **Kinematic authority** — the arm frame chain, joint origins, TCP, and nominal
  board-to-robot transform reconstructed from the separately hash-pinned URDF
  and frozen simulation profile.
- **Conceptual** — target paths and explanatory motion graphics. These
  communicate intended behavior; they are not collision or motion
  qualification.

No manufacturer robot surface mesh is redistributed. A preparation script
downloads the pinned official archive, verifies its SHA-256, checks the STEP
envelope, and creates a local presentation mesh below ignored `/tmp/`. The
official assembly's default pose is shown as a static product visualization;
the film does not claim that pose is a qualified live trajectory.

`dimension_manifest.json` records the values and source authorities used by the
film. Run the validator before rendering:

```powershell
python presentations/blender/validate_dimensions.py
python presentations/blender/prepare_official_arm_asset.py
```

## Build

Blender 4.3 or newer:

```powershell
& "C:\Program Files\Blender Foundation\Blender 4.3\blender.exe" `
  --background --factory-startup `
  --python presentations/blender/build_workcell_explainer.py
```

This creates local generated media under `tmp/blender-workcell-video/`:

- `tactevra_workcell_explainer_v1.blend`
- `tactevra_workcell_explainer_poster_v1.png`

Review seven low-resolution editorial frames before the full render:

```powershell
& "C:\Program Files\Blender Foundation\Blender 4.3\blender.exe" `
  --background --factory-startup `
  --python presentations/blender/build_workcell_explainer.py -- --preview-shots
```

Render the complete 22-second, 24 fps, 1920×1080 film with:

```powershell
& "C:\Program Files\Blender Foundation\Blender 4.3\blender.exe" `
  --background --factory-startup `
  --python presentations/blender/build_workcell_explainer.py -- --render-video
```

The resulting MP4 is written beside the scene. Generated `.blend`, frames, and
video stay out of source control through the repository's existing `/tmp/`
ignore rule; the source scene builder and production notes are the reviewable
authorities.

When a clean render already exists and only screen-space labels changed, rebuild
the final MP4 without rerendering the 3D frames:

```powershell
& "C:\Program Files\Blender Foundation\Blender 4.3\blender.exe" `
  --background --factory-startup `
  --python presentations/blender/build_workcell_explainer.py -- --overlay-only
```

## Film structure

| Time | Shot | Evidence communicated |
|---:|---|---|
| 0–3.7 s | Product promise | One user request becomes one checked physical action |
| 3.7–7.4 s | 1 — Perceive | Fixed vision and direct tags establish the shared board frame |
| 7.4–10.7 s | 2 — Propose | AI supplies intent, target, frame, and confidence—not raw servo commands |
| 10.7–14 s | 3 — Check | Deterministic gates validate units, frames, reach, clearance, and freshness |
| 14–17 s | 3 — Check target + route | Named targets resolve through measured device geometry inside the deterministic check |
| 17–18.5 s | 4 — Execute | The sole controller writer sends one admitted, bounded action |
| 18.5–19.7 s | 5 — Verify | Telemetry and observation close the loop before the next action |
| 19.7–22 s | System close | One shared contract connects intent to verified physical action |

The composited information layer maintains a persistent architecture spine—
`PERCEIVE → PROPOSE → CHECK → EXECUTE → VERIFY`—and highlights the active
stage in every chapter. This gives a first-time viewer a stable mental model
while the camera moves between the workcell, arm, devices, and route.

The film ends with a visible qualification disclaimer. It must not be used as
fabrication approval, camera-load approval, or robot-motion evidence.

## Authoritative inputs

- `active-project/RoCell_v0_3/config/workcell_layout.json`
- `hardware/static_overhead_camera/config/printable_frame_design.json`
- `hardware/static_overhead_camera/cad/output/assembly/printable_camera_portal_printed_parts_only.stl`
- `active-project/RoCell_v0_3/stl/keyboard_station_left.stl`
- `active-project/RoCell_v0_3/stl/keyboard_station_right.stl`
- `active-project/RoCell_v0_3/stl/phone_tcp_station.stl`
- `software/models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf`
- `presentations/blender/dimension_manifest.json`

## Accuracy boundary

The board, keyboard and phone envelopes, indexed station placement, reference
tag centers, camera target, portal mesh, arm joint origins, TCP offset, and
nominal robot transform are sourced directly from repository authorities. The
station and portal shapes are imported from their actual STL files.

The arm's visible geometry comes from the official vendor STEP, but the source
and local tessellation remain untracked. Its STEP pose is static; it is not
segmented or driven as a qualified digital twin. Device manufacturing
variation, cable geometry, the installed robot transform, tag stack height,
and tool geometry also remain physical-measurement items. This film is therefore
an accurate system-layout and product-geometry explainer, not a motion-clearance
or fabrication release.

## Narration guide

> One request enters Tactevra. First, fixed vision and direct tags anchor the
> workspace to a shared board frame. The AI proposes intent, a named target,
> coordinate frame, and confidence—but never raw servo commands. Deterministic
> gates then check units, calibration, reach, clearance, and freshness. Measured
> device geometry resolves a key or phone control into a bounded target. The
> sole controller writer executes one admitted action. Telemetry and observation
> verify the result before the system continues. This visualization uses current
> RC03 dimensions and repository CAD. The arm surface comes from the
> hash-verified official assembly STEP and is shown in its default static pose;
> target paths remain conceptual until physically qualified.
