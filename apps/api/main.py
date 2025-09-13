from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path
import json, os, glob, sys, subprocess, threading

# paths
BASE = Path(__file__).resolve().parents[2]
PKG_PATH = BASE / "packages" / "generator"
try:
    from generator.paths import INPUTS, OUTPUTS
except Exception:
    INPUTS  = PKG_PATH / "inputs"
    OUTPUTS = PKG_PATH / "outputs"
INPUTS.mkdir(parents=True, exist_ok=True)
OUTPUTS.mkdir(parents=True, exist_ok=True)

# app
app = FastAPI(title="Shepard's Desk API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://192.168.1.12:3000", "*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/outputs", StaticFiles(directory=str(OUTPUTS), html=False), name="outputs")

class IntentReq(BaseModel):
    user_prompt: str

class GenReq(BaseModel):
    topic: str
    passage: str | None = None
    date: str | None = None

@app.get("/api/health")
def health(): return {"ok": True}

@app.post("/api/intent")
def save_intent(req: IntentReq):
    p = INPUTS / "user_intent.json"
    p.write_text(json.dumps({"user_prompt": req.user_prompt}, ensure_ascii=False, indent=2))
    return {"ok": True, "path": str(p)}

def _spawn_orchestrate(prompt: str):
    # persist the prompt for your pipeline
    (INPUTS / "user_intent.json").write_text(
        json.dumps({"user_prompt": prompt}, ensure_ascii=False, indent=2)
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PKG_PATH) + os.pathsep + env.get("PYTHONPATH", "")
    cmd = [sys.executable, "-u", "-m", "generator.orchestrate"]
    try:
        proc = subprocess.Popen(cmd, cwd=str(BASE), env=env,
                                stdout=sys.stdout, stderr=sys.stderr)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"spawn failed: {e}")
    return proc.pid

# single source of truth; both routes call this
@app.post("/api/generate")
def generate(req: GenReq):
    prompt = req.topic if not req.passage else f"{req.topic} {req.passage}"
    pid = _spawn_orchestrate(prompt)
    return {"status": "started", "pid": pid}

@app.post("/api/generate_stream")
def generate_stream(req: GenReq):
    # alias, same behavior
    return generate(req)

@app.get("/api/outputs")
def list_outputs():
    mp4s = sorted(glob.glob(str(OUTPUTS / "**/*.mp4"), recursive=True))
    files = []
    for p in mp4s[-10:]:
        rel = Path(p).relative_to(OUTPUTS).as_posix()
        files.append({"name": rel, "url": f"/outputs/{rel}"})
    return {"files": files}
