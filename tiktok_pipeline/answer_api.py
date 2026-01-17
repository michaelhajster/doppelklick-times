#!/usr/bin/env python3
"""
FastAPI service with selectable modes, models, and tone:
- full: full-context answering using all transcripts
- rag: hybrid RAG (embeddings retrieval + full transcripts of top_k)
- Models: GPT-4.1, Opus 4.5 (Claude)
- Tone: professional, casual
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List

import numpy as np
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
import anthropic


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_openai_key() -> str:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if key:
        return key
    fallback = Path("/Users/michaelhajster/mr.doppelklick/testapikey.md")
    if fallback.exists():
        return read_text(fallback).strip()
    raise RuntimeError("OPENAI_API_KEY not set")


def load_anthropic_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if key:
        return key
    fallback = Path("/Users/michaelhajster/mr.doppelklick/anthropic_key.md")
    if fallback.exists():
        return read_text(fallback).strip()
    raise RuntimeError("ANTHROPIC_API_KEY not set")


def cosine_sim(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    a_norm = a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-12)
    b_norm = b / (np.linalg.norm(b, axis=0, keepdims=True) + 1e-12)
    return a_norm @ b_norm


def load_dataset(profile: str, data_root: str):
    profile_dir = Path(data_root).resolve() / profile
    unified = json.loads(read_text(profile_dir / "unified.json"))
    rag_all_md = profile_dir / "rag" / "all_transcripts.md"
    all_md = read_text(rag_all_md) if rag_all_md.exists() else ""
    return unified, all_md, profile_dir


def load_index(profile_dir: Path):
    index_dir = profile_dir / "rag" / "index"
    meta_path = index_dir / "metadata.json"
    emb_path = index_dir / "embeddings.npy"
    if not meta_path.exists() or not emb_path.exists():
        return None, None
    meta = json.loads(read_text(meta_path))
    emb = np.load(emb_path)
    return meta, emb


def get_system_prompt(tone: str = "professional") -> str:
    base = """Du bist ein KI-Assistent, der auf dem Content von Mr. Doppelklick (@mr.doppelklick) basiert.

DEIN WISSENSBEREICH:
- Content Marketing & Social Media Strategie
- Personal Branding & Positionierung
- TikTok, Instagram, YouTube Growth
- Hooks, Storytelling & Formatentwicklung
- Sales Funnels & Monetarisierung
- Zielgruppen & Nischen-Strategien

WICHTIGE REGELN:
1. Antworte ausschließlich basierend auf dem gegebenen Kontext (TikTok-Transkripte)
2. Wenn eine Information nicht im Kontext enthalten ist, sage das ehrlich
3. Strukturiere deine Antworten klar mit Überschriften und Aufzählungen
4. Gib konkrete, umsetzbare Empfehlungen
5. Fasse am Ende die wichtigsten Punkte zusammen"""

    if tone == "casual":
        style = """

STIL:
- Schreibe locker und authentisch, wie ein erfahrener Mentor
- Verwende "du" und sprich den Leser direkt an
- Sei enthusiastisch aber substanziell
- Nutze gelegentlich Metaphern und Beispiele aus dem Alltag"""
    else:  # professional
        style = """

