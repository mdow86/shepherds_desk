"use client";
import { useEffect, useState } from "react";

export default function Home() {
  const [topic, setTopic] = useState("");
  const [passage, setPassage] = useState("");
  const [date, setDate] = useState("");
  const [busy, setBusy] = useState(false);
  const [files, setFiles] = useState<{ name: string; url: string }[]>([]);
  const [msg, setMsg] = useState("");
  const [log, setLog] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);

  async function refreshOutputs() {
    const r = await fetch(`/_api/api/outputs`);
    const j = await r.json();
    setFiles(j.files || []);
  }

  async function poll(job_id: string) {
    let status = "running";
    setLog("");
    while (status === "running") {
      const r = await fetch(`/_api/api/jobs/${job_id}`);
      const j = await r.json();
      status = j.status;
      setLog(j.log_tail || "");
      await new Promise((res) => setTimeout(res, 1000));
    }
    setMsg(status === "done" ? "Done." : "Error.");
    setBusy(false);
    await refreshOutputs();
  }

async function handleGenerate() {
  setBusy(true);
  setMsg("Starting…");
  setLog("");
  setJobId(null);

  console.log("USING generate_stream");

  // save intent
  await fetch(`/_api/api/intent`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_prompt: `${topic} ${passage}`.trim() }),
  });

  // run orchestrate with live logs in uvicorn console
  const r = await fetch(`/_api/api/generate_stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ topic, passage: passage || null, date: date || null }),
  });
  const j = await r.json();
  setMsg(`Running (pid ${j.pid})…`);

  // give the backend a moment, then refresh the outputs list
  setTimeout(refreshOutputs, 5000);
  setBusy(false);
}


  useEffect(() => { refreshOutputs(); }, []);

  return (
    <main className="min-h-screen bg-gradient-to-b from-sky-50 via-white to-sky-50 p-6">
      <div className="max-w-4xl mx-auto space-y-6">
        <h1 className="text-2xl font-semibold text-sky-700">Shepard&apos;s Desk</h1>

        <div className="rounded-2xl bg-white shadow p-4 space-y-3">
          <div className="grid gap-2">
            <label className="text-sm text-slate-600">Topic</label>
            <input className="border rounded-xl px-3 py-2" value={topic} onChange={e=>setTopic(e.target.value)} />
          </div>
          <div className="grid gap-2">
            <label className="text-sm text-slate-600">Passage (optional)</label>
            <input className="border rounded-xl px-3 py-2" value={passage} onChange={e=>setPassage(e.target.value)} />
          </div>
          <button onClick={handleGenerate} disabled={busy || !topic.trim()}
            className={`px-4 py-2 rounded-2xl text-white ${busy ? "bg-sky-300" : "bg-sky-600 hover:bg-sky-700"}`}>
            {busy ? "Working…" : "Plan & Generate"}
          </button>
          <div className="text-sm text-slate-600">
            {msg}{jobId ? ` • Job ${jobId}` : ""}
          </div>

          {log && (
            <pre className="mt-2 max-h-72 overflow-auto text-xs bg-slate-50 border rounded-xl p-2 whitespace-pre-wrap">
{log}
            </pre>
          )}
        </div>

        <div className="rounded-2xl bg-white shadow p-4">
          <h2 className="font-semibold mb-2">Recent Outputs</h2>
          {files.length === 0 ? <div className="text-sm text-slate-500">No files yet.</div> : (
            <ul className="text-sm space-y-2">
              {files.map((f) => (
                <li key={f.name} className="flex items-center justify-between border rounded-xl px-3 py-2">
                  <span>{f.name}</span>
                  <a className="text-sky-700 underline" href={`/_api${f.url}`} target="_blank">Open</a>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </main>
  );
}
