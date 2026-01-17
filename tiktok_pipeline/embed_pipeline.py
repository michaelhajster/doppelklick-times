#!/usr/bin/env python3
"""
TikTok pipeline using the public embed page + creator item_list API.
- Lists all videos via creator/item_list
- Fetches per-video data from /embed/v2/<id>
- Downloads audio via ffmpeg directly from embed video URL
- Downloads TikTok captions from subtitleInfos (VTT)
"""

from __future__ import annotations

import argparse
import json
import random
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen

USER_AGENT = "Mozilla/5.0"

PROFILE_RE = re.compile(r"tiktok\.com/@([A-Za-z0-9_.-]+)")
FRONTITY_RE = re.compile(
    r'<script id="__FRONTITY_CONNECT_STATE__" type="application/json">(.*?)</script>'
)


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
        return {"username": "unknown", "url": profile}

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
            line = re.sub(r"<[^>]+>", "", line)
            lines.append(line)

    cleaned: List[str] = []
    last = None
    for line in lines:
        if line != last:
            cleaned.append(line)
        last = line
    return " ".join(cleaned).strip()


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=True, indent=2)


def write_jsonl(path: Path, rows: Iterable[Dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=True) + "\n")


def fetch_url(url: str, headers: Optional[Dict[str, str]] = None, timeout: int = 20) -> str:
    req = Request(url, headers=headers or {"User-Agent": USER_AGENT})
    with urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def fetch_sec_uid(profile_url: str) -> Optional[str]:
    html = fetch_url(profile_url, headers={"User-Agent": USER_AGENT})
    m = re.search(r'"secUid"\s*:\s*"(.*?)"', html)
    return m.group(1) if m else None


def fetch_creator_items(sec_uid: str, max_videos: int, verbose: bool) -> List[Dict]:
    seen = set()
    items: List[Dict] = []
    cursor = int(time.time() * 1e3)

    no_new_pages = 0
    for page in range(1, 200):
        device_id = str(random.randint(7250000000000000000, 7351147085025500000))
        params = {
            "aid": "1988",
            "app_language": "en",
            "app_name": "tiktok_web",
            "browser_language": "en-US",
            "browser_name": "Mozilla",
            "browser_online": "true",
            "browser_platform": "Win32",
            "browser_version": "5.0 (Windows)",
            "channel": "tiktok_web",
            "cookie_enabled": "true",
            "count": "15",
            "cursor": str(cursor),
            "device_id": device_id,
            "device_platform": "web_pc",
            "focus_state": "true",
            "from_page": "user",
            "history_len": "2",
            "is_fullscreen": "false",
            "is_page_visible": "true",
            "language": "en",
            "os": "windows",
            "priority_region": "",
            "referer": "",
            "region": "US",
            "screen_height": "1080",
            "screen_width": "1920",
            "secUid": sec_uid,
            "type": "1",
            "tz_name": "UTC",
            "verifyFp": "verify_" + "".join(random.choice("0123456789abcdef") for _ in range(7)),
            "webcast_language": "en",
        }
        url = "https://www.tiktok.com/api/creator/item_list/?" + urlencode(params)
        raw = fetch_url(url, headers={"User-Agent": USER_AGENT})
        obj = json.loads(raw)
        lst = obj.get("itemList") or []
        if not lst:
            no_new_pages += 1
            if no_new_pages >= 3:
                break
            cursor -= 7 * 86400000
            continue

        added = 0
        for it in lst:
            vid = it.get("id")
            if not vid or vid in seen:
                continue
            seen.add(vid)
            items.append(it)
            added += 1
            if max_videos and len(items) >= max_videos:
                return items

        last = lst[-1].get("createTime")
        if last:
            next_cursor = int(last * 1000)
            if next_cursor == cursor:
                cursor -= 7 * 86400000
            else:
                cursor = next_cursor
        else:
            cursor -= 7 * 86400000

        if added == 0:
            no_new_pages += 1
        else:
            no_new_pages = 0
        if no_new_pages >= 3:
            break
        if cursor < 1472706000000:
            break

        if verbose:
            print(f"Fetched page {page}, total {len(items)}")

    return items


def fetch_embed_data(video_id: str) -> Optional[Dict]:
    embed_url = f"https://www.tiktok.com/embed/v2/{video_id}"
    html = fetch_url(embed_url, headers={"User-Agent": USER_AGENT})
    m = FRONTITY_RE.search(html)
    if not m:
        return None
    data = json.loads(m.group(1))
    return data.get("source", {}).get("data", {}).get(f"/embed/v2/{video_id}")


