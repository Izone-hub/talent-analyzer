# Talent Analyzer

AI-powered CV analysis tool that extracts text from resumes, enriches it with GitHub profile data, and returns a structured ATS analysis with scores, checks, and suggested profile fields.

## Architecture

```
main.py              ← FastAPI app entry point
app/
├── config.py        ← ENVIRONMENT, OPENCODE_URL, GEMINI_API_KEY, MAX_CV_CHARS
├── extractor.py     ← PDF / DOCX / TXT text extraction (pypdf, python-docx)
├── condense.py      ← Text cleaning & section prioritisation (2500 char cap)
├── ai.py            ← AI engine: local OpenCode (dev) / Gemini (prod) + fallback
├── github_processor.py  ← GitHub repos, READMEs, language & skill extraction
└── routers.py       ← Routes: GET /, POST /analyze-cv
prompts/
└── analyze_cv.txt   ← AI prompt template (editable without touching Python)theme
history/             ← Persisted analysis results (JSON)
extracted/           ← Temp CV text files (auto-cleaned after analysis)
```

## Flow

```
Upload CV + GitHub username (optional)
        │
        ▼
Extract text ← PDF / DOCX / TXT (local, no API calls)
        │
        ▼
Condense → 2500 char cap, section prioritised
        │
        ▼
GitHub fetch ← repos, READMEs, languages, skills (background)
        │
        ▼
Merge CV + GitHub → appended to temp file, sent to AI
        │
        ▼
AI analysis → JSON: ats_score, score_breakdown, checks, suggested_fields
        │
        ▼
Save history/ → {stem}_{ts}.json + GitHub data embedded
Cleanup → temp extracted/ file deleted
```

## Quick Start

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Open `http://localhost:8000`.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `ENVIRONMENT` | `development` | `development` → local OpenCode; `production` → Gemini |
| `OPENCODE_URL` | `http://localhost:4096` | OpenCode session endpoint |
| `OPENCODE_URL` | `http://localhost:4096` | Alias for `OPENCODE_URL` if your env uses the alternate spelling |
| `GEMINI_API_KEY` | — | Required when ENVIRONMENT=production or OpenCode unreachable |

Example `.env`:

```env
ENVIRONMENT=development
OPENCODE_URL=http://localhost:4096
GEMINI_API_KEY=
```

## API

### `POST /analyze-cv`

Upload a CV file with an optional GitHub username.

- **file** (required) — PDF, DOCX, or TXT
- **github_username** (optional) — GitHub profile to enrich analysis

Returns extracted text, ATS analysis JSON, engine used, and history file path.
