# Run

1. `python -m venv .venv && source .venv/bin/activate` (Windows: `.venv\Scripts\activate`)
2. `pip install -r requirements.txt`

3. Create `.env` with:
GLOO_CLIENT_ID=...
GLOO_CLIENT_SECRET=...

4. Edit `inputs/user_intent.json` as needed.
5. `python api_call.py` → writes `outputs/plan.json`.

# Tests (no network)
`pytest -q`