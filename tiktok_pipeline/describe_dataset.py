#!/usr/bin/env python3
"""
Generate high-quality documentation for the dataset:
- per-video token counts
- total token counts
- per-video summaries + topics (optional, OpenAI)
- overall dataset summary
Outputs to data/<profile>/docs
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import tiktoken
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


def write_jsonl(path: Path, rows: Iterable[Dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=True) + "\n")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def token_count(text: str, enc) -> int:
    if not text:
        return 0
    return len(enc.encode(text))


def build_item_md(rec: Dict) -> str:
    vid = rec.get("id", "")
    url = rec.get("url", "")
    ts = rec.get("timestamp", "")
    title = rec.get("title") or rec.get("description") or ""

    md = [
        f"# {vid}",
        "",
        "```yaml",
        f"id: {vid}",
        f"url: {url}",
        f"timestamp: {ts}",
        f"duration: {rec.get('duration','')}",
        f"transcript_tokens: {rec.get('transcript_tokens',0)}",
        f"captions_tokens: {rec.get('captions_tokens',0)}",
        f"total_tokens: {rec.get('total_tokens',0)}",
        "```",
        "",
    ]

    if title:
        md += ["## Title/Description", "", title, ""]

    summary = rec.get("summary") or ""
    if summary:
        md += ["## Summary (DE)", "", summary, ""]

    topics = rec.get("topics") or []
    if topics:
        md += ["## Topics", "", ", ".join(topics), ""]

    transcript = (rec.get("transcript") or {}).get("text") if isinstance(rec.get("transcript"), dict) else ""
    if transcript:
        md += ["## Transcript", "", transcript, ""]

    return "\n".join(md).strip() + "\n"


def summarize_item(client: OpenAI, rec: Dict, model: str) -> Dict:
    transcript = (rec.get("transcript") or {}).get("text") if isinstance(rec.get("transcript"), dict) else ""
    title = rec.get("title") or rec.get("description") or ""

    prompt = (
        "Du bist ein exzellenter deutschsprachiger Analyst. "
        "Liefere ausschließlich JSON mit den Feldern: summary_de, topics, keywords. "
        "summary_de: 120-200 Wörter, maximal deskriptiv. "
        "topics: 5-12 kurze Themen. "
        "keywords: 8-15 Stichwörter.\n\n"
        f"TITLE/DESCRIPTION: {title}\n\n"
        f"TRANSCRIPT:\n{transcript}"
    )

    resp = client.responses.create(
        model=model,
        input=prompt,
    )

    try:
        data = json.loads(resp.output_text)
    except Exception:
        # fallback: wrap as plain
        data = {"summary_de": resp.output_text, "topics": [], "keywords": []}

    return data


def summarize_dataset(client: OpenAI, records: List[Dict], model: str) -> Dict:
    # build a compact topic list
    topics = []
    for r in records:
        for t in r.get("topics") or []:
            topics.append(t)
    topic_str = ", ".join(topics[:400])

    prompt = (
        "Du bist ein deutschsprachiger Analyst. "
        "Fasse die Gesamtdaten der TikTok-Transkripte zusammen. "
        "Liefere ausschließlich JSON mit Feldern: overview_de, top_themes, suggested_use_cases. "
        "overview_de: 200-300 Wörter, deskriptiv. "
        "top_themes: 10-20 Themen. "
        "suggested_use_cases: 5-10 Anwendungsfälle.\n\n"
        f"THEMES (raw): {topic_str}"
    )

    resp = client.responses.create(
        model=model,
        input=prompt,
    )

    try:
        data = json.loads(resp.output_text)
    except Exception:
        data = {"overview_de": resp.output_text, "top_themes": [], "suggested_use_cases": []}

    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Describe dataset with tokens + summaries")
    parser.add_argument("--profile", default="mr.doppelklick", help="Username folder")
    parser.add_argument("--data-root", default="data", help="Root data directory")
    parser.add_argument("--out-dir", default="docs", help="Output folder name under profile")
    parser.add_argument("--summary-model", default="gpt-4.1", help="OpenAI model for summaries")
    parser.add_argument("--no-summaries", action="store_true", help="Skip OpenAI summaries")
    parser.add_argument("--skip-existing", action="store_true", help="Skip summaries if already present")
    parser.add_argument("--max", type=int, default=0, help="Limit number of summaries")
    parser.add_argument("--sleep", type=float, default=0.0, help="Sleep seconds between requests")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging")

    args = parser.parse_args()

    profile_dir = Path(args.data_root).resolve() / args.profile
    unified_path = profile_dir / "unified.json"
    if not unified_path.exists():
        raise SystemExit(f"Missing {unified_path}")

    uni = load_json(unified_path)
    records = uni.get("records", [])

    # Token encoding (approx for GPT-4.1)
    try:
        enc = tiktoken.get_encoding("o200k_base")
    except Exception:
        enc = tiktoken.get_encoding("cl100k_base")

    client = None
    if not args.no_summaries:
        api_key = load_api_key()
        client = OpenAI(api_key=api_key)

    out_dir = profile_dir / args.out_dir
    items_dir = out_dir / "items"

    # merge existing docs records (to retain summaries/topics between runs)
    docs_records_path = out_dir / "records.json"
    if docs_records_path.exists():
        try:
            old_records = load_json(docs_records_path).get("records", [])
            old_by_id = {r.get("id"): r for r in old_records if r.get("id")}
            for rec in records:
                old = old_by_id.get(rec.get("id"))
                if not old:
                    continue
                for key in (
                    "summary",
                    "topics",
                    "keywords",
                    "summary_error",
                ):
                    if old.get(key):
                        rec[key] = old[key]
        except Exception:
            pass

    summaries_done = 0
    for rec in records:
        transcript = (rec.get("transcript") or {}).get("text") if isinstance(rec.get("transcript"), dict) else ""
        captions = rec.get("captions") or []
        caps_text = "\n".join([c.get("text", "") for c in captions if isinstance(c, dict) and c.get("text")])

        rec["transcript_tokens"] = token_count(transcript, enc)
        rec["captions_tokens"] = token_count(caps_text, enc)
        rec["total_tokens"] = rec["transcript_tokens"] + rec["captions_tokens"]
        rec["char_count"] = len(transcript)
        rec["word_count"] = len(transcript.split())

        if args.no_summaries:
            continue

        if args.skip_existing and rec.get("summary") and rec.get("topics"):
            continue

        if args.max and summaries_done >= args.max:
            continue

        try:
            if args.verbose:
                print(f"Summarizing {rec.get('id')}...")
            data = summarize_item(client, rec, args.summary_model)
            rec["summary"] = data.get("summary_de", "")
            rec["topics"] = data.get("topics", [])
            rec["keywords"] = data.get("keywords", [])
            rec.pop("summary_error", None)
            summaries_done += 1
        except Exception as exc:
            rec["summary_error"] = str(exc)

        if args.sleep > 0:
            time.sleep(args.sleep)

    # Dataset-level summary
    dataset_summary = {}
    if not args.no_summaries:
        try:
            dataset_summary = summarize_dataset(client, records, args.summary_model)
        except Exception as exc:
            dataset_summary = {"overview_de": "", "top_themes": [], "suggested_use_cases": [], "error": str(exc)}

    # Write per-item markdown + json
    for rec in records:
        vid = rec.get("id")
        if not vid:
            continue
        write_json(items_dir / f"{vid}.json", rec)
        (items_dir / f"{vid}.md").write_text(build_item_md(rec), encoding="utf-8")

    # Build overview
    total_tokens = sum(r.get("total_tokens", 0) for r in records)
    overview = {
        "profile": uni.get("profile"),
        "username": uni.get("username"),
        "generated_at": iso_now(),
        "counts": {
            "records": len(records),
            "audio": sum(1 for r in records if r.get("audio_path")),
            "captions": sum(1 for r in records if r.get("captions")),
            "transcripts": sum(1 for r in records if r.get("transcript")),
        },
        "token_stats": {
            "total_tokens": total_tokens,
            "avg_tokens_per_video": round(total_tokens / max(len(records), 1), 2),
        },
        "dataset_summary": dataset_summary,
    }

    write_json(out_dir / "overview.json", overview)
    write_json(out_dir / "records.json", {"records": records})
    write_jsonl(out_dir / "records.jsonl", records)

    # Markdown overview
    md = [
        f"# Dataset Overview ({uni.get('username')})",
        "",
        f"Generated at: {overview['generated_at']}",
        "",
        "## Counts",
        f"- Records: {overview['counts']['records']}",
        f"- Audio: {overview['counts']['audio']}",
        f"- Captions: {overview['counts']['captions']}",
        f"- Transcripts: {overview['counts']['transcripts']}",
        "",
        "## Token Stats",
        f"- Total tokens (transcripts + captions): {overview['token_stats']['total_tokens']}",
        f"- Avg tokens per video: {overview['token_stats']['avg_tokens_per_video']}",
        "",
    ]
    if dataset_summary.get("overview_de"):
        md += ["## Summary (DE)", "", dataset_summary.get("overview_de", ""), ""]
    if dataset_summary.get("top_themes"):
        md += ["## Top Themes", "", ", ".join(dataset_summary.get("top_themes", [])), ""]
    if dataset_summary.get("suggested_use_cases"):
        md += ["## Suggested Use Cases", "", "\n".join([f"- {u}" for u in dataset_summary.get("suggested_use_cases", [])]), ""]

    (out_dir / "overview.md").write_text("\n".join(md).strip() + "\n", encoding="utf-8")

    if args.verbose:
        print(f"Wrote docs to {out_dir}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
