"""
End-to-end runner:
1) Call Gloo to produce outputs/plan.json
2) Generate WAVs with Piper from plan.json
3) Generate PNGs with SD WebUI API from plan.json
4) Compose final MP4 (+ SRT)

Usage:
  python orchestrate.py
Options:
  python orchestrate.py --skip-gloo --skip-tts --skip-img --skip-video
  python orchestrate.py --api http://127.0.0.1:7860 --model "D:\\tools\\piper\\models\\en_GB-northern_english_male-medium.onnx" --piper "D:\\tools\\piper\\piper.exe"

Exit codes:
  0 success, nonzero on first failed stage.
"""

from __future__ import annotations
import argparse
import subprocess
from pathlib import Path
import sys
import time
import json

ROOT = Path(__file__).parent
PLAN = ROOT / "outputs" / "plan.json"

# Defaults; override with CLI
DEFAULT_PIPER_EXE = r"D:\dev\windows\gloo\tools\piper\piper.exe"
DEFAULT_PIPER_MODEL = r"D:\dev\windows\gloo\tools\piper\models\en_GB-alan-low.onnx"
DEFAULT_SD_API = "http://127.0.0.1:7860"

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
    args = ap.parse_args()

    # 1) Gloo → plan.json
    if not args.skip_gloo:
        run_step("GLOO", [sys.executable, str(ROOT / "api_call.py")])
    else:
        print("[GLOO] skipped")
    if not exists_plan():
        print("Missing outputs/plan.json; cannot continue.")
        sys.exit(2)
    print(f"[PLAN] {PLAN} — Title: {load_title()}")

    # 2) TTS (Piper)
    if not args.skip_tts:
        run_step(
            "TTS",
            [
                sys.executable,
                str(ROOT / "tts_piper_batch.py"),
                "--exe", args.piper,
                "--model", args.model,
                "--outdir", str(ROOT / "outputs" / "audio"),
                "--plan", str(PLAN),
            ],
        )
    else:
        print("[TTS] skipped")

    # 3) Images (Automatic1111)
    if not args.skip_img:
        run_step(
            "IMG",
            [
                sys.executable,
                str(ROOT / "image_gen_batch.py"),
                "--api", args.api,
                "--w", str(args.w),
                "--h", str(args.h),
                "--steps", str(args.steps),
                "--cfg", str(args.cfg),
                "--sampler", args.sampler,
                "--plan", str(PLAN),
                "--outdir", str(ROOT / "outputs" / "images"),
            ],
        )
    else:
        print("[IMG] skipped")

    # 4) Video compose
    if not args.skip_video:
        run_step(
            "VIDEO",
            [
                sys.executable,
                str(ROOT / "video_compose.py"),
                "--plan", str(PLAN),
                "--imgdir", str(ROOT / "outputs" / "images"),
                "--audiodir", str(ROOT / "outputs" / "audio"),
                "--out", str(ROOT / "outputs" / "video" / "final.mp4"),
            ],
        )
    else:
        print("[VIDEO] skipped")

    print("DONE")

if __name__ == "__main__":
    main()
