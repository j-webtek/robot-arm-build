# Tactevra overview-media verification receipt

**Document status:** Current published-media verification  
**Authority:** Byte identity and post-merge inspection only; this record is not a Blender rerender, third-party-rights disposition, or physical qualification

The current overview-media revision entered `main` in commit
`3e8be273cdf53daeef1818da8f027225b700c0e4` through
[pull request #112](https://github.com/j-webtek/tactevra/pull/112). The
machine-readable [verification receipt](verification_receipt.json) binds the
committed media files to exact byte sizes and SHA-256 digests and records the
authority manifest used by the documented scene builder.

## Verified delivery

- The committed MP4 is 77.003 seconds of H.264 video at 1920×1080 and 24 fps,
  with AAC stereo audio and a selectable English subtitle stream.
- The sidecar WebVTT file contains 19 ordered cues whose timing fits within
  the delivery duration.
- Seven representative frames sampled across the committed MP4 were reviewed
  for sequence, readable labels, and the closing limitation notice.
- The MP4, poster, captions, and dimension manifest match the byte identities
  in the machine-readable receipt.

Blender 4.3.2 and the identified FFmpeg build were observed during this
post-merge inspection. They describe the inspection environment, not proven
provenance for the original render. Pull request #112 records the separate full
render and audio-QA validation; this receipt did not reproduce that render.

## Limits

- This is an architectural explanation only. It does not qualify robot motion,
  collision behavior, fabrication, calibration, or autonomous operation.
- Published media includes no vendor source mesh.
- The wider Waveshare URDF redistribution question remains tracked in
  [issue #88](https://github.com/j-webtek/tactevra/issues/88).
- Any later change to a published media byte or its authority manifest must
  update the machine-readable receipt. CI and the Pages build reject drift.
