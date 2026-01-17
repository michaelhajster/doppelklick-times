#!/usr/bin/env python3
"""
Export a RAG-friendly dataset:
- data/<username>/rag/unified.json
- data/<username>/rag/records.jsonl
- data/<username>/rag/all_transcripts.md
- data/<username>/rag/items/<id>.json
- data/<username>/rag/items/<id>.md
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=True, indent=2)


def write_jsonl(path: Path, rows: Iterable[Dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=True) + "\n")


def safe(val) -> str:
    if val is None:
        return ""
    return str(val)


def sort_key(rec: Dict) -> int:
    ts = rec.get("timestamp")
    try:
        return int(ts) if ts is not None else -1
    except Exception:
        return -1


def build_md(rec: Dict) -> str:
    vid = safe(rec.get("id"))
    url = safe(rec.get("url"))
    ts = safe(rec.get("timestamp"))
    title = safe(rec.get("title") or rec.get("description") or "")
    uploader = safe(rec.get("uploader"))
    duration = safe(rec.get("duration"))
    view_count = safe(rec.get("view_count"))
    like_count = safe(rec.get("like_count"))
    comment_count = safe(rec.get("comment_count"))
    repost_count = safe(rec.get("repost_count"))

    transcript = ""
    if isinstance(rec.get("transcript"), dict):
        transcript = safe(rec["transcript"].get("text"))

    captions_text = ""
    caps = rec.get("captions") or []
    if caps:
        parts = []
        for c in caps:
            text = safe(c.get("text"))
            if text:
                parts.append(text)
        captions_text = "\n".join(parts)

    md = [
        f"# {vid}",
        "",
        "```yaml",
        f"id: {vid}",
        f"url: {url}",
        f"timestamp: {ts}",
        f"uploader: {uploader}",
        f"duration: {duration}",
        f"view_count: {view_count}",
        f"like_count: {like_count}",
        f"comment_count: {comment_count}",
        f"repost_count: {repost_count}",
        "```",
        "",
    ]
    if title:
        md += ["## Title/Description", "", title, ""]
    md += ["## Transcript (OpenAI)", "", transcript or "", ""]
    if captions_text:
        md += ["## Captions (TikTok)", "", captions_text, ""]

    return "\n".join(md).strip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Export RAG-friendly dataset")
    parser.add_argument("--profile", default="mr.doppelklick", help="Username folder")
    parser.add_argument("--data-root", default="data", help="Root data directory")
    parser.add_argument("--out-dir", default="rag", help="Output folder name under profile")
    args = parser.parse_args()

    profile_dir = Path(args.data_root).resolve() / args.profile
    unified_path = profile_dir / "unified.json"
    if not unified_path.exists():
        raise SystemExit(f"Missing {unified_path}")

    uni = read_json(unified_path)
    records = uni.get("records", [])
    records.sort(key=sort_key, reverse=True)

    rag_dir = profile_dir / args.out_dir
    items_dir = rag_dir / "items"

    # write unified.json
    out_uni = {
        "profile": uni.get("profile"),
        "username": uni.get("username"),
        "generated_at": iso_now(),
        "counts": {
            "records": len(records),
            "audio": sum(1 for r in records if r.get("audio_path")),
            "captions": sum(1 for r in records if r.get("captions")),
            "transcripts": sum(1 for r in records if r.get("transcript")),
        },
        "records": records,
    }
    write_json(rag_dir / "unified.json", out_uni)

    # jsonl for easy ingestion
    write_jsonl(rag_dir / "records.jsonl", records)

    # per-item files + all_transcripts.md
    all_md_parts: List[str] = []
    for rec in records:
        vid = rec.get("id")
        if not vid:
            continue
        write_json(items_dir / f"{vid}.json", rec)
        md = build_md(rec)
        (items_dir / f"{vid}.md").write_text(md, encoding="utf-8")
        all_md_parts.append(md)

    (rag_dir / "all_transcripts.md").write_text("\n\n".join(all_md_parts), encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
