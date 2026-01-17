#!/usr/bin/env python3
"""
Build embeddings index for hybrid RAG.
Outputs to data/<profile>/rag/index/
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import numpy as np
from openai import OpenAI


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def load_api_key() -> str:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if key:
        return key
    fallback = Path("/Users/michaelhajster/mr.doppelklick/testapikey.md")
    if fallback.exists():
        return read_text(fallback)
    raise SystemExit("ERROR: OPENAI_API_KEY not set and testapikey.md not found")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=True, indent=2)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build hybrid RAG embedding index")
    parser.add_argument("--profile", default="mr.doppelklick", help="Username folder")
    parser.add_argument("--data-root", default="data", help="Root data directory")
    parser.add_argument("--model", default="text-embedding-3-large", help="Embedding model")
    parser.add_argument("--batch", type=int, default=25, help="Batch size")
    parser.add_argument("--use-md", action="store_true", help="Embed MD docs instead of transcript text")
    parser.add_argument("--verbose", action="store_true")

    args = parser.parse_args()

    profile_dir = Path(args.data_root).resolve() / args.profile
    unified_path = profile_dir / "unified.json"
    if not unified_path.exists():
        raise SystemExit(f"Missing {unified_path}")

    rag_dir = profile_dir / "rag"
    index_dir = rag_dir / "index"
    index_dir.mkdir(parents=True, exist_ok=True)

    uni = load_json(unified_path)
    records = uni.get("records", [])

    # build texts
    texts: List[str] = []
    ids: List[str] = []
    meta: List[Dict] = []

    for rec in records:
        vid = rec.get("id")
        if not vid:
            continue
        if args.use_md:
            md_path = rag_dir / "items" / f"{vid}.md"
            if not md_path.exists():
                continue
            text = read_text(md_path)
        else:
            transcript = (rec.get("transcript") or {}).get("text") if isinstance(rec.get("transcript"), dict) else ""
            title = rec.get("title") or rec.get("description") or ""
            text = f"{title}\n\n{transcript}".strip()
        if not text:
            continue
        ids.append(vid)
        texts.append(text)
        meta.append({
            "id": vid,
            "url": rec.get("url"),
            "timestamp": rec.get("timestamp"),
            "text_len": len(text),
        })

    if args.verbose:
        print(f"Embedding {len(texts)} items...")

    api_key = load_api_key()
    client = OpenAI(api_key=api_key)

    vectors: List[List[float]] = []
    for i in range(0, len(texts), args.batch):
        batch = texts[i : i + args.batch]
        resp = client.embeddings.create(model=args.model, input=batch)
        vectors.extend([d.embedding for d in resp.data])
        if args.verbose:
            print(f"Embedded {min(i+args.batch, len(texts))}/{len(texts)}")
        time.sleep(0.2)

    arr = np.array(vectors, dtype=np.float32)
    np.save(index_dir / "embeddings.npy", arr)

    index_meta = {
        "model": args.model,
        "created_at": iso_now(),
        "count": len(ids),
        "ids": ids,
        "meta": meta,
    }
    write_json(index_dir / "metadata.json", index_meta)

    if args.verbose:
        print(f"Wrote index to {index_dir}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
