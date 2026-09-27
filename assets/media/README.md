# Repository overview media

These files provide the short Tactevra explainer featured near the top of the
repository README:

- `tactevra-overview.mp4` — 1920×1080 H.264/AAC narrated delivery file with a
  selectable English subtitle stream;
- `tactevra-overview.en.vtt` — English WebVTT sidecar for players and future
  web surfaces that support external caption tracks;
- `tactevra-overview-poster.jpg` — lightweight linked preview for GitHub and
  clients that do not render an inline video player.

The README poster opens the project player at
`https://j-webtek.github.io/tactevra/`. GitHub's repository file viewer does not
reliably preview MP4 files on mobile, so the Pages player is the supported
playback surface. It serves the same checked-in assets with the correct media
type, native controls, inline mobile playback, and a WebVTT caption selector.

The approximately 77-second MP4 includes an optional subtitle stream rather
than burned-in captions. Viewers can enable it in a compatible player, and
future translations can be added as separate `.vtt` files without rerendering
the 3D film.

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
it packages the reviewed web render, captions, and poster only. The main film
includes narration; the build also creates a square social derivative with
burned-in captions below ignored `tmp/`. The film is an architectural
visualization, not robot-motion or fabrication qualification.
