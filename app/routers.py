import time
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from app.config import STATIC_DIR
from app.extractor import extract_text_from_file
from app.github_processor import process_github
from app.ai import analyze

router = APIRouter()

INDEX_HTML = (STATIC_DIR / "index.html").read_text() if (STATIC_DIR / "index.html").exists() else ""
PROMPT_TEMPLATE = Path("prompts/analyze_cv.txt").read_text()

EXTRACTED_DIR = Path("extracted")
EXTRACTED_DIR.mkdir(exist_ok=True)
HISTORY_DIR = Path("history")
HISTORY_DIR.mkdir(exist_ok=True)


@router.get("/")
async def serve_app():
    return HTMLResponse(INDEX_HTML if INDEX_HTML else "<h1>Talent Analyzer</h1><p>index.html not found in static/</p>")


@router.get("/github-process/{username}")
async def github_process(username: str):
    result = await process_github(username)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return {
        "username": result["username"],
        "repo_count": result["repo_count"],
        "readmes_fetched": result["readmes_fetched"],
        "languages": result["languages"],
        "skills": result["skills"],
        "saved_as": result["saved_as"],
        "content": result["content"],
    }


@router.post("/analyze-cv")
async def analyze_cv(file: UploadFile = File(...), github_username: str = Form("")):
    if not file.filename:
        raise HTTPException(400, "No file provided")

    try:
        cv_text = await extract_text_from_file(file)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(422, f"Failed to extract text from CV: {e}")

    stem = Path(file.filename).stem
    ts = str(int(time.time()))
    cv_out = EXTRACTED_DIR / f"cv_{stem}_{ts}.txt"
    cv_out.write_text(cv_text)

    github_info = None
    if github_username.strip():
        try:
            gh = await process_github(github_username)
        except Exception:
            gh = {"error": f"GitHub lookup unavailable for '{github_username}'"}

        if "error" not in gh:
            github_info = gh
            with open(cv_out, "a") as f:
                f.write(f"\n\n--- GITHUB PROFILE DATA ---\n{gh['content']}")

    combined_text = cv_out.read_text()

    summary_prompt = PROMPT_TEMPLATE.format(cv_text=combined_text)
    result = await analyze(summary_prompt)

    history_record = result["response"] if isinstance(result["response"], dict) else {"raw": str(result["response"])}
    if github_info:
        history_record["github"] = {
            "username": github_info["username"],
            "repo_count": github_info["repo_count"],
            "readmes_fetched": github_info["readmes_fetched"],
            "languages": github_info["languages"],
            "skills": github_info["skills"],
        }

    history_out = HISTORY_DIR / f"{stem}_{ts}.json"
    history_out.write_text(json.dumps(history_record, indent=2))

    if cv_out.exists():
        cv_out.unlink()

    return {
        "filename": file.filename,
        "history_saved_as": str(history_out),
        "extracted_text": cv_text,
        "char_count": len(cv_text),
        "github_username": github_username or None,
        "github": github_info,
        "analysis": result["response"],
        "engine": result["engine"],
    }