STIL:
- Schreibe professionell und präzise
- Verwende klare, geschäftliche Sprache
- Fokussiere auf Fakten und bewährte Methoden
- Formuliere sachlich aber verständlich"""

    return base + style


def openai_answer(model: str, system: str, user: str) -> str:
    client = OpenAI(api_key=load_openai_key())
    try:
        resp = client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.output_text
    except Exception:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content


def anthropic_answer(model: str, system: str, user: str) -> str:
    client = anthropic.Anthropic(api_key=load_anthropic_key())
    message = client.messages.create(
        model=model,
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return message.content[0].text


def get_answer(model: str, system: str, user: str) -> tuple[str, str]:
    """Route to correct provider based on model name."""
    if model in ["claude-opus-4-5-20251101", "opus-4.5", "claude-sonnet", "claude-3-5-sonnet-20241022"]:
        model_id = "claude-opus-4-5-20251101" if "opus" in model else "claude-3-5-sonnet-20241022"
        return anthropic_answer(model_id, system, user), "anthropic"
    else:
        return openai_answer(model, system, user), "openai"


class AnswerRequest(BaseModel):
    question: str
    mode: str = "full"
    model: str = "gpt-4.1"
    tone: str = "professional"
    top_k: int = 30
    include_captions: bool = False
    profile: str = "mr.doppelklick"
    data_root: str = "data"


app = FastAPI(title="Mr. Doppelklick AI", version="2.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/answer")
async def answer(req: AnswerRequest):
    try:
        unified, all_md, profile_dir = load_dataset(req.profile, req.data_root)
    except Exception as e:
        return {"error": f"Dataset nicht gefunden: {str(e)}", "mode": req.mode, "model": req.model, "tone": req.tone}

    records = unified.get("records", [])
    system_prompt = get_system_prompt(req.tone)

    if req.mode == "full":
        context = all_md
        user = f"FRAGE: {req.question}\n\nKONTEXT ({len(records)} TikTok-Transkripte von @mr.doppelklick):\n{context}"
        try:
            answer_text, provider = get_answer(req.model, system_prompt, user)
        except Exception as e:
            return {"error": f"API Fehler: {str(e)}", "mode": req.mode, "model": req.model, "tone": req.tone}
        return {
            "mode": "full",
            "answer": answer_text,
            "sources": "all",
            "model": req.model,
            "provider": provider,
            "tone": req.tone,
            "total_videos": len(records)
        }

    # RAG mode
    meta, emb = load_index(profile_dir)
    if meta is None or emb is None:
        return {"error": "RAG index missing. Run build_rag_index.py first."}

    # Embed query with OpenAI (even for Claude answers)
    openai_client = OpenAI(api_key=load_openai_key())
    emb_model = meta.get("model", "text-embedding-3-large")
    q_emb = openai_client.embeddings.create(model=emb_model, input=req.question).data[0].embedding
    q_vec = np.array(q_emb, dtype=np.float32)

    sims = cosine_sim(emb, q_vec)
    top_k = min(req.top_k, len(sims)) if req.top_k > 0 else len(sims)
    top_idx = np.argsort(-sims)[:top_k]
    ids = [meta["ids"][i] for i in top_idx]
    id_to_idx = {meta["ids"][i]: i for i in range(len(meta["ids"]))}

    context_parts: List[str] = []
    sources = []
    for vid in ids:
        rec = next((r for r in records if r.get("id") == vid), None)
        if not rec:
            continue
        transcript = (rec.get("transcript") or {}).get("text") if isinstance(rec.get("transcript"), dict) else ""
        caps_text = ""
        if req.include_captions:
            caps = rec.get("captions") or []
            caps_text = "\n".join([c.get("text", "") for c in caps if isinstance(c, dict) and c.get("text")])
        context_parts.append(f"# Video {vid}\n{transcript}\n{caps_text}".strip())
        idx = id_to_idx.get(vid)
        score = float(sims[idx]) if idx is not None else None
        sources.append({"id": vid, "url": rec.get("url"), "score": score})

    context = "\n\n".join(context_parts)
    user = f"FRAGE: {req.question}\n\nKONTEXT (Top {top_k} relevante Videos von @mr.doppelklick):\n{context}"
    try:
        answer_text, provider = get_answer(req.model, system_prompt, user)
    except Exception as e:
        return {"error": f"API Fehler: {str(e)}", "mode": req.mode, "model": req.model, "tone": req.tone}

    return {
        "mode": "rag",
        "answer": answer_text,
        "sources": sources,
        "top_k": top_k,
        "model": req.model,
        "provider": provider,
        "tone": req.tone
    }


@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.1", "models": ["gpt-4.1", "opus-4.5"]}


@app.get("/models")
async def models():
    return {
        "available": [
            {"id": "gpt-4.1", "name": "GPT-4.1", "provider": "openai", "recommended_mode": "full"},
            {"id": "opus-4.5", "name": "Claude Opus 4.5", "provider": "anthropic", "recommended_mode": "rag"},
        ],
        "tones": [
            {"id": "professional", "name": "Professionell"},
            {"id": "casual", "name": "Locker"},
        ]
    }
