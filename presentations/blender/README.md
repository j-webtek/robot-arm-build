# Tactevra workcell explainer

This package builds a reproducible Blender scene and short informational film of
the current Tactevra RC03 workcell concept.

The scene deliberately separates four evidence classes:

- **Measured** — RC03 board and device envelopes copied from
  `active-project/RoCell_v0_3/config/workcell_layout.json`.
- **Designed** — repository-owned portal and station STL geometry.
- **Kinematic authority** — the arm frame chain, joint origins, TCP, and nominal
  board-to-robot transform reconstructed from the hash-pinned RoArm-M3 URDF and
  the frozen simulation profile.
- **Conceptual** — the arm's visible housings, animated joint values, light
  paths, and explanatory motion graphics. These communicate intended behavior;
  they are not collision or motion qualification.

No manufacturer robot surface mesh is redistributed. The arm visual uses an
exact URDF frame skeleton with original proxy surfaces assembled from Blender
primitives. The distinction is intentional: link placement is dimension
controlled, while exterior clearances still require a rights-cleared CAD model
or physical correlation before collision qualification.

`dimension_manifest.json` records the values and source authorities used by the
film. Run the validator before rendering:

```powershell
python presentations/blender/validate_dimensions.py
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

Render the complete 18-second, 24 fps, 1280×720 film with:

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
| 0–4 s | Full-system hero | Designed portal plus measured work surface |
| 4–8 s | Static-vision rise | 1000 mm nominal camera optical target |
| 8–12 s | Device targeting | Measured keyboard/phone envelopes and indexed stations |
| 12–16 s | Checked movement | Exact URDF frame geometry, conceptual motion, and bounded target highlights |
| 16–18 s | System close | Request → perceive → plan → check → act → verify |

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

The arm's exterior housings and links are visual proxies because the pinned
local model contains no redistributable visual or collision mesh. Device
manufacturing variation, cable geometry, the installed robot transform, tag
stack height, and tool geometry also remain physical-measurement items. This
film is therefore an accurate system-layout explainer, not a motion-clearance or
fabrication release.

## Narration guide

> Tactevra turns a user request into a checked physical action. A fixed overhead
> camera observes the indexed work surface. Known keyboard and phone geometry
> anchors each target in the board frame. Perception proposes a destination;
> deterministic planning validates coordinates, clearance, and route. Only an
> admitted movement reaches the controller. The system then observes the result
> before continuing. This visualization uses the current RC03 dimensions and
> repository CAD. The arm follows the pinned URDF frame chain; its visible skin
> and animated poses remain conceptual until physically qualified.
