# First real-photo seed: ten keyboard workcell views

The user provided ten original JPEGs on 2026-09-25. Their byte hashes and
dimensions are in [the manifest](../data/real_photo_seed_v0.manifest.json),
and scene-level agent labels are in
[the labels](../data/real_photo_seed_v0.labels.json). Original files remain
under ignored `software/ai/data/raw/real_photo_seed_v0/`; GitHub receives
metadata and labels, not the raw captures or their EXIF.

## What the photos establish

- The current physical scene contains a compact keyboard, RoArm arm, printed
  board-reference sheets, ruler, and fixtures. Several views show the arm over
  or beside the keyboard. The end effector appears bare in these photos.
- The keyboard is visible from high and low oblique viewpoints, with some
  arm/cable occlusion and reflective cover material. These views are useful
  for designing detection labels and testing scene recognition.
- Printed crosses and a ruler supply useful visual context. Their image
  positions are not measured board-to-camera registration. A ruler in a
  perspective image does not establish 3D tool-tip or key coordinates.
- The ten images are correlated views of one setup. No phone or on-screen
  keyboard is present. The loose camera visible in one view is not evidence
  that these frames came from the final fixed overhead camera.

## Current training status

No vision model was trained from this set. It has scene-level labels only,
no target-center or device-pose labels, no calibrated camera identity, no
measured board/keyboard transform, and no independent capture session for a
holdout score. Training coordinate regression on these photos would turn
visual guesses into false physical labels. The photos are now a real-data
seed for annotation design and appearance checks, not an executable
coordinate source.

## Next capture and labeling pass

1. Mount the intended overhead camera and save its original frames with
   camera identity, capture timestamp, image mode, and byte hash.
2. With the robot stationary, record varied keyboard placements, lighting,
   and arm occlusions. Include the intended phone with several clearly known
   screen states in separate capture sessions.
3. Measure or commission the board markers, keyboard/phone pose, target
   centers, and tool-tip/frame transforms. Label visible image regions and
   pixel centers separately from measured millimetre coordinates.
4. Group data by capture session and placement. Hold out whole sessions for
   evaluation. Measure wrong-target selection and board-frame coordinate
   error in addition to image detection accuracy.
5. Feed image-derived observations into the existing visual-target contract;
   then test the combined intent-to-target path before integrating any
   checked motion trajectory.
