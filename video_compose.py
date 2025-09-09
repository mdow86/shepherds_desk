"""
Stitches plan.json + generated images + wavs into a single MP4.

- Supports Plan v1 (fixed 10s clips, key 'dialogue') and Plan v2 (variable durations with
  'dialogue_text' and optional 'verse{ref,text}', 'mode').
- For each clip, the target slot is (end_sec - start_sec). If the audio is longer than the slot,
  we extend the image duration to match audio.
- Writes subtitles.srt from subtitle (if provided) else from spoken text.
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
    AudioClip, concatenate_audioclips
)
from moviepy.audio.AudioClip import AudioArrayClip

DEFAULT_PLAN = Path("outputs/plan.json")
DEFAULT_IMGDIR = Path("outputs/images")
DEFAULT_AUDIODIR = Path("outputs/audio")
DEFAULT_OUT = Path("outputs/video/final.mp4")

DEFAULT_SR = 24000  # Piper default sample rate
FPS = 30


# ---------- Plan helpers ----------
def load_plan(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Cannot read plan: {e}", file=sys.stderr)
        sys.exit(1)


def get_clip_times(clip: dict, default_index: int) -> tuple[float, float]:
    """
    v2: use start_sec/end_sec.
    v1 fallback: derive 10s slots based on index (1→[0,10), 2→[10,20), ...).
    """
    if "start_sec" in clip and "end_sec" in clip:
        return float(clip["start_sec"]), float(clip["end_sec"])
    start = (default_index - 1) * 10.0
    end = default_index * 10.0
    return start, end


def clip_spoken_text(clip: dict) -> str:
    """
    v2: combine verse.text (+ref) + dialogue_text for captions if no 'subtitle'.
    v1: use 'dialogue'.
    """
    if "dialogue_text" in clip or "verse" in clip:
        parts = []
        verse = clip.get("verse") or None
        if verse and verse.get("text"):
            ref = verse.get("ref", "").strip()
            parts.append(f"{verse['text']} ({ref})." if ref else verse["text"])
        if clip.get("dialogue_text"):
            parts.append(clip["dialogue_text"])
        return " ".join(" ".join(parts).split())
    # v1
    return " ".join((clip.get("dialogue", "") or "").split())


def clip_subtitle(clip: dict) -> str:
    """Prefer explicit subtitle if present, else spoken text."""
    sub = clip.get("subtitle")
    if isinstance(sub, str) and sub.strip():
        return " ".join(sub.strip().split())
    return clip_spoken_text(clip)


# ---------- SRT helpers ----------
def srt_escape(text: str) -> str:
    return (text or "").replace("\n", " ").strip()


def to_srt_timestamp(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    hh = ms // (3600 * 1000); ms %= 3600 * 1000
    mm = ms // (60 * 1000);   ms %= 60 * 1000
    ss = ms // 1000;          ms %= 1000
    return f"{hh:02d}:{mm:02d}:{ss:02d},{ms:03d}"


def write_srt(plan: dict, srt_path: Path) -> None:
    lines = []
    clips = plan.get("clips", [])
    for clip in clips:
        idx = int(clip["index"])
        start, end = get_clip_times(clip, idx)
        text = srt_escape(clip_subtitle(clip))
        lines.append(f"{idx}")
        lines.append(f"{to_srt_timestamp(start)} --> {to_srt_timestamp(end)}")
        lines.append(text)
        lines.append("")  # blank line
    srt_path.parent.mkdir(parents=True, exist_ok=True)
    srt_path.write_text("\n".join(lines), encoding="utf-8")


# ---------- Audio helpers ----------
def make_silence_array(duration: float, fps: int, nchannels: int) -> AudioArrayClip:
    """Return digital silence with shape (n_samples, nchannels)."""
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
        return make_silence_array(slot_dur, fps=DEFAULT_SR, nchannels=1)


# ---------- Build video ----------
def build_video(plan_path: Path, img_dir: Path, aud_dir: Path, out_path: Path) -> None:
    plan = load_plan(plan_path)
    clips = plan.get("clips", [])
    if not clips:
        print("No clips in plan.", file=sys.stderr)
        sys.exit(1)

    segs = []
    for c in clips:
        idx = int(c["index"])
        img_path = img_dir / f"clip{idx}.png"
        wav_path = aud_dir / f"clip{idx}.wav"

        if not img_path.exists():
            print(f"Missing image: {img_path}", file=sys.stderr)
            sys.exit(1)

        # Planned slot duration
        start, end = get_clip_times(c, idx)
        slot_dur = max(0.01, float(end - start))

        # Load/fit audio to slot
        a = fit_audio_to_slot(wav_path, slot_dur)

        # Image duration extends to audio if audio is longer than slot
        dur = max(slot_dur, getattr(a, "duration", slot_dur))

        v = ImageClip(str(img_path), duration=dur).set_fps(FPS).set_audio(a)
        segs.append(v)

    final = concatenate_videoclips(segs, method="compose")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    final.write_videofile(
        str(out_path),
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        threads=0,
        preset="medium",
        bitrate="4000k"
    )

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
