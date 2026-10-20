"""Local web server. Binds to 127.0.0.1 only: data never leaves the machine."""
from __future__ import annotations

import base64
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import citations, data_io, llm, report, router
from .catalog import TECHNIQUES, tiers, tree
from .catalog.base import RunInput

STATIC = Path(__file__).parent / "static"
EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
app = FastAPI(title="SurfactantKit Studio")
SESSIONS: dict[str, dict] = {}


def _session(sid: str) -> dict:
    if sid not in SESSIONS:
        raise HTTPException(404, "Unknown session; reload the page.")
    return SESSIONS[sid]


def _tech(tid: str):
    if tid not in TECHNIQUES:
        raise HTTPException(404, f"Unknown technique {tid}")
    return TECHNIQUES[tid]


def _describe(t, session_values: dict) -> dict:
    return {
        "id": t.id, "title": t.title, "category": t.category, "level": t.level, "summary": t.summary,
        "dataset": None if not t.dataset else {
            "columns": [{"key": c.key, "label": c.label, "units": c.units} for c in t.dataset.columns],
            "min_rows": t.dataset.min_rows, "example": t.dataset.example},
        "params": [{"key": p.key, "label": p.label, "kind": p.kind, "unit": p.unit, "help": p.help,
                    "choices": p.choices, "required": p.required,
                    "value": session_values.get(p.from_session, p.default) if p.from_session else p.default}
                   for p in t.params],
        "methods": [m.__dict__ for m in t.methods],
        "requires": t.requires, "missing": [k for k in t.requires if k not in session_values],
        "unlocks": [{"id": u, "title": TECHNIQUES[u].title} for u in t.unlocks if u in TECHNIQUES],
        "followups": t.followups, "citations": citations.for_keys(t.citations), "tiers": tiers(t),
    }


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.post("/api/session")
def new_session():
    sid = uuid.uuid4().hex
    SESSIONS[sid] = {"values": {}, "runs": [], "tables": {}, "web_search": False}
    return {"sid": sid}


@app.get("/api/catalog")
def catalog(sid: str | None = None):
    vals = SESSIONS.get(sid, {}).get("values", {}) if sid else {}
    return {"tree": tree(), "techniques": {k: _describe(t, vals) for k, t in TECHNIQUES.items()}}


@app.get("/api/example/{name}")
def example(name: str):
    p = (EXAMPLES / name).resolve()
    if p.parent != EXAMPLES.resolve() or not p.exists():
        raise HTTPException(404)
    return FileResponse(p)


@app.post("/api/upload")
async def upload(sid: str = Form(...), technique: str = Form(...), file: UploadFile = File(...)):
    s, t = _session(sid), _tech(technique)
    if not t.dataset:
        raise HTTPException(400, "This technique does not take a dataset.")
    try:
        df = data_io.read_table(file.filename or "data.csv", await file.read())
    except Exception as e:  # noqa: BLE001 - surface the parser's message to the researcher
        raise HTTPException(400, f"Could not read the file: {e}")
    s["tables"][technique] = {"name": file.filename, "df": df}
    return data_io.suggest_mapping(df, t.dataset)


class RunRequest(BaseModel):
    sid: str
    technique: str
    method: str = ""
    params: dict = {}
    mapping: dict | None = None


@app.post("/api/run")
def run(req: RunRequest):
    s, t = _session(req.sid), _tech(req.technique)
    missing = [k for k in t.requires if k not in s["values"]]
    if missing:
        raise HTTPException(400, "Run the analysis that produces " + ", ".join(missing) + " first.")
    data, notes = None, []
    if t.dataset:
        tab = s["tables"].get(t.id)
        if not tab or not req.mapping:
            raise HTTPException(400, "Upload a dataset and confirm the column mapping first.")
        try:
            data, notes = data_io.extract(tab["df"], t.dataset, req.mapping)
        except (KeyError, ValueError) as e:
            raise HTTPException(400, str(e))
    for p in t.params:
        if p.required and req.params.get(p.key) in (None, ""):
            raise HTTPException(400, f"Please set: {p.label}.")
    try:
        r = t.run(RunInput(data, req.params, req.method or (t.methods[0].key if t.methods else ""), s["values"]))
    except ValueError as e:
        raise HTTPException(400, str(e))
    s["values"].update({k: v for k, v in r.provides.items() if v is not None})
    for k in ("temperature_K", "system_type"):
        if req.params.get(k) not in (None, ""):
            s["values"][k] = req.params[k]
    data_note = ""
    if t.dataset:
        data_note = f"Data: {s['tables'][t.id]['name']}, {len(next(iter(data.values())))} points. " + " ".join(notes)
    record = {"technique": t.id, "method": req.method, "data_note": data_note.strip(),
              "values": [{"label": v.label, "text": v.text()} for v in r.values],
              "figures": [{"name": f.name, "caption": f.caption, "png": f.png} for f in r.figures],
              "conclusion": r.conclusion, "warnings": r.warnings, "toolkit_calls": r.toolkit_calls}
    s["runs"].append(record)
    now_ready = [u for u in TECHNIQUES.values() if u.level == "derived"
                 and all(k in s["values"] for k in u.requires)]
    return {**{k: v for k, v in record.items() if k != "figures"},
            "figures": [{"name": f["name"], "caption": f["caption"],
                         "png": base64.b64encode(f["png"]).decode()} for f in record["figures"]],
            "followups": t.followups, "citations": citations.for_keys(t.citations), "tiers": tiers(t, r.toolkit_calls),
            "ready_next": [{"id": u.id, "title": u.title} for u in now_ready], "run_index": len(s["runs"]) - 1}


class ChatRequest(BaseModel):
    sid: str
    message: str


LLM = llm.LocalLLM()


@app.get("/api/status")
def status():
    return {"local_ai": LLM.available(), "model": LLM.model}


@app.post("/api/chat")
def chat(req: ChatRequest):
    s = _session(req.sid)
    model = LLM if s.get("use_ai", True) and LLM.available() else None
    out = router.route(req.message, s["values"], model, s.setdefault("history", []))
    s["history"] += [{"role": "user", "content": req.message},
                     {"role": "assistant", "content": out["reply"][:600]}]
    return out


class Settings(BaseModel):
    sid: str
    use_ai: bool = True
    model: str | None = None


@app.post("/api/settings")
def settings(req: Settings):
    s = _session(req.sid)
    s["use_ai"] = req.use_ai
    if req.model:
        LLM.model = req.model
    return {"use_ai": s["use_ai"], "model": LLM.model, "local_ai": LLM.available()}


@app.get("/api/report/{sid}.{fmt}")
def get_report(sid: str, fmt: str, sample: str = "", author: str = "", affiliation: str = ""):
    s = _session(sid)
    if not s["runs"]:
        raise HTTPException(400, "Run at least one analysis first.")
    content = report.build_content(s["runs"], report.default_meta(sample, author, affiliation))
    if fmt == "docx":
        return Response(report.to_docx(content), media_type="application/vnd.openxmlformats-officedocument."
                        "wordprocessingml.document",
                        headers={"Content-Disposition": 'attachment; filename="surfactant_report.docx"'})
    if fmt == "pdf":
        return Response(report.to_pdf(content), media_type="application/pdf",
                        headers={"Content-Disposition": 'attachment; filename="surfactant_report.pdf"'})
    raise HTTPException(404)


def main():
    import uvicorn
    import webbrowser
    webbrowser.open("http://127.0.0.1:8770")
    uvicorn.run(app, host="127.0.0.1", port=8770)
