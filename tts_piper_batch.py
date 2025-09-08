"""
Generate TTS WAV files from the validated plan.json using Piper on Windows.

Requirements:
- You already have Piper extracted, e.g. D:\tools\piper\piper.exe
- You downloaded a voice model (.onnx) and its matching .onnx.json

Usage:
  python tts_piper_batch.py
Optional:
  python tts_piper_batch.py --plan outputs/plan.json --exe "D:\\tools\\piper\\piper.exe" --model "D:\\tools\\piper\\models\\en_GB-northern_english_male-medium.onnx" --outdir outputs/audio
"""

from __future__ import annotations
import argparse
import json
import subprocess
from pathlib import Path
import sys

# --- Defaults: edit if you want hard-coded paths ---
DEFAULT_PLAN = Path("outputs/plan.json")
DEFAULT_PIPER_EXE = Path(r"D:\dev\windows\gloo\tools\piper\piper.exe")
DEFAULT_MODEL = Path(r"D:\dev\windows\gloo\tools\piper\models\en_GB-alan-low.onnx")
DEFAULT_OUTDIR = Path("outputs/audio")


def run_piper(text: str, exe: Path, model: Path, wav_out: Path) -> None:
    """
    Call Piper with the given text → write to wav_out.
    We pass text via stdin to avoid shell quoting issues.
    """
    # Ensure parent dir exists
    wav_out.parent.mkdir(parents=True, exist_ok=True)

    # Piper CLI:
    #   piper.exe -m <model.onnx> -f <output.wav>
    cmd = [str(exe), "-m", str(model), "-f", str(wav_out)]

    # stdin is the text bytes; check=True raises if Piper returns non-zero.
    subprocess.run(cmd, input=text.encode("utf-8"), check=True)


def load_plan(plan_path: Path) -> dict:
    """
    Load the JSON plan file that api_call.py wrote after validation.
    """
    try:
        with plan_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Plan not found: {plan_path}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Invalid JSON in plan: {e}", file=sys.stderr)
        sys.exit(1)


def sanitize_dialogue(text: str) -> str:
    """
    Minimal cleanup before TTS. Keep it simple for MVP.
    - Strip leading/trailing spaces.
    - Replace weird newlines with spaces.
    You can expand this later (e.g., remove emojis, enforce punctuation).
    """
    return " ".join(text.strip().split())


def main() -> None:
    ap = argparse.ArgumentParser(description="Batch-generate WAV files from plan.json using Piper")
    ap.add_argument("--plan", type=Path, default=DEFAULT_PLAN, help="Path to plan.json")
    ap.add_argument("--exe", type=Path, default=DEFAULT_PIPER_EXE, help="Path to piper.exe")
    ap.add_argument("--model", type=Path, default=DEFAULT_MODEL, help="Path to .onnx voice model")
    ap.add_argument("--outdir", type=Path, default=DEFAULT_OUTDIR, help="Output directory for WAV files")
    args = ap.parse_args()

    # Basic checks
    if not args.exe.exists():
        print(f"piper.exe not found: {args.exe}", file=sys.stderr)
        sys.exit(1)
    if not args.model.exists():
        print(f"Voice model not found: {args.model}", file=sys.stderr)
        sys.exit(1)

    plan = load_plan(args.plan)
    clips = plan.get("clips", [])
    if not clips:
        print("Plan has no clips.", file=sys.stderr)
        sys.exit(1)

    # Sequential generation. Simple and predictable.
    generated = []
    for clip in clips:
        idx = clip.get("index")
        dialogue = sanitize_dialogue(clip.get("dialogue", ""))
        if not dialogue:
            print(f"Clip {idx}: empty dialogue; skipping.", file=sys.stderr)
            continue

        # Name files deterministically: clip1.wav, clip2.wav, ...
        wav_path = args.outdir / f"clip{idx}.wav"

        # Optional: print progress
        print(f"[{idx}/{len(clips)}] TTS → {wav_path.name}")
        try:
            run_piper(dialogue, args.exe, args.model, wav_path)
            generated.append(wav_path)
        except subprocess.CalledProcessError as e:
            print(f"Clip {idx}: Piper failed with exit code {e.returncode}", file=sys.stderr)
            sys.exit(e.returncode)

    # Summary
    if generated:
        print(f"Done. Wrote {len(generated)} files → {args.outdir.resolve()}")
    else:
        print("No files generated.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
