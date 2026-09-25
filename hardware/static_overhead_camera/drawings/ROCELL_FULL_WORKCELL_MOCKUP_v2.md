# Workcell realistic mockup v2

Created with built-in ImageGen, using a dimensionally scaled CAD render as the sole geometry reference. This is a visualization of the current prototype design, not fabrication approval or proof of camera-load safety. No engineering geometry was changed.

## Scale and sources

- Board: 610 × 457 × 18 mm.
- Printed portal overall mesh bounds: 850 mm wide; 1108.9 mm from bench plane to top.
- Tower axes: 730 mm apart.
- Camera optical-height target: 1000 mm above board.
- Keyboard nominal envelope: 315 × 147 × 21 mm.
- Phone nominal envelope: 77.9 × 164.4 × 7.9 mm, flat in its cradle.
- Portal geometry: ../cad/output/assembly/printable_camera_portal_printed_parts_only.stl
- Portal configuration: ../config/printable_frame_design.json
- Workcell layout: ../../../active-project/RoCell_v0_3/config/workcell_layout.json
- Reproducible reference renderer: ../../../tmp/workcell_mock_v2/render_reference.py
- Robot visual meshes: manufacturer roarm_ws repository, commit 40dbd84b553695212fab713e8465f817ba95454d, roarm_m3 visual links. Nominal robot pose and installed base/clamp placement are illustrative, not a surveyed installation.

The accompanying SCALE_REFERENCE image is the dimensional visual authority. AI-generated bolt details, tags, surface features and minor geometry are illustrative; do not count hardware or measure from the photorealistic image. The source configuration remains a parametric prototype, not released for fabrication or robot operation.

## Final ImageGen prompt

Use case: sketch-to-render.
Primary request: Turn the supplied dimensionally scaled CAD reference into a photorealistic product mockup of this exact robotic keyboard-and-phone workcell. The input is the geometry authority. Preserve its exact camera angle, object positions, silhouettes, lattice construction, proportions, and generous empty vertical space. Square image.

The object is a tall bench-mounted workcell. It is NOT a short desktop gantry. The black 3D-printed portal is approximately 1109 mm from bench to top, 850 mm overall width including the feet; tower axes are 730 mm apart. The wooden board is only 610 mm wide, 457 mm deep, 18 mm thick. Thus tower height is about 1.8 times BOARD width. Keep this exact tall aspect ratio from the reference. Do not enlarge the devices or shorten the towers to fill space.
Two open-lattice segmented black ABS towers at the near FRONT corners, connected by an open-lattice crossbar. Preserve the repeated triangular open cutouts in all truss members, broad rectangular splice collars and flat corner joining plates. Exactly two parallel open-U lattice booms extend AWAY from the viewer, horizontally behind the front crossbar, to the carriage over board center. Camera is a SMALL machine-vision body and cylindrical downward-facing lens, partially obscured below the carriage as in the reference. Do not enlarge it into a DSLR or drop it down on a long stalk.
A black compact keyboard sits flat in black perimeter station clamps at left front. A black smartphone sits FLAT screen-up in portrait orientation in a low black printed cradle at right front, with the small calibration island immediately to its left. Preserve their projected size from the reference: keyboard 315x147 mm; phone 78x164 mm. The robot is mounted at board rear center, with its upper link nearly vertical and its forearm reaching toward the viewer as the mesh shows. It is a small black Waveshare RoArm-M3, with slender twin carbon-fiber link plates and servo housings. Preserve its actual pose, height, narrow links and compact base; add realistic mechanical surface detail without changing its silhouette. Six square reference tags stay at the positions shown, use plausible black-white AprilTag-like patterns.
Add light birch plywood grain, realistic matte black printed ABS with fine horizontal layer texture, restrained metal bolt heads ONLY at the existing connection holes, metallic servo details, keyboard key legends and subtle dark screen reflection. USB routing follows the thin line shown above the right crossbar and down the right tower; safety tether is thin stainless steel. Do not add orange decorative cables.
Environment: a neutral light gray sturdy workbench surface supporting BOTH portal feet and entire plywood underside at the same height, soft warm-neutral studio lighting, gentle contact shadows and sharp detail. No workshop clutter. Keep full assembly in frame.
Hard constraints: match reference geometry and component scale; no parts relocated; no cylindrical fat robot redesign; no closed rectangular metal extrusion replacing printed lattice; no horizontal beam at board height; no extra tower or camera; no large hanging camera; no floating parts; no tilt of phone screen; no labels, dimensions or text outside keyboard legends; no changed camera viewpoint. This is a MATERIAL AND LIGHTING pass on the given CAD assembly, not a redesign.

