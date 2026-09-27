# Tactevra workcell explainer

This package builds a reproducible Blender scene and narrated informational film
of the current Tactevra RC03 workcell concept.

The scene deliberately separates six evidence classes:

- **Measured** — RC03 board and device envelopes copied from
  `active-project/RoCell_v0_3/config/workcell_layout.json`.
- **Designed** — repository-owned portal and station STL geometry.
- **Hardware appearance authority** — a local, hash-verified tessellation of
  Waveshare's official RoArm-M3 STEP assembly. It is shown in every static
  architecture, proposal, validation, and verification shot.
- **Kinematic authority** — the arm frame chain, joint origins, TCP, and nominal
  board-to-robot transform reconstructed from the separately hash-pinned URDF
  and frozen simulation profile.
- **Execution-only articulated presentation rig** — aligned to the official
  base position and shaped with the RoArm-M3's rectangular serial servos,
  paired links, exposed fasteners, wrist plates, and gripper language. It is
  used only during the short shot labeled `SIMULATED PRESS`; its authored pose
  is not a solved trajectory.
- **Conceptual** — target paths and explanatory motion graphics. These
  communicate intended behavior; they are not collision or motion
  qualification.

No manufacturer robot surface mesh is redistributed. The preparation script
verifies the pinned official STEP below ignored `/tmp/`. The film uses that
exact surface as its static visual authority and makes the one proxy-motion
cut explicit on screen. Controller close-ups temporarily hide the tall camera
portal to reveal the arm; the overlay identifies this as a presentation
cutaway rather than a different hardware configuration.

The keyboard and phone preserve the measured RC03 device envelopes and target
origins. Their shells, controls, legends, glass, interface, and cables are
presentation-detail geometry: they make the intended device classes and
interactions legible, but are not manufacturer CAD or fabrication authority.

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

- `tactevra_workcell_explainer_v3.blend`
- `tactevra_workcell_explainer_poster_v3.png`
- `tactevra_workcell_explainer_v3.mp4` — 1080p narrated master
- `tactevra_workcell_explainer_silent_v3.mp4` — 1080p picture master
- `tactevra_workcell_explainer_web_1080p_v3.mp4` — web delivery
- `tactevra_workcell_explainer_distribution_1080p_v3.mp4` — high-quality
  1920×1080, approximately 5 Mbps LinkedIn/YouTube upload master
- `tactevra_workcell_explainer_social_square_v3.mp4` — square, captioned derivative
- `tactevra_workcell_explainer_captions_v3.srt` — voice-matched captions
- `tactevra_workcell_explainer_soundtrack_v3.wav` — restrained music and cues

Review thirteen low-resolution editorial frames before the full render:

```powershell
& "C:\Program Files\Blender Foundation\Blender 4.3\blender.exe" `
  --background --factory-startup `
  --python presentations/blender/build_workcell_explainer.py -- --preview-shots
```

Render the complete 77-second, 24 fps, 1920×1080 film with:

```powershell
& "C:\Program Files\Blender Foundation\Blender 4.3\blender.exe" `
  --background --factory-startup `
  --python presentations/blender/build_workcell_explainer.py -- --render-video
```

To replace the fallback voice without rerendering the 3D picture, generate the
eleven clips in `ELEVENLABS_NARRATION.md`, then run:

```powershell
& "C:\Program Files\Blender Foundation\Blender 4.3\blender.exe" `
  --background --factory-startup `
  --python presentations/blender/build_workcell_explainer.py -- `
  --overlay-only --voiceover-dir "C:\path\to\elevenlabs-clips"
```

The resulting MP4 is written beside the scene. Generated `.blend`, frames, and
video stay out of source control through the repository's existing `/tmp/`
ignore rule; the source scene builder and production notes are the reviewable
authorities.

## Publish the repository overview

After reviewing the 1080p delivery render, publish the intentionally tracked
README media with:

```powershell
& "C:\Program Files\Blender Foundation\Blender 4.3\blender.exe" `
  --background --factory-startup `
  --python presentations/blender/build_workcell_explainer.py -- `
  --publish-homepage-media
```

This requires `ffmpeg` on `PATH` and writes a compact MP4, poster, social-card
image, English WebVTT captions, and WebVTT chapters to `assets/media/`. The MP4
contains the same captions as a selectable `mov_text` subtitle stream, so they
can be enabled or disabled by the viewer. Add future languages as separate
WebVTT files and subtitle streams; do not burn accessibility text into the
picture master.

The repository README uses the poster as a durable GitHub-compatible preview
that links directly to the captioned video. This avoids autoplay and respects
reader choice while keeping the explainer prominent on the main page.

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
| 0–4 s | Request | One clear task: “Press the H key” |
| 4–10 s | Stakes | Physical AI must be dependable because guesses become motion |
| 10–14 s | Promise | One request becomes one checked physical action |
| 14–22 s | 1 — Perceive | Fixed vision and tags establish a shared board frame |
| 22–30 s | 2 — Propose | The model proposes an action and target, never raw motor commands |
| 30–37 s | 3 — Reject | A stale, malformed plan is blocked while the arm stays still |
| 37–44 s | 3 — Accept | Every deterministic admission gate passes |
| 44–51 s | Resolve | The H key resolves through the camera, board, and device frames |
| 51–58 s | 4 — Execute | A single rendered, explicitly simulated H contact is shown |
| 58–65 s | 5 — Verify | Telemetry and observation close the loop |
| 65–72 s | Payoff | The five stages join into one shared contract |
| 72–77 s | End card | Brand, tagline, URL, and a restrained qualification note |

