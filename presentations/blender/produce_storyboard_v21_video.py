"""Assemble the canonical 100-second storyboard render into a reviewable film.

The storyboard JSON owns scene timing, narration, and chapters. Blender owns
the picture. This script owns only deterministic audio, captions, muxing, and
delivery verification so editorial changes do not silently drift across tools.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import struct
import subprocess
import wave
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST_PATH = HERE / "storyboard_v21_shots.json"
DEFAULT_OUT = ROOT / "tmp" / "blender-storyboard-v21"


def timestamp(seconds: float, decimal: str = ".") -> str:
    milliseconds = round(seconds * 1000)
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d}{decimal}{millis:03d}"


def write_text_tracks(manifest: dict, out: Path) -> tuple[Path, Path, Path, Path]:
    srt = out / "tactevra_storyboard_v21.en.srt"
    vtt = out / "tactevra_storyboard_v21.en.vtt"
    chapters_vtt = out / "tactevra_storyboard_v21.chapters.vtt"
    metadata = out / "tactevra_storyboard_v21.chapters.ffmeta"
    srt_blocks: list[str] = []
    vtt_blocks = ["WEBVTT"]
    for cue in manifest["narration"]:
        srt_blocks.append(
            f"{cue['id']}\n{timestamp(cue['start'], ',')} --> "
            f"{timestamp(cue['end'], ',')}\n{cue['text']}"
        )
        vtt_blocks.append(
            f"{timestamp(cue['start'])} --> {timestamp(cue['end'])}\n{cue['text']}"
        )
    srt.write_text("\n\n".join(srt_blocks) + "\n", encoding="utf-8")
    vtt.write_text("\n\n".join(vtt_blocks) + "\n", encoding="utf-8")

    chapter_blocks = ["WEBVTT"]
    ffmeta = [";FFMETADATA1"]
    for chapter in manifest["chapters"]:
        chapter_blocks.append(
            f"{timestamp(chapter['start'])} --> {timestamp(chapter['end'])}\n"
            f"{chapter['label']}"
        )
        ffmeta.extend(
            (
                "[CHAPTER]",
                "TIMEBASE=1/1000",
                f"START={round(chapter['start'] * 1000)}",
                f"END={round(chapter['end'] * 1000)}",
                f"title={chapter['label']}",
            )
        )
    chapters_vtt.write_text("\n\n".join(chapter_blocks) + "\n", encoding="utf-8")
    metadata.write_text("\n".join(ffmeta) + "\n", encoding="utf-8")
    return srt, vtt, chapters_vtt, metadata


def _pulse(t: float, center: float, frequency: float, length: float) -> float:
    local = t - center
    if not 0 <= local <= length:
        return 0.0
    envelope = math.sin(math.pi * local / length) ** 2
    return math.sin(2 * math.pi * frequency * local) * envelope


def write_soundtrack(path: Path, manifest: dict) -> None:
    sample_rate = 48_000
    duration = manifest["duration_seconds"]
    rhythm_contacts = [item["contact_frame"] / manifest["fps"] for item in manifest["rhythm"]["targets"]]
    phone_contacts = [frame / manifest["fps"] for frame in manifest["phone_sequence"]["contact_frames"]]
    send_contact = manifest["phone_sequence"]["send_contact_frame"] / manifest["fps"]
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        block = bytearray()
        for index in range(sample_rate * duration):
            t = index / sample_rate
            root = (55.0, 65.41, 73.42, 61.74)[int(t // 16) % 4]
            reject_silence = 0.0 if 28.0 <= t < 33.0 else 1.0
            breathe = 0.72 + 0.28 * math.sin(2 * math.pi * 0.0625 * t) ** 2
            bed = reject_silence * breathe * (
                0.024 * math.sin(2 * math.pi * root * t)
                + 0.014 * math.sin(2 * math.pi * root * 1.5 * t + 0.6)
                + 0.008 * math.sin(2 * math.pi * root * 2.0 * t + 1.2)
            )
            cue = 0.0
            cue += 0.11 * _pulse(t, 29.2, 145.0, 0.52)  # rejection
            for gate_index, gate_time in enumerate((34.0, 35.0, 36.0, 37.0, 38.0)):
                cue += 0.05 * _pulse(t, gate_time, 520 + gate_index * 65, 0.14)
            cue += 0.10 * _pulse(t, 39.1, 850.0, 0.38)  # first permit
            cue += 0.12 * _pulse(t, 1057 / 24, 1180.0, 0.10)  # first key
            for contact in rhythm_contacts:
                cue += 0.10 * _pulse(t, contact, 1120.0, 0.09)
                cue += 0.04 * _pulse(t, contact + 0.35, 760.0, 0.14)
            for contact in phone_contacts:
                cue += 0.075 * _pulse(t, contact, 920.0, 0.075)
            cue += 0.11 * _pulse(t, send_contact, 1240.0, 0.12)
            for tone in (523.25, 659.25, 783.99):
                cue += 0.038 * _pulse(t, 88.0, tone, 0.62)
            sample = max(-0.92, min(0.92, bed + cue))
            pan = 0.035 * math.sin(2 * math.pi * 0.07 * t)
            block.extend(
                struct.pack(
                    "<hh",
                    int(sample * (1 - pan) * 32767),
                    int(sample * (1 + pan) * 32767),
                )
            )
            if len(block) >= 192_000:
                wav.writeframesraw(block)
                block.clear()
        if block:
            wav.writeframesraw(block)


def media_duration(ffprobe: str, path: Path) -> float:
    result = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(json.loads(result.stdout)["format"]["duration"])


def ensure_voiceover(manifest: dict, out: Path, voice_dir: Path | None) -> Path:
    if voice_dir is not None:
        return voice_dir
    voice_dir = out / "voiceover_v21"
    powershell = shutil.which("pwsh") or shutil.which("powershell")
    if not powershell:
        raise RuntimeError("PowerShell is required for the local review narration")
    subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(HERE / "generate_storyboard_v21_voiceover.ps1"),
            "-OutputDirectory",
            str(voice_dir),
        ],
        check=True,
    )
    return voice_dir


def select_voice_files(manifest: dict, voice_dir: Path) -> list[Path]:
    selected: list[Path] = []
    for cue in manifest["narration"]:
        stem = f"voice_{cue['id']:02d}"
        candidate = next(
            (voice_dir / f"{stem}{suffix}" for suffix in (".wav", ".mp3", ".m4a") if (voice_dir / f"{stem}{suffix}").is_file()),
            None,
        )
        if candidate is None:
            raise FileNotFoundError(f"Missing {stem}.wav/.mp3/.m4a in {voice_dir}")
        selected.append(candidate)
    return selected


def assemble(silent_video: Path, voice_dir: Path | None, out: Path) -> Path:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise RuntimeError("ffmpeg and ffprobe are required")
    out.mkdir(parents=True, exist_ok=True)
    duration = media_duration(ffprobe, silent_video)
    if abs(duration - manifest["duration_seconds"]) > 0.25:
        raise RuntimeError(f"Silent render is {duration:.3f}s; expected 100s")

    srt, _vtt, _chapters_vtt, metadata = write_text_tracks(manifest, out)
    soundtrack = out / "tactevra_storyboard_v21_soundtrack.wav"
    write_soundtrack(soundtrack, manifest)
    voice_dir = ensure_voiceover(manifest, out, voice_dir)
    voices = select_voice_files(manifest, voice_dir)

    inputs = [ffmpeg, "-y", "-i", str(silent_video), "-i", str(soundtrack)]
    for voice in voices:
        inputs.extend(("-i", str(voice)))
    inputs.extend(("-i", str(srt), "-i", str(metadata)))
    audio_graph = ["[1:a]volume=0.70[bed]"]
    voice_labels: list[str] = []
    for input_index, (cue, voice) in enumerate(zip(manifest["narration"], voices), start=2):
        available = cue["end"] - cue["start"] - 0.15
        source_duration = media_duration(ffprobe, voice)
        tempo = max(1.0, source_duration / available)
        if tempo > 2.0:
            raise RuntimeError(f"{voice.name} needs unsupported tempo {tempo:.2f}x")
        label = f"voice{cue['id']}"
        delay = round(cue["start"] * 1000)
        fade_start = max(0.0, available - 0.10)
        audio_graph.append(
            f"[{input_index}:a]aresample=48000,atempo={tempo:.5f},volume=1.0,"
            f"atrim=duration={available:.3f},afade=t=out:st={fade_start:.3f}:d=0.10,"
            f"adelay={delay}|{delay}[{label}]"
        )
        voice_labels.append(f"[{label}]")
    audio_graph.append(
        "".join(voice_labels)
        + f"amix=inputs={len(voice_labels)}:duration=longest:normalize=0,"
        "apad=whole_dur=100,asplit=2[voice_sidechain][voices]"
    )
    audio_graph.append(
        "[bed][voice_sidechain]sidechaincompress=threshold=0.018:ratio=6:"
        "attack=18:release=320[ducked]"
    )
    audio_graph.append(
        "[ducked][voices]amix=inputs=2:duration=longest:normalize=0,"
        "loudnorm=I=-14:TP=-2.0:LRA=7[mix]"
    )
    final = out / "tactevra_storyboard_v21_review.mp4"
    subtitle_index = 2 + len(voices)
    metadata_index = subtitle_index + 1
    subprocess.run(
        inputs
        + [
            "-filter_complex",
            ";".join(audio_graph),
            "-map",
            "0:v:0",
            "-map",
            "[mix]",
            "-map",
            f"{subtitle_index}:0",
            "-map_metadata",
            str(metadata_index),
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "256k",
            "-ar",
            "48000",
            "-c:s",
            "mov_text",
            "-metadata:s:s:0",
            "language=eng",
            "-disposition:s:0",
            "default",
            "-t",
            "100",
            "-movflags",
            "+faststart",
            str(final),
        ],
        check=True,
    )
    poster = out / "tactevra_storyboard_v21_poster.jpg"
    subprocess.run(
        [ffmpeg, "-y", "-ss", "40.05", "-i", str(final), "-frames:v", "1", "-update", "1", "-q:v", "2", str(poster)],
        check=True,
    )
    report = {
        "video": str(final),
        "duration_seconds": media_duration(ffprobe, final),
        "narration_cues": len(manifest["narration"]),
        "chapters": len(manifest["chapters"]),
        "selectable_subtitles": True,
        "poster": str(poster),
        "source_render": str(silent_video),
    }
    (out / "tactevra_storyboard_v21_build.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))
    return final


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--silent-video", type=Path, required=True)
    parser.add_argument("--voice-dir", type=Path)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    assemble(args.silent_video.resolve(), args.voice_dir, args.output_dir.resolve())


if __name__ == "__main__":
    main()
