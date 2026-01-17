#!/usr/bin/env python3
"""
TikTok audio + metadata pipeline using yt-dlp.
- Accepts profile URL or username.
- Downloads audio (mp3 if ffmpeg available).
- Optionally downloads subtitles (TikTok captions) and parses to text.
- Writes JSON and JSONL index files.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

try:
    from yt_dlp import YoutubeDL
except Exception as exc:  # pragma: no cover
    print("ERROR: yt-dlp is not installed. Run: python3 -m pip install -r tiktok_pipeline/requirements.txt", file=sys.stderr)
    raise


PROFILE_RE = re.compile(r"tiktok\.com/@([A-Za-z0-9_.-]+)")


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_profile(profile: str) -> Dict[str, str]:
    profile = profile.strip()
    if profile.startswith("@"):
        username = profile[1:]
        url = f"https://www.tiktok.com/@{username}"
        return {"username": username, "url": url}

    if "tiktok.com" in profile:
        m = PROFILE_RE.search(profile)
        if m:
            username = m.group(1)
            url = f"https://www.tiktok.com/@{username}"
            return {"username": username, "url": url}
        # fallback if url does not match regex
        return {"username": "unknown", "url": profile}

    # assume raw username
    username = profile
    url = f"https://www.tiktok.com/@{username}"
    return {"username": username, "url": url}


def vtt_to_text(vtt_path: Path) -> str:
    lines: List[str] = []
    with vtt_path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith("WEBVTT"):
                continue
            if "-->" in line:
                continue
            # strip simple tags
            line = re.sub(r"<[^>]+>", "", line)
            lines.append(line)

    # de-duplicate consecutive duplicates
    cleaned: List[str] = []
    last = None
    for line in lines:
        if line != last:
            cleaned.append(line)
        last = line
    return " ".join(cleaned).strip()


def find_caption_files(base_dir: Path, video_id: str) -> List[Path]:
    # yt-dlp uses patterns like <id>.<lang>.vtt or <id>.vtt
    matches = list(base_dir.glob(f"{video_id}*.vtt"))
    return sorted(matches)


def build_ydl_opts(
    audio_dir: Path,
    cookies: Optional[str],
    cookies_from_browser: Optional[str],
    extractor_args: Optional[Dict[str, Dict[str, List[str]]]],
    download_audio: bool,
    write_subs: bool,
    sub_langs: Optional[List[str]],
    verbose: bool,
) -> Dict:
    ydl_opts: Dict = {
        "quiet": not verbose,
        "no_warnings": not verbose,
        "ignoreerrors": False,
        "retries": 5,
        "fragment_retries": 5,
        "concurrent_fragment_downloads": 1,
        "outtmpl": str(audio_dir / "%(id)s.%(ext)s"),
        "restrictfilenames": True,
    }

    if cookies:
        ydl_opts["cookiefile"] = cookies
    if cookies_from_browser:
        # tuple: (browser_name, profile, keyring, container)
        parts = cookies_from_browser.split(":", 1)
        browser_name = parts[0]
        profile = parts[1] if len(parts) > 1 and parts[1] else None
        ydl_opts["cookiesfrombrowser"] = (browser_name, profile, None, None)
    if extractor_args:
        ydl_opts["extractor_args"] = extractor_args

    if download_audio:
        ydl_opts["format"] = "bestaudio/best"
        if shutil.which("ffmpeg"):
            ydl_opts["postprocessors"] = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ]
        else:
            # fallback: keep original audio container
            ydl_opts["postprocessors"] = []
    else:
        ydl_opts["skip_download"] = True

    if write_subs:
        ydl_opts["writesubtitles"] = True
        ydl_opts["writeautomaticsub"] = True
        ydl_opts["subtitlesformat"] = "vtt"
        if sub_langs and sub_langs != ["all"]:
            ydl_opts["subtitleslangs"] = sub_langs

    return ydl_opts


def list_profile_videos(
    profile_url: str,
    cookies: Optional[str],
    cookies_from_browser: Optional[str],
    verbose: bool,
    max_videos: int,
) -> List[Dict]:
    # extract_flat to quickly list entries without full metadata
    ydl_opts: Dict = {
        "quiet": not verbose,
        "no_warnings": not verbose,
        "ignoreerrors": True,
        "extract_flat": True,
        "dump_single_json": True,
    }
    if max_videos and max_videos > 0:
        ydl_opts["playlistend"] = max_videos
    if cookies:
        ydl_opts["cookiefile"] = cookies
    if cookies_from_browser:
        parts = cookies_from_browser.split(":", 1)
        browser_name = parts[0]
        profile = parts[1] if len(parts) > 1 and parts[1] else None
        ydl_opts["cookiesfrombrowser"] = (browser_name, profile, None, None)

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(profile_url, download=False)

    entries = info.get("entries") or []
    videos: List[Dict] = []
    for entry in entries:
        if not entry:
            continue
        video_id = entry.get("id")
        url = entry.get("url") or entry.get("webpage_url")
        if not url and video_id:
            # best effort
            url = f"https://www.tiktok.com/@unknown/video/{video_id}"
        if not url:
            continue
        videos.append({"id": video_id, "url": url})
    return videos


def extract_video(
    video_url: str,
    ydl: YoutubeDL,
    ydl_fallback: Optional[YoutubeDL],
    download_audio: bool,
    sleep_requests: float,
) -> Optional[Dict]:
    try:
        info = ydl.extract_info(video_url, download=download_audio)
        if info is None and ydl_fallback:
            info = ydl_fallback.extract_info(video_url, download=download_audio)
    except Exception as exc:
        if ydl_fallback:
            try:
                info = ydl_fallback.extract_info(video_url, download=download_audio)
            except Exception as exc2:
                return {"url": video_url, "error": str(exc2), "error_primary": str(exc)}
        else:
            return {"url": video_url, "error": str(exc)}
    finally:
        if sleep_requests > 0:
            time.sleep(sleep_requests)

    return info


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=True, indent=2)


def write_jsonl(path: Path, rows: Iterable[Dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="TikTok audio + metadata pipeline")
    parser.add_argument("--profile", required=True, help="TikTok profile URL or username")
    parser.add_argument("--out", default="data", help="Output root directory")
    parser.add_argument("--cookies", default=None, help="Path to cookies.txt (Netscape format)")
    parser.add_argument(
        "--cookies-from-browser",
        default=None,
        help="Browser name optionally with profile, e.g. chrome or chrome:Profile 1",
    )
    parser.add_argument("--write-subs", action="store_true", help="Download subtitles/captions if available")
    parser.add_argument("--sub-lang", default="all", help="Comma-separated subtitle langs, or 'all'")
    parser.add_argument("--max-videos", type=int, default=0, help="Limit videos (0 = all)")
    parser.add_argument("--no-download-audio", action="store_true", help="Skip audio download")
    parser.add_argument("--skip-existing", action="store_true", help="Skip videos that already have audio")
    parser.add_argument("--sleep", type=float, default=0.0, help="Sleep seconds between requests")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging")
    parser.add_argument("--device-id", default=None, help="TikTok device_id to force app API")
    parser.add_argument("--app-info", default=None, help="TikTok app_info string to force app API")
    parser.add_argument("--force-app-api", action="store_true", help="Force app API extraction")

    args = parser.parse_args()

    profile_info = normalize_profile(args.profile)
    username = profile_info["username"]
    profile_url = profile_info["url"]

    out_root = Path(args.out).resolve()
    profile_dir = out_root / username
    audio_dir = profile_dir / "audio"
    meta_dir = profile_dir / "meta"
    audio_dir.mkdir(parents=True, exist_ok=True)
    meta_dir.mkdir(parents=True, exist_ok=True)

    sub_langs = [s.strip() for s in args.sub_lang.split(",") if s.strip()]
    if not sub_langs:
        sub_langs = ["all"]

    download_audio = not args.no_download_audio

    extractor_args = None
    force_app_api = args.force_app_api or args.device_id or args.app_info
    if force_app_api:
        device_id = args.device_id
        if not device_id:
            device_id = str(random.randint(7250000000000000000, 7351147085025500000))
        extractor_args = {"tiktok": {"device_id": [device_id]}}
        if args.app_info:
            extractor_args["tiktok"]["app_info"] = [args.app_info]

    if args.verbose:
        print(f"Profile: {profile_url}")
        print(f"Output: {profile_dir}")

    videos = list_profile_videos(
        profile_url, args.cookies, args.cookies_from_browser, args.verbose, args.max_videos
    )
    if args.max_videos > 0:
        videos = videos[: args.max_videos]

    if args.verbose:
        print(f"Found {len(videos)} video entries")

    ydl_opts = build_ydl_opts(
        audio_dir=audio_dir,
        cookies=args.cookies,
        cookies_from_browser=args.cookies_from_browser,
        extractor_args=None,
        download_audio=download_audio,
        write_subs=args.write_subs,
        sub_langs=sub_langs,
        verbose=args.verbose,
    )
    ydl_app_opts = None
    if extractor_args:
        ydl_app_opts = build_ydl_opts(
            audio_dir=audio_dir,
            cookies=args.cookies,
            cookies_from_browser=args.cookies_from_browser,
            extractor_args=extractor_args,
            download_audio=download_audio,
            write_subs=args.write_subs,
            sub_langs=sub_langs,
            verbose=args.verbose,
        )

    existing_records: Dict[str, Dict] = {}
    index_path = profile_dir / "index.json"
    if index_path.exists():
        try:
            existing = json.loads(index_path.read_text(encoding="utf-8"))
            for r in existing.get("records", []):
                if r.get("id"):
                    existing_records[r["id"]] = r
        except Exception:
            existing_records = {}

    records: List[Dict] = []
    with YoutubeDL(ydl_opts) as ydl:
        ydl_app = YoutubeDL(ydl_app_opts) if ydl_app_opts else None
        try:
            for i, vid in enumerate(videos, start=1):
                url = vid["url"]
                vid_id = vid.get("id")
                if args.skip_existing and vid_id and vid_id in existing_records:
                    if existing_records[vid_id].get("audio_path"):
                        records.append(existing_records[vid_id])
                        continue
                if args.verbose:
                    print(f"[{i}/{len(videos)}] {url}")
                info = extract_video(url, ydl, ydl_app, download_audio, args.sleep) or {}

                record: Dict = {
                    "id": info.get("id") or vid.get("id"),
                    "url": info.get("webpage_url") or url,
                    "title": info.get("title"),
                    "description": info.get("description"),
                    "uploader": info.get("uploader"),
                    "uploader_id": info.get("uploader_id"),
                    "timestamp": info.get("timestamp"),
                    "upload_date": info.get("upload_date"),
                    "duration": info.get("duration"),
                    "view_count": info.get("view_count"),
                    "like_count": info.get("like_count"),
                    "comment_count": info.get("comment_count"),
                    "repost_count": info.get("repost_count"),
                    "source": "tiktok",
                    "extracted_at": iso_now(),
                    "error": info.get("error"),
                }

                video_id = record.get("id")
                if video_id:
                    # try to locate audio file
                    mp3_path = audio_dir / f"{video_id}.mp3"
                    if mp3_path.exists():
                        record["audio_path"] = str(mp3_path.relative_to(profile_dir))
                        record["audio_ext"] = "mp3"
                    else:
                        # fallback: pick first audio file with id prefix
                        candidates = list(audio_dir.glob(f"{video_id}.*"))
                        if candidates:
                            record["audio_path"] = str(candidates[0].relative_to(profile_dir))
                            record["audio_ext"] = candidates[0].suffix.lstrip(".")

                    # locate captions
                    caption_files = find_caption_files(audio_dir, video_id)
                    if caption_files:
                        caps = []
                        for p in caption_files:
                            caps.append(
                                {
                                    "path": str(p.relative_to(profile_dir)),
                                    "ext": p.suffix.lstrip("."),
                                    "text": vtt_to_text(p),
                                }
                            )
                        record["captions"] = caps

                records.append(record)
        finally:
            if ydl_app:
                ydl_app.close()

    jsonl_path = profile_dir / "videos.jsonl"

    output = {
        "profile": profile_url,
        "username": username,
        "count": len(records),
        "generated_at": iso_now(),
        "records": records,
    }

    write_json(index_path, output)
    write_jsonl(jsonl_path, records)

    if args.verbose:
        print(f"Wrote: {index_path}")
        print(f"Wrote: {jsonl_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
