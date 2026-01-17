#!/usr/bin/env python3
"""
Build a unified dataset + per-item JSON files, and optionally transcribe audio with OpenAI.

Outputs:
- data/<username>/unified.json
- data/<username>/items/<id>.json
- data/<username>/transcripts/<id>.json (OpenAI response)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

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


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=True, indent=2)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def merge_records(a: Dict, b: Dict) -> Dict:
    """Merge two records, preferring non-empty values and unioning captions."""
    out = dict(a)
    for k, v in b.items():
        if v is None:
            continue
        if k not in out or out[k] in (None, "", [], {}):
            out[k] = v
            continue
        if k == "captions" and isinstance(v, list):
            existing = out.get("captions", [])
            by_lang = {c.get("lang") or c.get("path"): c for c in existing if isinstance(c, dict)}
            for c in v:
                key = c.get("lang") or c.get("path")
                if key and key not in by_lang:
                    by_lang[key] = c
            out["captions"] = list(by_lang.values())
    return out


def sort_key(rec: Dict) -> int:
    ts = rec.get("timestamp")
    try:
        return int(ts) if ts is not None else -1
    except Exception:
        return -1


def transcribe_audio(client: OpenAI, audio_path: Path, model: str) -> Dict:
    with audio_path.open("rb") as f:
        resp = client.audio.transcriptions.create(model=model, file=f)
    # resp is pydantic, but we only need text
    return {
        "text": resp.text,
        "model": model,
        "provider": "openai",
        "created_at": iso_now(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build unified dataset and transcribe audio")
    parser.add_argument("--profile", default="mr.doppelklick", help="Username (folder name)")
    parser.add_argument("--data-root", default="data", help="Root data directory")
    parser.add_argument("--model", default="gpt-4o-transcribe", help="OpenAI transcription model")
    parser.add_argument("--no-transcribe", action="store_true", help="Skip OpenAI transcription")
    parser.add_argument("--skip-existing", action="store_true", help="Skip if transcript exists")
    parser.add_argument("--max", type=int, default=0, help="Limit number of transcriptions")
    parser.add_argument("--sleep", type=float, default=0.0, help="Sleep seconds between requests")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging")

    args = parser.parse_args()

    profile_dir = Path(args.data_root).resolve() / args.profile
    index_path = profile_dir / "index.json"
    if not index_path.exists():
        raise SystemExit(f"ERROR: Missing {index_path}")

    idx = load_json(index_path)
    records_in = idx.get("records", [])

    # Deduplicate by id
    by_id: Dict[str, Dict] = {}
    for rec in records_in:
        vid = rec.get("id")
        if not vid:
            continue
        if vid not in by_id:
            by_id[vid] = rec
        else:
            by_id[vid] = merge_records(by_id[vid], rec)

    records = list(by_id.values())
    records.sort(key=sort_key, reverse=True)

    transcripts_dir = profile_dir / "transcripts"
    items_dir = profile_dir / "items"

    client = None
    if not args.no_transcribe:
        api_key = load_api_key()
        client = OpenAI(api_key=api_key)

    transcribed = 0
    for rec in records:
        vid = rec.get("id")
        if not vid:
            continue
        audio_rel = rec.get("audio_path")
        if not audio_rel:
            continue
        audio_path = profile_dir / audio_rel
        if not audio_path.exists():
            rec["error"] = "audio_missing"
            continue

        t_path = transcripts_dir / f"{vid}.json"
        if t_path.exists():
            if args.skip_existing:
                try:
                    rec["transcript"] = load_json(t_path)
                except Exception:
                    pass
                continue

        if args.no_transcribe:
            continue

        if args.max and transcribed >= args.max:
            break

        try:
            if args.verbose:
                print(f"Transcribing {vid}...")
            transcript = transcribe_audio(client, audio_path, args.model)
            write_json(t_path, transcript)
            rec["transcript"] = transcript
            transcribed += 1
        except Exception as exc:
            rec["transcript_error"] = str(exc)

        if args.sleep > 0:
            time.sleep(args.sleep)

    # Write per-item files
    for rec in records:
        vid = rec.get("id")
        if not vid:
            continue
        write_json(items_dir / f"{vid}.json", rec)

    # Write unified file
    unified = {
        "profile": idx.get("profile"),
        "username": idx.get("username"),
        "generated_at": iso_now(),
        "counts": {
            "records": len(records),
            "audio": sum(1 for r in records if r.get("audio_path")),
            "captions": sum(1 for r in records if r.get("captions")),
            "transcripts": sum(1 for r in records if r.get("transcript")),
        },
        "records": records,
    }
    write_json(profile_dir / "unified.json", unified)

    if args.verbose:
        print(f"Wrote {profile_dir / 'unified.json'}")
        print(f"Wrote items to {items_dir}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
