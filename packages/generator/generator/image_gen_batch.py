"""
Generate images for each clip in outputs/plan.json using Automatic1111 WebUI API.
- Uses the plan's per-clip `image_prompt` directly (no fixed art style).
- Writes PNGs to outputs/images/clipN.png
- Keeps a church-safe negative prompt by default.

Prereq:
- Automatic1111 running with --api at http://127.0.0.1:7860
- A 16:9 capable SD model (SDXL recommended) selected in WebUI.

Usage:
  python image_gen_batch.py
  python image_gen_batch.py --api http://127.0.0.1:7860 --w 1024 --h 576
  python image_gen_batch.py --style "soft cinematic lighting, natural colors"   # optional
"""

from __future__ import annotations
import argparse
import json
from pathlib import Path
import requests
import sys
import time
import re
import base64

DEFAULT_PLAN = Path("outputs/plan.json")
DEFAULT_OUTDIR = Path("outputs/images")
DEFAULT_API = "http://0.0.0.0:7861"

# Negative prompt to keep it church-safe and clean
NEGATIVE_PROMPT = (
    "nudity, nsfw, sexual, obscene, gore, graphic violence, blood, "
    "text, typography, watermark, logo, signature, "
    "low quality, blurry, deformed, extra fingers, extra limbs, mutated, disfigured, "
    "jpeg artifacts, cartoon, anime, meme"
)

# Simple content filter to avoid unsafe scenes before sending to the model
UNSAFE_PATTERNS = [
    r"\bnude\b", r"\bnudity\b", r"\bnsfw\b", r"\bgore\b", r"\bgraphic\b", r"\bviolence\b"
]


def is_safe(prompt: str) -> bool:
    """Reject obviously unsafe prompts."""
    p = (prompt or "").lower()
    return not any(re.search(rx, p) for rx in UNSAFE_PATTERNS)


def build_prompt(base: str, style_suffix: str | None) -> str:
    """
    Combine the plan's clip image_prompt with optional user-provided style.
    Always discourage embedded text.
    """
    base = (base or "").strip().rstrip(".")
    tail = "no text, no typography"
    if style_suffix:
        style_suffix = style_suffix.strip().rstrip(".")
        return f"{base}. {style_suffix}. {tail}"
    return f"{base}. {tail}"


def txt2img(
    api_base: str,
    prompt: str,
    negative_prompt: str,
    width: int,
    height: int,
    steps: int = 28,
    cfg: float = 6.5,
    sampler: str = "DPM++ 2M Karras",
    seed: int = -1,
):
    """
    Call Automatic1111 /sdapi/v1/txt2img and return the first image bytes (PNG).
    """
    url = f"{api_base}/sdapi/v1/txt2img"
    payload = {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "width": width,
        "height": height,
        "steps": steps,
        "cfg_scale": cfg,
        "sampler_name": sampler,
        "seed": seed,
        "restore_faces": False,
        "enable_hr": False,
        "save_images": False,
        "batch_size": 1,
        "n_iter": 1,
    }
    r = requests.post(url, json=payload, timeout=300)
    r.raise_for_status()
    data = r.json()
    if "images" not in data or not data["images"]:
        raise RuntimeError(f"No image returned: {data}")
    img_b64 = data["images"][0]
    return base64.b64decode(img_b64)


def load_plan(plan_path: Path) -> dict:
    with plan_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate images from plan.json via Automatic1111 API")
    ap.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    ap.add_argument("--outdir", type=Path, default=DEFAULT_OUTDIR)
    ap.add_argument("--api", type=str, default=DEFAULT_API)
    ap.add_argument("--w", type=int, default=1024)
    ap.add_argument("--h", type=int, default=576)
    ap.add_argument("--steps", type=int, default=28)
    ap.add_argument("--cfg", type=float, default=6.5)
    ap.add_argument("--sampler", type=str, default="DPM++ 2M Karras")
    ap.add_argument("--style", type=str, default="", help="Optional style suffix to append to prompts")
    args = ap.parse_args()

    if not args.plan.exists():
        print(f"Missing plan: {args.plan}", file=sys.stderr)
        sys.exit(1)
    args.outdir.mkdir(parents=True, exist_ok=True)

    plan = load_plan(args.plan)
    clips = plan.get("clips", [])
    if not clips:
        print("No clips in plan.", file=sys.stderr)
        sys.exit(1)

    style_suffix = args.style if args.style.strip() else None

    print(f"API: {args.api}")
    generated = 0
    for clip in clips:
        idx = clip.get("index")
        base_prompt = clip.get("image_prompt", "")
        if not base_prompt:
            print(f"[clip{idx}] empty image_prompt; skipping", file=sys.stderr)
            continue
        if not is_safe(base_prompt):
            print(f"[clip{idx}] skipped due to unsafe prompt content")
            continue

        full_prompt = build_prompt(base_prompt, style_suffix)
        print(f"[{idx}/{len(clips)}] {full_prompt[:120]}...")

        # optional: deterministic seed per clip for reproducibility
        seed = -1  # or: 1000 + int(idx)

        try:
            png_bytes = txt2img(
                api_base=args.api,
                prompt=full_prompt,
                negative_prompt=NEGATIVE_PROMPT,
                width=args.w,
                height=args.h,
                steps=args.steps,
                cfg=args.cfg,
                sampler=args.sampler,
                seed=seed,
            )
        except requests.HTTPError as e:
            print(f"[clip{idx}] HTTP error: {e}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"[clip{idx}] generation failed: {e}", file=sys.stderr)
            sys.exit(1)

        out_path = args.outdir / f"clip{idx}.png"
        out_path.write_bytes(png_bytes)
        generated += 1
        time.sleep(0.2)  # gentle pacing

    print(f"Done. Wrote {generated} images → {args.outdir.resolve()}")


if __name__ == "__main__":
    main()
