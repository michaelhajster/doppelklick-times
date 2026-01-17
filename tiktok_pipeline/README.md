# TikTok audio + metadata pipeline

This pulls all videos from a TikTok profile and saves:
- audio files (mp3 if ffmpeg is available)
- metadata in JSON and JSONL
- optional TikTok captions (if available) as VTT and plain text

## Setup

```
python3 -m pip install -r tiktok_pipeline/requirements.txt
```

## Run

Recommended (embed pipeline, more reliable for all videos):

```
python3 tiktok_pipeline/embed_pipeline.py --profile @mr.doppelklick --write-subs --verbose
```

Then build a unified dataset + per-item files + OpenAI transcripts:

```
python3 tiktok_pipeline/build_dataset.py --profile mr.doppelklick --model gpt-4o-transcribe --skip-existing --verbose
```

Outputs:

```
./data/<username>/unified.json
./data/<username>/items/<id>.json
./data/<username>/transcripts/<id>.json
```

Generate high-quality documentation (token stats, summaries, topics):

```
python3 tiktok_pipeline/describe_dataset.py --profile mr.doppelklick --summary-model gpt-4.1 --skip-existing --verbose
```

Docs output:

```
./data/<username>/docs/overview.md
./data/<username>/docs/records.jsonl
./data/<username>/docs/items/<id>.md
```

Build hybrid RAG embeddings index:

```
python3 tiktok_pipeline/build_rag_index.py --profile mr.doppelklick --model text-embedding-3-large --verbose
```

Run answer API (full-context or hybrid RAG):

```
python3 -m uvicorn tiktok_pipeline.answer_api:app --host 0.0.0.0 --port 8000
```

Example request:

```
curl -X POST http://localhost:8000/answer \\
  -H 'Content-Type: application/json' \\
  -d '{\"question\":\"Was sind die wichtigsten Hooks?\",\"mode\":\"full\",\"model\":\"gpt-4.1\"}'
```

Basic (download all audio for a profile):

```
python3 tiktok_pipeline/pipeline.py --profile https://www.tiktok.com/@mr.doppelklick --verbose
```

With subtitles (TikTok captions), if available:

```
python3 tiktok_pipeline/pipeline.py --profile @mr.doppelklick --write-subs --verbose
```

Limit to first N videos (useful for testing):

```
python3 tiktok_pipeline/pipeline.py --profile @mr.doppelklick --max-videos 5 --verbose
```

Resume without re-downloading existing audio:

```
python3 tiktok_pipeline/pipeline.py --profile @mr.doppelklick --skip-existing --verbose
```

Output goes to:

```
./data/<username>/
  audio/
  index.json
  videos.jsonl
```

## Cookies (if TikTok blocks requests)

If TikTok blocks scraping, export cookies in Netscape format and pass:

```
python3 tiktok_pipeline/pipeline.py --profile @mr.doppelklick --cookies /path/to/cookies.txt --verbose
```

A common method is a browser extension that exports cookies.txt for tiktok.com.

Alternatively, use cookies directly from an installed browser profile:

```
python3 tiktok_pipeline/pipeline.py --profile @mr.doppelklick --cookies-from-browser chrome --verbose
```

If TikTok blocks direct webpage extraction for videos, force the app API:

```
python3 tiktok_pipeline/pipeline.py --profile @mr.doppelklick --force-app-api --verbose
```

## Notes

- If ffmpeg is not installed, audio is saved in the original container (e.g. m4a).
- Captions are only saved if TikTok provides them for a video.
