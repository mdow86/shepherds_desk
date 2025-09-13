"use client";
import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export default function Home() {
  const [topic, setTopic] = useState("");
  const [passage, setPassage] = useState("");
  const [date, setDate] = useState("");
  const [busy, setBusy] = useState(false);
  const [files, setFiles] = useState<{name:string;url:string}[]>([]);
  const [msg, setMsg] = useState("");

  async function refreshOutputs() {
    const r = await fetch(`${API}/api/outputs`);
    const j = await r.json();
    setFiles(j.files || []);
  }

  async function handleGenerate() {
    setBusy(true);
    setMsg("Generating…");
    try {
      await fetch(`${API}/api/intent`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_prompt: `${topic} ${passage}`.trim() }),
      });
      const r = await fetch(`${API}/api/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic, passage: passage || null, date: date || null }),
      });
      const j = await r.json();
      setMsg(j.status || "done");
    } catch (e:any) {
      setMsg(`Error: ${e?.message || e}`);
    } finally {
      setBusy(false);
      await refreshOutputs();
    }
  }

  useEffect(() => { refreshOutputs(); }, []);

  return (
    <main className="min-h-screen bg-gradient-to-b from-sky-50 via-white to-sky-50 p-6">
      <div className="max-w-3xl mx-auto space-y-6">
        <h1 className="text-2xl font-semibold text-sky-700">Shepard&apos;s Desk</h1>
        <div className="rounded-2xl bg-white shadow p-4 space-y-3">
          <div className="grid gap-2">
            <label className="text-sm text-slate-600">Topic</label>
            <input className="border rounded-xl px-3 py-2" value={topic} onChange={e=>setTopic(e.target.value)} placeholder="Good Samaritan for K" />
          </div>
          <div className="grid gap-2">
            <label className="text-sm text-slate-600">Passage (optional)</label>
            <input className="border rounded-xl px-3 py-2" value={passage} onChange={e=>setPassage(e.target.value)} placeholder="Luke 10:25-37" />
          </div>
          <div className="grid gap-2">
            <label className="text-sm text-slate-600">Date (optional, YYYY-MM-DD)</label>
            <input className="border rounded-xl px-3 py-2" value={date} onChange={e=>setDate(e.target.value)} placeholder="2025-10-06" />
          </div>
          <button
            onClick={handleGenerate}
            disabled={busy || !topic.trim()}
            className={`px-4 py-2 rounded-2xl text-white ${busy ? "bg-sky-300" : "bg-sky-600 hover:bg-sky-700"}`}
          >
            {busy ? "Working…" : "Plan & Generate"}
          </button>
          <div className="text-sm text-slate-600">{msg}</div>
        </div>

        <div className="rounded-2xl bg-white shadow p-4">
          <h2 className="font-semibold mb-2">Recent Outputs</h2>
          {files.length === 0 ? (
            <div className="text-sm text-slate-500">No files yet.</div>
          ) : (
            <ul className="text-sm space-y-2">
              {files.map(f => (
                <li key={f.name} className="flex items-center justify-between border rounded-xl px-3 py-2">
                  <span>{f.name}</span>
                  <a className="text-sky-700 underline" href={`${API}${f.url}`} target="_blank" rel="noreferrer">Open</a>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </main>
  );
}
