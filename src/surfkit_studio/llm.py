"""Local language model (Ollama) for the chat: intent routing and phrasing only.

The model never produces a number or a citation. It reads the user's message,
the technique catalog and what the session already holds, and returns JSON:
which technique the request is about (or none) and one or two plain sentences.
Everything substantive (principle, method choices, results, accuracy,
references) is appended from the catalog by the router, so a small model
cannot put a wrong value in front of a researcher. A reply containing any
digit is discarded. If Ollama is not running the app falls back to the
keyword router.
"""
from __future__ import annotations

import json
import os
import re

import httpx

from .catalog import TECHNIQUES

OLLAMA_URL = os.environ.get("SURFKIT_OLLAMA_URL", "http://127.0.0.1:11434")
DEFAULT_MODEL = os.environ.get("SURFKIT_MODEL", "qwen3:1.7b")

SCHEMA = {
    "type": "object",
    "properties": {
        "technique": {"type": ["string", "null"]},
        "intent": {"type": "string", "enum": ["run", "explain", "next", "other"]},
        "reply": {"type": "string"},
    },
    "required": ["technique", "intent", "reply"],
}


def _catalog_text(session: dict) -> str:
    lines = []
    for t in TECHNIQUES.values():
        need = ("needs data: " + " vs ".join(c.label for c in t.dataset.columns)) if t.dataset else (
            "derived from earlier results" + (" (ready)" if all(k in session for k in t.requires) else ""))
        methods = "; ".join(m.label for m in t.methods)
        lines.append(f"- {t.id}: {t.title}. {t.summary} [{need}] Methods: {methods}")
    return "\n".join(lines)


def system_prompt(session: dict) -> str:
    done = sorted(k for k in session if not k.startswith("tensiometry_"))
    return (
        "You are the assistant inside SurfactantKit Studio, a local app that analyses a researcher's surfactant "
        "data with a validated calculation library. You do NOT calculate anything yourself.\n"
        "Your only jobs: (1) decide which technique from the catalog the message is about, (2) write one or two "
        "short, friendly sentences acknowledging the request.\n"
        "Rules: never write any number or digit; never cite papers; never state a property value; never invent "
        "a technique. If the message is not about one catalog technique, use technique null. "
        "intent is 'run' (they want to compute something), 'explain' (what something means), 'next' (what to do "
        "after a result) or 'other'.\n\n"
        f"Catalog:\n{_catalog_text(session)}\n\n"
        f"Results already in this session: {', '.join(done) if done else 'none yet'}.\n"
        'Answer only with JSON: {"technique": <id or null>, "intent": <intent>, "reply": <sentences>}'
    )


class LocalLLM:
    def __init__(self, model: str = DEFAULT_MODEL, url: str = OLLAMA_URL, timeout: float = 60.0):
        self.model, self.url, self.timeout = model, url.rstrip("/"), timeout

    def available(self) -> bool:
        try:
            r = httpx.get(f"{self.url}/api/tags", timeout=2.0)
            return r.status_code == 200 and any(m.get("name") == self.model for m in r.json().get("models", []))
        except httpx.HTTPError:
            return False

    def route(self, message: str, session: dict, history: list[dict] | None = None) -> dict | None:
        """Return {'technique', 'intent', 'reply'} or None if the model is unusable."""
        msgs = [{"role": "system", "content": system_prompt(session)}]
        msgs += (history or [])[-6:]
        msgs.append({"role": "user", "content": message})
        try:
            r = httpx.post(f"{self.url}/api/chat", timeout=self.timeout, json={
                "model": self.model, "messages": msgs, "stream": False, "think": False,
                "format": SCHEMA, "options": {"temperature": 0, "num_ctx": 4096}})
            r.raise_for_status()
            out = json.loads(r.json()["message"]["content"])
        except (httpx.HTTPError, KeyError, ValueError, TypeError):
            return None
        return sanitize(out)


def sanitize(out: dict) -> dict | None:
    if not isinstance(out, dict):
        return None
    tid = out.get("technique")
    if tid not in TECHNIQUES:
        tid = None
    reply = str(out.get("reply") or "").strip()
    # the model may not state values: any digit, or anything that looks like a citation, drops its sentence
    if re.search(r"\d|et al\.|doi|\(\s*(19|20)", reply, re.I):
        reply = ""
    intent = out.get("intent") if out.get("intent") in ("run", "explain", "next", "other") else "other"
    return {"technique": tid, "intent": intent, "reply": reply[:400]}