The composited information layer maintains a persistent architecture spine—
`PERCEIVE → PROPOSE → CHECK → EXECUTE → VERIFY`—and highlights the active
stage in every chapter. This gives a first-time viewer a stable mental model
while the camera moves between the workcell, arm, devices, and route.

The film ends with a small grey qualification note. It must not be used as
fabrication approval, camera-load approval, robot-motion evidence, or evidence
that a physical keypress occurred.

## Editorial system

The final composite adds a controlled finishing layer without altering the
dimension-checked 3D render:

- true 200 ms cross-dissolves overlap adjacent camera setups without discarding
  source frames;
- chapter titles explain one architectural decision at a time;
- a persistent five-stage spine highlights the current system responsibility;
- monospace cards show a nominal model proposal, admission result, resolved
  board target, execution permit, and verification result;
- the deterministic check contrasts a rejected stale-frame example with an
  accepted proposal, making the safety boundary visible instead of merely
  describing it;
- an explicit frame-chain card shows how `camera_px` becomes `board_mm`, then a
  device-local named target;
- the hash-verified official arm surface makes the expected motor housings,
  dual-link architecture, fasteners, and gripper silhouette legible in every
  static hardware shot;
- a six-row compact keyboard reconstruction uses the measured RC03 envelope
  and the nominal 19.05 mm pitch encoded by the target profile, with realistic
  stagger, modifier-key widths, recessed key wells, beveled caps, legends,
  enclosure trim, status lights, and a connected cable rather than a uniform
  placeholder grid;
- a layered phone reconstruction adds an aluminum envelope, optical glass,
  receiver, camera, side controls, cable, and a modeled host-verification UI
  while preserving the configured phone origin and measured screen plane;
- a small persistent Tactevra wordmark establishes brand continuity without
  competing with chapter titles;
- procedural birch and bench variation, restrained depth of field, animated
  focal length, pulsing registration tags, board-frame axes, and a visible
  camera-to-board-to-key trace add material and motion depth while keeping the
  exact hardware surface visually coherent;
- every chapter has its own camera grammar: a complete workcell reveal,
  hardware beauty orbit, fixture-to-lens perception move, three distinct
  decision dollies, orthographic-like target resolution, tooling close-up,
  sharp phone macro, and wide payoff return;
- the target-resolution camera is square to the keyboard, the execution view
  keeps the complete servo-style rig and attached harness in frame, and the
  payoff pushes closer so the physical system supports the closing summary;
- key legends, an H target ring carried into contact, a connected stylus, and separate
  telemetry and host-result panels make the target, action, and observed result
  legible without implying a live controller trace;
- calm local narration is the loudest element; the deterministic soundtrack
  uses one cue meaning per state and stays audible between lines at roughly
  18–22 dB below the voice;
- silent 1080p, narrated 1080p, web 1080p, square social, and SRT caption
  variants are generated from the same authority;
- proposal, resolution, and execution cards are framed as model, contract, and
  simulation evidence rather than as a live controller trace;
- informational graphics are composited after transitions, keeping titles and
  evidence labels readable during every cut.

The published poster and social card deliberately differ from an ordinary
beauty frame. They pair the film's blocked stale-plan state with its verified
host result under the headline “Physical intelligence, checked.” so the shared
image explains the product even before a viewer presses play.

When revising the film, preserve these communication rules: one idea per shot,
no unqualified capability claims, no raw model output presented as an admitted
controller command, no critical text outside title-safe margins, and no visual
effect that obscures the hardware evidence.

The registration pulses and frame-chain trace are conceptual state graphics.
They are not a TCP trace, servo simulation, collision result, or qualified
trajectory. The rendered tool contact is explicitly labeled as a simulated
press. The arm in that execution shot is a hardware-shaped articulated
presentation rig aligned to the official base and URDF dimensions, not a
segmented, validated digital twin. Static shots use the exact official
assembly surface but do not establish an installed pose or clearance.

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

The visible arm is dimensioned from the pinned official URDF but is not a
qualified digital twin. The optional vendor STEP and local tessellation remain
untracked. Device manufacturing
variation, cable geometry, the installed robot transform, tag stack height,
and tool geometry also remain physical-measurement items. This film is therefore
an accurate system-layout and product-geometry explainer, not a motion-clearance
or fabrication release.

## Narration and truth boundary

`generate_voiceover.ps1` creates fallback sentence-level narration using an
installed Windows voice. `ELEVENLABS_NARRATION.md` defines the preferred
eleven-clip handoff; pass its folder with `--voiceover-dir`. The build aligns
either source to the screenplay,
mixes the dialogue to approximately −14 LUFS with a −1 dBTP ceiling, and writes
SRT and WebVTT captions matching the spoken script. Replace the local voice with
a recorded human performance later without changing the timings or captions.

The continuous arm, moving stylus, and H key are presentation animation,
explicitly labeled `SIMULATED PRESS`. They explain the intended controller
boundary; they are not a kinematic solve, collision check, or physical record.
