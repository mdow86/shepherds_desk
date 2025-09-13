import argparse
from datetime import date as _date
from pathlib import Path
from .paths import OUTPUTS

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--date", default=str(_date.today()))
    args = ap.parse_args()
    # adapt this call to your orchestrator signature
    try:
        from .orchestrate import main as run_orchestrator
        run_orchestrator(prompt=args.prompt, target_date=args.date)
    except Exception as e:
        raise SystemExit(f"orchestrator failed: {e}")
    print(f"Done. Outputs -> {Path(OUTPUTS)}")

if __name__ == "__main__":
    main()
