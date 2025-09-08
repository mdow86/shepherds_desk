"""
Pure mappers from plan → downstream job payloads.
No network calls here. Safe to unit-test.
"""

from __future__ import annotations
from typing import List, Dict, Any

def plan_to_image_jobs(plan: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Map each clip's image_prompt into a simple image job spec.
    """
    jobs = []
    for clip in plan["clips"]:
        jobs.append({
            "scene_id": f"clip{clip['index']}",
            "prompt": f"{clip['image_prompt']}, aspect 16:9, cinematic",
            "aspect": "16:9"
        })
    return jobs

def plan_to_tts_jobs(plan: Dict[str, Any], voice: str = "default") -> List[Dict[str, str]]:
    """
    Map each clip's dialogue into a TTS job. The line_id matches the clip index.
    """
    jobs = []
    for clip in plan["clips"]:
        jobs.append({
            "line_id": f"clip{clip['index']}",
            "voice": voice,
            "text": clip["dialogue"]
        })
    return jobs

def summarize_jobs(image_jobs, tts_jobs) -> str:
    """
    Short summary string for logging or CLI output.
    """
    return f"images={len(image_jobs)}, tts_lines={len(tts_jobs)}"
