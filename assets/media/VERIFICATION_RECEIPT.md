# Tactevra overview-media verification receipt

**Document status:** Current published-media verification  
**Authority:** Byte identity and post-merge inspection only; this record is not a Blender rerender, third-party-rights disposition, or physical qualification

The current overview-media revision was produced from commit
`6250415bd045652ab219e4a7b0ebf298c075a9d5` through
[pull request #137](https://github.com/j-webtek/tactevra/pull/137). The
machine-readable [verification receipt](verification_receipt.json) binds the
committed media files to exact byte sizes and SHA-256 digests and records the
authority manifest used by the documented scene builder.

## Verified delivery

- The committed MP4 is 77.013 seconds of H.264 video at 1600×900 and 24 fps,
  with AAC stereo audio and a selectable English subtitle stream.
- Eleven timestamp-ordered ElevenLabs narration clips were aligned to the
  documented scene windows without speech-rate modification.
- Final audio measures −14.3 LUFS integrated with a −1.6 dBFS true peak, with
  no interval of one second or longer below −45 dB.
- The sidecar WebVTT file contains 19 ordered cues whose timing fits within
  the delivery duration.
- Twelve representative frames sampled across the committed MP4 were reviewed
  for sequence, framing, readable labels, and the closing limitation notice.
- Static hardware-appearance shots use the hash-verified official RoArm-M3
  STEP-derived surface. Animated execution uses a hardware-shaped articulated
  presentation rig aligned to the official base and dimension contract; the
  resolved H marker matches the nominal target profile recorded in the
  repository.
- Reject and accept cards remain in the empty left-side field so the stationary
  gripper stays visible, and the former persistent micro-label is absent.
- The MP4, poster, social preview, captions, chapters, and dimension manifest match the byte identities
  in the machine-readable receipt.

Blender 4.3.2 and the identified FFmpeg build were observed during the full
rerender and final inspection. Pull request #137 records that render, visual
review, selectable-caption check, and final audio-QA validation.

## Limits

- This is an architectural explanation only. It does not qualify robot motion,
  collision behavior, fabrication, calibration, or autonomous operation.
- Published media includes no vendor source mesh.
- The GitHub delivery is intentionally compressed below the repository's
  10 MiB ordinary-review ceiling; the documented build emits a separate
  higher-bitrate 1920×1080 upload master.
- The wider Waveshare URDF redistribution question remains tracked in
  [issue #88](https://github.com/j-webtek/tactevra/issues/88).
- Any later change to a published media byte or its authority manifest must
  update the machine-readable receipt. CI and the Pages build reject drift.