def download_caption(sub_url: str, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    req = Request(sub_url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=20) as resp:
        out_path.write_bytes(resp.read())


def extract_audio_from_video_url(video_url: str, embed_url: str, out_mp3: Path) -> None:
    out_mp3.parent.mkdir(parents=True, exist_ok=True)
    headers = f"User-Agent: {USER_AGENT}\r\nReferer: {embed_url}\r\n"
    cmd = [
        "ffmpeg",
        "-y",
        "-headers",
        headers,
        "-i",
        video_url,
        "-vn",
        "-af",
        "aformat=sample_fmts=s16p",
        "-acodec",
        "libmp3lame",
        "-q:a",
        "2",
        str(out_mp3),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main() -> int:
    parser = argparse.ArgumentParser(description="TikTok embed pipeline")
    parser.add_argument("--profile", required=True, help="TikTok profile URL or username")
    parser.add_argument("--out", default="data", help="Output root directory")
    parser.add_argument("--max-videos", type=int, default=0, help="Limit videos (0 = all)")
    parser.add_argument("--skip-existing", action="store_true", help="Skip videos that already have audio")
    parser.add_argument("--write-subs", action="store_true", help="Download subtitles/captions if available")
    parser.add_argument("--sleep", type=float, default=0.0, help="Sleep seconds between requests")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging")

    args = parser.parse_args()

    profile_info = normalize_profile(args.profile)
    username = profile_info["username"]
    profile_url = profile_info["url"]

    out_root = Path(args.out).resolve()
    profile_dir = out_root / username
    audio_dir = profile_dir / "audio"
    profile_dir.mkdir(parents=True, exist_ok=True)
    audio_dir.mkdir(parents=True, exist_ok=True)

    sec_uid = fetch_sec_uid(profile_url)
    if not sec_uid:
        raise SystemExit("ERROR: Unable to extract secUid from profile page")

    items = fetch_creator_items(sec_uid, args.max_videos, args.verbose)
    if args.verbose:
        print(f"Found {len(items)} items")

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

    for i, it in enumerate(items, start=1):
        vid = it.get("id")
        if not vid:
            continue
        if args.skip_existing and vid in existing_records and existing_records[vid].get("audio_path"):
            records.append(existing_records[vid])
            continue

        if args.verbose:
            print(f"[{i}/{len(items)}] {vid}")

        record: Dict = {
            "id": vid,
            "url": f"https://www.tiktok.com/@{username}/video/{vid}",
            "description": it.get("desc"),
            "timestamp": it.get("createTime"),
            "view_count": (it.get("stats") or {}).get("playCount"),
            "like_count": (it.get("stats") or {}).get("diggCount"),
            "comment_count": (it.get("stats") or {}).get("commentCount"),
            "repost_count": (it.get("stats") or {}).get("shareCount"),
            "uploader_id": (it.get("author") or {}).get("id"),
            "uploader": (it.get("author") or {}).get("uniqueId"),
            "source": "tiktok",
            "extracted_at": iso_now(),
        }

        embed_url = f"https://www.tiktok.com/embed/v2/{vid}"
        try:
            embed_data = fetch_embed_data(vid)
            if embed_data:
                video_data = embed_data.get("videoData", {})
                item_infos = (video_data.get("itemInfos") or {})
                video_info = item_infos.get("video") or {}
                video_urls = video_info.get("urls") or []
                music_infos = video_data.get("musicInfos") or {}
                author_infos = video_data.get("authorInfos") or {}

                record["title"] = item_infos.get("text")
                record["duration"] = (video_info.get("videoMeta") or {}).get("duration")
                record["uploader"] = author_infos.get("uniqueId") or record.get("uploader")
                record["uploader_id"] = author_infos.get("userId") or record.get("uploader_id")
                record["embed_url"] = embed_url
                record["embed_video_url"] = video_urls[0] if video_urls else None
                record["music_play_url"] = (music_infos.get("playUrl") or [None])[0]

                # download audio from embed video url
                if video_urls:
                    out_mp3 = audio_dir / f"{vid}.mp3"
                    extract_audio_from_video_url(video_urls[0], embed_url, out_mp3)
                    record["audio_path"] = str(out_mp3.relative_to(profile_dir))
                    record["audio_ext"] = "mp3"
                elif record.get("music_play_url"):
                    # fallback: use music-only URL (slideshows)
                    out_mp3 = audio_dir / f"{vid}.mp3"
                    extract_audio_from_video_url(record["music_play_url"], embed_url, out_mp3)
                    record["audio_path"] = str(out_mp3.relative_to(profile_dir))
                    record["audio_ext"] = "mp3"
                else:
                    record["error"] = "No video URLs found in embed data"
            else:
                record["error"] = "No embed data found"
        except Exception as exc:
            record["error"] = str(exc)

        # captions via item_list subtitleInfos
        if args.write_subs:
            try:
                subs = (it.get("video") or {}).get("subtitleInfos") or []
                if subs:
                    caps = []
                    for s in subs:
                        lang = s.get("LanguageCodeName") or s.get("LanguageID") or "unknown"
                        sub_url = s.get("Url")
                        if not sub_url:
                            continue
                        out_vtt = audio_dir / f"{vid}.{lang}.vtt"
                        download_caption(sub_url, out_vtt)
                        caps.append(
                            {
                                "path": str(out_vtt.relative_to(profile_dir)),
                                "ext": "vtt",
                                "lang": lang,
                                "text": vtt_to_text(out_vtt),
                            }
                        )
                    if caps:
                        record["captions"] = caps
            except Exception as exc:
                record["captions_error"] = str(exc)

        records.append(record)
        if args.sleep > 0:
            time.sleep(args.sleep)

    # merge any previous records that were not returned in this run
    record_ids = {r.get("id") for r in records if r.get("id")}
    for rid, rec in existing_records.items():
        if rid not in record_ids:
            records.append(rec)

    output = {
        "profile": profile_url,
        "username": username,
        "count": len(records),
        "generated_at": iso_now(),
        "records": records,
    }

    write_json(index_path, output)
    write_jsonl(profile_dir / "videos.jsonl", records)

    if args.verbose:
        print(f"Wrote: {index_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
