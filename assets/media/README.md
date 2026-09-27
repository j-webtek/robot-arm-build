# Repository overview media

These files provide the short Tactevra explainer featured near the top of the
repository README:

- `tactevra-overview.mp4` — 1280×720 H.264/AAC delivery file with a selectable
  English subtitle stream;
- `tactevra-overview.en.vtt` — English WebVTT sidecar for players and future
  web surfaces that support external caption tracks;
- `tactevra-overview-poster.jpg` — lightweight linked preview for GitHub and
  clients that do not render an inline video player.

The MP4 subtitle stream is optional rather than burned into the image. Viewers
can enable it in a compatible player, and future translations can be added as
separate `.vtt` files without rerendering the 3D film.

## Rebuild the published files

First create and review the web render documented in
[`presentations/blender/README.md`](../../presentations/blender/README.md).
Then run:

```powershell
& "C:\Program Files\Blender Foundation\Blender 4.3\blender.exe" `
  --background --factory-startup `
  --python presentations/blender/build_workcell_explainer.py -- `
  --publish-homepage-media
```

The publish step requires `ffmpeg` on `PATH`. It copies no vendor source mesh;
it packages the reviewed compact render, captions, and poster only. The film is
an architectural visualization, not robot-motion or fabrication qualification.
