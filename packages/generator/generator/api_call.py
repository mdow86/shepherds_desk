"""
Calls Gloo chat completions with a strict JSON prompt loaded from a template,
injects user input (from arg or inputs/user_intent.json), validates the model
output, and writes the plan to outputs/plan.json. Also prints job summaries.
"""

from __future__ import annotations
import json
from typing import List, Dict, Optional
import requests

from .paths import INPUTS, OUTPUTS, TEMPLATES, SCHEMAS

# access_token.py may live at repo root or inside the package.
try:
    from .access_token import get_bearer_header, CLIENT_ID, CLIENT_SECRET  # if you moved it under generator/
except ImportError:
    from access_token import get_bearer_header, CLIENT_ID, CLIENT_SECRET  # fallback to repo root

from .validators.json_validate import load_schema, parse_and_validate
from .mappers import plan_to_image_jobs, plan_to_tts_jobs, summarize_jobs

# Constants and paths
API_URL = "https://platform.ai.gloo.com/ai/v1/chat/completions"
SCHEMA_PATH = SCHEMAS / "plan_schema.json"
PROMPT_TEMPLATE_PATH = TEMPLATES / "llm_plan_prompt.txt"
INPUT_PATH = INPUTS / "user_intent.json"
OUTPUT_PLAN_PATH = OUTPUTS / "plan.json"


def load_user_prompt(override: Optional[str] = None) -> str:
    """
    Returns the user prompt. If override is provided, uses that.
    Otherwise reads inputs/user_intent.json.
    """
    if override is not None:
        prompt = override.strip()
    else:
        data = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
        prompt = data.get("user_prompt", "").strip()
    if not prompt:
        raise ValueError("No user prompt provided. Set override or populate inputs/user_intent.json with 'user_prompt'.")
    return prompt


def build_user_message(user_prompt: str) -> str:
    """
    Loads the template and injects the user prompt into {{USER_PROMPT}}.
    """
    template = PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")
    return template.replace("{{USER_PROMPT}}", user_prompt)


def call_gloo(messages: List[Dict[str, str]]) -> str:
    """
    Posts to Gloo chat completions and returns assistant message content.
    Raises on HTTP error or missing fields.
    """
    headers = get_bearer_header(CLIENT_ID, CLIENT_SECRET)
    payload = {
        "model": "meta.llama3-70b-instruct-v1:0",
        "messages": messages,
    }
    resp = requests.post(API_URL, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        raise RuntimeError(f"Unexpected response shape: {data}") from e


def main(user_prompt: Optional[str] = None) -> None:
    OUTPUTS.mkdir(parents=True, exist_ok=True)

    # 1) Prepare messages
    u_prompt = load_user_prompt(user_prompt)
    system_msg = {"role": "system", "content": "You are a human-flourishing assistant."}
    user_msg = {"role": "user", "content": build_user_message(u_prompt)}
    messages = [system_msg, user_msg]

    # 2) Call Gloo
    raw_content = call_gloo(messages)
    print("HTTP OK; received model output.")

    # 3) Validate JSON plan
    schema = load_schema(SCHEMA_PATH)
    plan = parse_and_validate(raw_content, schema)

    # 4) Persist plan
    OUTPUT_PLAN_PATH.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    print(f"Wrote plan → {OUTPUT_PLAN_PATH}")

    # 5) Derive job specs (no network)
    image_jobs = plan_to_image_jobs(plan)
    tts_jobs = plan_to_tts_jobs(plan, voice="warm_female")

    # 6) Print concise summary
    print(f"Title: {plan['title']}")
    print(f"Clips: {len(plan['clips'])} | {summarize_jobs(image_jobs, tts_jobs)}")


if __name__ == "__main__":
    main()
