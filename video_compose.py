"""
Stitches plan.json + generated images + wavs into a single MP4.
- 6 clips, each 10s (from plan invariants).
- Pads/trim audio per clip to 10.0s.
- Writes subtitles.srt from dialogue.
- Outputs to outputs/video/final.mp4

Run:
  python video_compose.py
Optional:
  python video_compose.py --plan outputs/plan.json --imgdir outputs/images --audiodir outputs/audio --out outputs/video/final.mp4
"""

from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
import numpy as np

from moviepy.editor import (
    ImageClip, AudioFileClip, concatenate_videoclips,
    CompositeAudioClip, AudioClip, concatenate_audioclips
)
from moviepy.audio.AudioClip import AudioArrayClip

DEFAULT_PLAN = Path("outputs/plan.json")
DEFAULT_IMGDIR = Path("outputs/images")
DEFAULT_AUDIODIR = Path("outputs/audio")
DEFAULT_OUT = Path("outputs/video/final.mp4")
DEFAULT_SR = 24000  # Piper default sample rate

FPS = 30
CLIP_DUR = 10.0  # seconds per segment

def load_plan(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Cannot read plan: {e}", file=sys.stderr); sys.exit(1)

def srt_escape(text: str) -> str:
    # Minimal cleanup for SRT
    return text.replace("\n", " ").strip()

def to_srt_timestamp(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    hh = ms // (3600 * 1000); ms %= 3600 * 1000
    mm = ms // (60 * 1000);   ms %= 60 * 1000
    ss = ms // 1000;          ms %= 1000
    return f"{hh:02d}:{mm:02d}:{ss:02d},{ms:03d}"

def write_srt(plan: dict, srt_path: Path) -> None:
    lines = []
    for clip in plan["clips"]:
        idx = clip["index"]
        start = float(clip["start_sec"])
        end = float(clip["end_sec"])
        dlg = srt_escape(clip["dialogue"])
        lines.append(f"{idx}")
        lines.append(f"{to_srt_timestamp(start)} --> {to_srt_timestamp(end)}")
        lines.append(dlg)
        lines.append("")  # blank line
    srt_path.parent.mkdir(parents=True, exist_ok=True)
    srt_path.write_text("\n".join(lines), encoding="utf-8")

def make_silence_array(duration: float, fps: int, nchannels: int) -> AudioArrayClip:
    """
    Return true digital silence with the right shape: (n_samples, nchannels).
    """
    n = max(1, int(round(duration * fps)))
    arr = np.zeros((n, nchannels), dtype=np.float32)
    return AudioArrayClip(arr, fps=fps)

def fit_audio_to_slot(wav_path: Path, slot_dur: float) -> AudioClip:
    """
    If audio exists: trim or right-pad with silence to slot_dur.
    If missing: pure silence with DEFAULT_SR mono.
    """
    if wav_path.exists():
        a = AudioFileClip(str(wav_path))
        fps = int(a.fps)
        nch = int(getattr(a, "nchannels", 1))
        if a.duration > slot_dur:
            return a.subclip(0, slot_dur)
        if a.duration < slot_dur:
            pad = make_silence_array(slot_dur - a.duration, fps=fps, nchannels=nch)
            return concatenate_audioclips([a, pad])
        return a
    else:
        # no audio → mono silence
        return make_silence_array(slot_dur, fps=DEFAULT_SR, nchannels=1)
def build_video(plan_path: Path, img_dir: Path, aud_dir: Path, out_path: Path) -> None:
    plan = load_plan(plan_path)
    clips = plan.get("clips", [])
    if not clips:
        print("No clips in plan.", file=sys.stderr); sys.exit(1)

    # Build per-clip video segments
    segs = []
    for c in clips:
        idx = c["index"]
        img_path = img_dir / f"clip{idx}.png"
        wav_path = aud_dir / f"clip{idx}.wav"

        if not img_path.exists():
            print(f"Missing image: {img_path}", file=sys.stderr); sys.exit(1)

        # Image → 10s video
        v = ImageClip(str(img_path), duration=CLIP_DUR).set_fps(FPS)

        # Audio → fit to 10s
        a = fit_audio_to_slot(wav_path, CLIP_DUR)
        v = v.set_audio(a)

        segs.append(v)

    # Concatenate all
    final = concatenate_videoclips(segs, method="compose")

    # Ensure output dir
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Write MP4 (H.264 + AAC). moviepy picks imageio-ffmpeg by default.
    final.write_videofile(
        str(out_path),
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        threads=0,
        preset="medium",
        bitrate="4000k"
    )

    # Subtitles sidecar
    srt_path = out_path.with_suffix(".srt")
    write_srt(plan, srt_path)
    print(f"Wrote: {out_path}")
    print(f"Wrote: {srt_path}")

def main():
    ap = argparse.ArgumentParser(description="Compose images+audio into a single MP4 from plan.json")
    ap.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    ap.add_argument("--imgdir", type=Path, default=DEFAULT_IMGDIR)
    ap.add_argument("--audiodir", type=Path, default=DEFAULT_AUDIODIR)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    build_video(args.plan, args.imgdir, args.audiodir, args.out)

if __name__ == "__main__":
    main()
