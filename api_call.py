"""
Calls Gloo chat completions with a strict JSON prompt loaded from a template,
injects user input from a JSON file, validates the model output, and writes
the plan to outputs/plan.json. Also prints derived job summaries.

Requires:
- access_token.py for auth (CLIENT_ID/CLIENT_SECRET via .env).
- schemas/plan_schema.json for validation.
- prompt_templates/llm_plan_prompt.txt for the user message template.
- inputs/user_intent.json for dynamic end-user prompt.

Note:
- Network call goes to Gloo's /ai/v1/chat/completions endpoint.
- Keeps your original model choice and system prompt.
"""

from __future__ import annotations
import json
from pathlib import Path
import requests

from access_token import get_bearer_header, CLIENT_ID, CLIENT_SECRET
from validators.json_validate import load_schema, parse_and_validate
from jobs.mappers import plan_to_image_jobs, plan_to_tts_jobs, summarize_jobs

# Constants and paths
API_URL = "https://platform.ai.gloo.com/ai/v1/chat/completions"
ROOT = Path(__file__).parent
SCHEMA_PATH = ROOT / "schemas" / "plan_schema.json"
PROMPT_TEMPLATE_PATH = ROOT / "prompt_templates" / "llm_plan_prompt.txt"
INPUT_PATH = ROOT / "inputs" / "user_intent.json"
OUTPUTS_DIR = ROOT / "outputs"
OUTPUT_PLAN_PATH = OUTPUTS_DIR / "plan.json"

def load_user_prompt() -> str:
    """
    Reads the end-user input from inputs/user_intent.json.
    """
    data = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    prompt = data.get("user_prompt", "").strip()
    if not prompt:
        raise ValueError("inputs/user_intent.json is missing 'user_prompt'")
    return prompt

def build_user_message() -> str:
    """
    Loads the template and injects the user prompt into {{USER_PROMPT}}.
    """
    template = PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")
    user_prompt = load_user_prompt()
    return template.replace("{{USER_PROMPT}}", user_prompt)

def call_gloo(messages: list[dict]) -> str:
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

def main() -> None:
    OUTPUTS_DIR.mkdir(exist_ok=True)

    # 1) Prepare messages
    system_msg = {"role": "system", "content": "You are a human-flourishing assistant."}
    user_msg = {"role": "user", "content": build_user_message()}
    messages = [system_msg, user_msg]

    # 2) Call Gloo
    raw_content = call_gloo(messages)
    print("HTTP OK; received model output.")

    # 3) Validate JSON plan
    schema = load_schema(SCHEMA_PATH)
    plan = parse_and_validate(raw_content, schema)

    # 4) Persist plan
    OUTPUT_PLAN_PATH.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    print(f"Wrote plan → {OUTPUT_PLAN_PATH.relative_to(ROOT)}")

    # 5) Derive job specs (no network)
    image_jobs = plan_to_image_jobs(plan)
    tts_jobs = plan_to_tts_jobs(plan, voice="warm_female")

    # 6) Print concise summary
    print(f"Title: {plan['title']}")
    print(f"Clips: {len(plan['clips'])} | {summarize_jobs(image_jobs, tts_jobs)}")

if __name__ == "__main__":
    main()
