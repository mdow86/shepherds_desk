"""
Utilities to parse and validate model output.
- Ensures strict JSON
- Validates against JSON Schema
- Enforces timing and indexing invariants
"""

from __future__ import annotations
import json
from pathlib import Path
from jsonschema import Draft7Validator

def load_schema(schema_path: Path) -> dict:
    with schema_path.open("r", encoding="utf-8") as f:
        return json.load(f)

def parse_and_validate(raw_text: str, schema: dict) -> dict:
    """
    Raises ValueError on any issue. Returns parsed dict on success.
    """
    # Trim whitespace. Model output should be pure JSON.
    s = raw_text.strip()

    # Parse JSON strictly.
    try:
        data = json.loads(s)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e.msg} at pos {e.pos}") from e

    # Validate against schema.
    validator = Draft7Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda e: e.path)
    if errors:
        msgs = []
        for e in errors:
            path = "/".join(map(str, e.path)) or "(root)"
            msgs.append(f"{path}: {e.message}")
        raise ValueError("Schema validation failed: " + " | ".join(msgs))

    # Custom invariants: exactly 6 clips, 10s each, sequential indices.
    clips = data.get("clips", [])
    if len(clips) != 6:
        raise ValueError("Must have exactly 6 clips")

    for i, c in enumerate(clips, start=1):
        if c["index"] != i:
            raise ValueError(f"clips[{i-1}].index must be {i}")
        dur = c["end_sec"] - c["start_sec"]
        if abs(dur - 10) > 1e-6:
            raise ValueError(f"clips[{i-1}] must be 10 seconds long")
        if c["start_sec"] != (i - 1) * 10 or c["end_sec"] != i * 10:
            raise ValueError(f"clips[{i-1}] must span [{(i-1)*10},{i*10})")

    return data
