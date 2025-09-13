"""
Compose images + WAVs into MP4 with padded timing.

Policy
- Ignore plan start/end. Derive each segment duration from:
    seg_dur = lead_sec + audio_dur + trail_sec
- Speech starts after a silent lead-in so each slide breathes at start and end.
- If audio missing: seg_dur = max(min_dur_sec, lead_sec + trail_sec).
- Write SRT using the cumulative timeline (not plan times).
- Supports Plan v1 ('dialogue') and v2 ('dialogue_text' and optional 'subtitle').

Run:
  python video_compose.py
  python video_compose.py --plan outputs/plan.json --imgdir outputs/images --audiodir outputs/audio --out outputs/video/final.mp4 --lead 1.5 --trail 2.0 --min 6.0
"""

from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
import numpy as np

from moviepy.editor import (
    ImageClip, AudioFileClip, concatenate_videoclips, concatenate_audioclips
)
from moviepy.audio.AudioClip import AudioArrayClip

DEFAULT_PLAN = Path("outputs/plan.json")
DEFAULT_IMGDIR = Path("outputs/images")
DEFAULT_AUDIODIR = Path("outputs/audio")
DEFAULT_OUT = Path("outputs/video/final.mp4")

DEFAULT_SR = 24000   # Piper WAVs default
FPS = 30

# ---------- Plan helpers ----------
def load_plan(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Cannot read plan: {e}", file=sys.stderr); sys.exit(1)

def clip_text_for_caption(clip: dict) -> str:
    """Prefer 'subtitle'; else v2 'dialogue_text'; else v1 'dialogue'."""
    for key in ("subtitle", "dialogue_text", "dialogue"):
        val = (clip.get(key) or "").strip()
        if val:
            return " ".join(val.split())
    return ""

# ---------- SRT helpers ----------
def srt_escape(text: str) -> str:
    return (text or "").replace("\n", " ").strip()

def to_srt_timestamp(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    hh = ms // (3600 * 1000); ms %= 3600 * 1000
    mm = ms // (60 * 1000);   ms %= 60 * 1000
    ss = ms // 1000;          ms %= 1000
    return f"{hh:02d}:{mm:02d}:{ss:02d},{ms:03d}"

def write_srt_from_segments(segments: list[tuple[int,float,float,str]], srt_path: Path) -> None:
    lines = []
    for idx, start, end, text in segments:
        lines.append(f"{idx}")
        lines.append(f"{to_srt_timestamp(start)} --> {to_srt_timestamp(end)}")
        lines.append(srt_escape(text))
        lines.append("")
    srt_path.parent.mkdir(parents=True, exist_ok=True)
    srt_path.write_text("\n".join(lines), encoding="utf-8")

# ---------- Audio helpers ----------
def make_silence_array(duration: float, fps: int, nchannels: int) -> AudioArrayClip:
    n = max(1, int(round(duration * fps)))
    arr = np.zeros((n, nchannels), dtype=np.float32)
    return AudioArrayClip(arr, fps=fps)

def build_padded_audio(wav_path: Path, lead: float, trail: float, min_dur: float):
    """
    Returns (audio_clip_with_lead_trail, total_duration_float).
    If no audio, returns silence of max(min_dur, lead+trail) at DEFAULT_SR mono.
    """
    if wav_path.exists():
        a = AudioFileClip(str(wav_path))
        fps = int(a.fps)
        nch = int(getattr(a, "nchannels", 1))
        core = a
        if lead > 0:
            core = concatenate_audioclips([make_silence_array(lead, fps, nch), core])
        if trail > 0:
            core = concatenate_audioclips([core, make_silence_array(trail, fps, nch)])
        return core, float(core.duration)
    else:
        dur = max(min_dur, lead + trail)
        silent = make_silence_array(dur, fps=DEFAULT_SR, nchannels=1)
        return silent, dur

# ---------- Build video ----------
def build_video(plan_path: Path, img_dir: Path, aud_dir: Path, out_path: Path,
                lead_sec: float, trail_sec: float, min_dur_sec: float) -> None:
    plan = load_plan(plan_path)
    clips = plan.get("clips", [])
    if not clips:
        print("No clips in plan.", file=sys.stderr); sys.exit(1)

    segments_for_srt: list[tuple[int,float,float,str]] = []
    segs = []
    t_cursor = 0.0

    for c in clips:
        idx = int(c["index"])
        img_path = img_dir / f"clip{idx}.png"
        wav_path = aud_dir / f"clip{idx}.wav"

        if not img_path.exists():
            print(f"Missing image: {img_path}", file=sys.stderr); sys.exit(1)

        a, seg_dur = build_padded_audio(
            wav_path=wav_path,
            lead=lead_sec,
            trail=trail_sec,
            min_dur=min_dur_sec,
        )

        v = ImageClip(str(img_path), duration=seg_dur).set_fps(FPS).set_audio(a)
        segs.append(v)

        start = t_cursor
        end = t_cursor + seg_dur
        text = clip_text_for_caption(c)
        segments_for_srt.append((idx, start, end, text))
        t_cursor = end

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
    write_srt_from_segments(segments_for_srt, srt_path)
    print(f"Wrote: {out_path}")
    print(f"Wrote: {srt_path}")

def main():
    ap = argparse.ArgumentParser(description="Compose images+audio into MP4 with padded timing")
    ap.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    ap.add_argument("--imgdir", type=Path, default=DEFAULT_IMGDIR)
    ap.add_argument("--audiodir", type=Path, default=DEFAULT_AUDIODIR)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--lead", type=float, default=1.5, help="Seconds of silence before speech")
    ap.add_argument("--trail", type=float, default=2.0, help="Seconds of silence after speech")
    ap.add_argument("--min", dest="min_dur", type=float, default=6.0, help="Minimum segment duration if audio is short/missing")
    args = ap.parse_args()

    build_video(args.plan, args.imgdir, args.audiodir, args.out, args.lead, args.trail, args.min_dur)

if __name__ == "__main__":
    main()
