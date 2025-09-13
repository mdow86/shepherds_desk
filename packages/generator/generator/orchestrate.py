"""
End-to-end runner:
1) Gloo -> outputs/plan.json
2) Piper TTS -> outputs/audio/clipN.wav
3) SD WebUI -> outputs/images/clipN.png
4) Compose -> outputs/video/final.mp4 (+ .srt)

Usage:
  python orchestrate.py
  python orchestrate.py --skip-gloo --skip-tts --skip-img --skip-video
  python orchestrate.py --api http://127.0.0.1:7860 --piper "D:\\dev\\windows\\gloo\\packages\\generator\\tools\\piper\\piper.exe" --model "D:\\dev\\windows\\gloo\\packages\\generator\\tools\\piper\\models\\en_GB-alan-low.onnx"
"""

from __future__ import annotations
import argparse
import subprocess
from pathlib import Path
import sys
import time
import json

# ---------- Paths ----------
# Prefer shared OUTPUTS so this stays in sync with api_call.py
try:
    from .paths import OUTPUTS
    PLAN = OUTPUTS / "plan.json"
except Exception:
    ROOT = Path(__file__).resolve().parents[2]   # …/packages/generator
    OUTPUTS = ROOT / "outputs"
    PLAN = OUTPUTS / "plan.json"

PY = sys.executable

# ---------- Defaults ----------
DEFAULT_PIPER_EXE = str(Path(__file__).parent / "tools" / "piper" / "piper.exe")
DEFAULT_PIPER_MODEL = str(Path(__file__).parent / "tools" / "piper" / "models" / "en_GB-alan-low.onnx")
DEFAULT_SD_API = "http://127.0.0.1:7861"  # your working port


# ---------- Helpers ----------
def exists_plan() -> bool:
    return PLAN.exists() and PLAN.stat().st_size > 2

def load_title() -> str:
    try:
        data = json.loads(PLAN.read_text(encoding="utf-8"))
        return data.get("title", "")
    except Exception:
        return ""

def run_step(name: str, cmd: list[str]) -> None:
    t0 = time.time()
    print(f"[{name}] → {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        dt = time.time() - t0
        print(f"[{name}] FAILED in {dt:.1f}s (exit {e.returncode})")
        sys.exit(e.returncode)
    dt = time.time() - t0
    print(f"[{name}] OK in {dt:.1f}s")

def run_module(modname: str, args: list[str]) -> None:
    run_step(modname.split('.')[-1].upper(), [PY, "-m", modname, *args])

# ---------- Main ----------
def main():
    ap = argparse.ArgumentParser(description="Pipeline orchestrator")
    ap.add_argument("--skip-gloo", action="store_true")
    ap.add_argument("--skip-tts", action="store_true")
    ap.add_argument("--skip-img", action="store_true")
    ap.add_argument("--skip-video", action="store_true")

    ap.add_argument("--piper", default=DEFAULT_PIPER_EXE, help="Path to piper.exe")
    ap.add_argument("--model", default=DEFAULT_PIPER_MODEL, help="Path to Piper .onnx")
    ap.add_argument("--api", default=DEFAULT_SD_API, help="Stable Diffusion WebUI base URL")

    ap.add_argument("--w", type=int, default=1024, help="Image width")
    ap.add_argument("--h", type=int, default=576, help="Image height")
    ap.add_argument("--steps", type=int, default=28)
    ap.add_argument("--cfg", type=float, default=6.5)
    ap.add_argument("--sampler", default="DPM++ 2M Karras")

    # pass through to video_compose.py
    ap.add_argument("--lead", type=float, default=1.5)
    ap.add_argument("--trail", type=float, default=2.0)
    ap.add_argument("--min", dest="min_dur", type=float, default=6.0)

    args = ap.parse_args()

    # Ensure output dirs exist
    (OUTPUTS / "audio").mkdir(parents=True, exist_ok=True)
    (OUTPUTS / "images").mkdir(parents=True, exist_ok=True)
    (OUTPUTS / "video").mkdir(parents=True, exist_ok=True)

    # 1) Gloo -> plan.json
    if not args.skip_gloo:
        run_module("generator.api_call", [])
    else:
        print("[GLOO] skipped")

    if not exists_plan():
        print(f"Missing plan: {PLAN}; cannot continue.")
        sys.exit(2)

    print(f"[PLAN] {PLAN} — Title: {load_title()}")

    # 2) TTS
    if not args.skip_tts:
        run_module(
            "generator.tts_piper_batch",
            [
                "--exe", args.piper,
                "--model", args.model,
                "--outdir", str(OUTPUTS / "audio"),
                "--plan", str(PLAN),
            ],
        )
    else:
        print("[TTS] skipped")

    # 3) Images
    if not args.skip_img:
        run_module(
            "generator.image_gen_batch",
            [
                "--api", args.api,
                "--w", str(args.w),
                "--h", str(args.h),
                "--steps", str(args.steps),
                "--cfg", str(args.cfg),
                "--sampler", args.sampler,
                "--plan", str(PLAN),
                "--outdir", str(OUTPUTS / "images"),
            ],
        )
    else:
        print("[IMG] skipped")

    # 4) Video
    if not args.skip_video:
        run_module(
            "generator.video_compose",
            [
                "--plan", str(PLAN),
                "--imgdir", str(OUTPUTS / "images"),
                "--audiodir", str(OUTPUTS / "audio"),
                "--out", str(OUTPUTS / "video" / "final.mp4"),
                "--lead", str(args.lead),
                "--trail", str(args.trail),
                "--min", str(args.min_dur),
            ],
        )
    else:
        print("[VIDEO] skipped")

    print("DONE")

if __name__ == "__main__":
    main()
