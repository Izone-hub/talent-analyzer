import time
import json
import logging
from pathlib import Path
from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from app.config import STATIC_DIR
from app.extractor import extract_text_from_file
from app.github_processor import process_github
from app.ai import analyze
from app.send_email import send_contact_email, send_contact_reply_email, send_job_acceptance_email

router = APIRouter()
logger = logging.getLogger(__name__)

INDEX_HTML = (STATIC_DIR / "index.html").read_text() if (STATIC_DIR / "index.html").exists() else ""
PROMPT_TEMPLATE = Path("prompts/analyze_cv.txt").read_text()
JOB_DESC_PROMPT = Path("prompts/generate_job_description.txt").read_text()
QUESTION_PROMPT = Path("prompts/generate_questions.txt").read_text()
EXTRACTED_DIR = Path("extracted")
EXTRACTED_DIR.mkdir(exist_ok=True)
HISTORY_DIR = Path("history")
HISTORY_DIR.mkdir(exist_ok=True)


def cleanup_temp_artifacts(*path_values: str) -> None:
    for path_value in path_values:
        if not path_value:
            continue

        path = Path(path_value)
        try:
            if path.exists():
                path.unlink()
        except OSError:
            pass

    for directory in (EXTRACTED_DIR, HISTORY_DIR):
        try:
            if directory.exists() and not any(directory.iterdir()):
                directory.rmdir()
        except OSError:
            pass


@router.get("/")
async def serve_app():
    return HTMLResponse(INDEX_HTML if INDEX_HTML else "<h1>Talent Analyzer</h1><p>index.html not found in static/</p>")


@router.get("/github-process/{username}")
async def github_process(username: str, background_tasks: BackgroundTasks):
    result = await process_github(username)
    if "error" in result:
        raise HTTPException(404, result["error"])
    background_tasks.add_task(cleanup_temp_artifacts, result.get("saved_as", ""))
    return {
        "username": result["username"],
        "repo_count": result["repo_count"],
        "readmes_fetched": result["readmes_fetched"],
        "languages": result["languages"],
        "skills": result["skills"],
        "saved_as": result["saved_as"],
        "content": result["content"],
    }


class GenerateJobDescriptionRequest(BaseModel):
    prompt: str
    company_name: str = ""


@router.post("/generate-job-description")
async def generate_job_description(req: GenerateJobDescriptionRequest):
    if not req.prompt.strip():
        raise HTTPException(400, "prompt is required")

    full_prompt = JOB_DESC_PROMPT.format(prompt=req.prompt)
    result = await analyze(full_prompt)
    return {
        "job_description": result["response"],
        "engine": result["engine"],
    }


class GenerateQuestionsRequest(BaseModel):
    prompt: str
    question_type: str = ""
    difficulty: str = ""


@router.post("/generate-questions")
async def generate_questions(req: GenerateQuestionsRequest):
    if not req.prompt.strip():
        raise HTTPException(400, "prompt is required")

    user_prompt = req.prompt
    if req.question_type:
        user_prompt += f"\n\nQuestion type: {req.question_type}"
    if req.difficulty:
        user_prompt += f"\n\nDifficulty: {req.difficulty}"

    full_prompt = QUESTION_PROMPT.format(prompt=user_prompt)
    result = await analyze(full_prompt)
    return {
        "questions": result["response"],
        "engine": result["engine"],
    }


class ContactRequest(BaseModel):
    first_name: str = Field(min_length=1)
    last_name: str = Field(min_length=1)
    email: str = Field(min_length=3)
    company: str = ""
    budget_range: str = ""
    project_details: str = Field(min_length=1)


@router.post("/api/v1/contact")
async def contact(req: ContactRequest):
    try:
        send_contact_email(
            first_name=req.first_name,
            last_name=req.last_name,
            email=req.email,
            company=req.company,
            budget_range=req.budget_range,
            project_details=req.project_details,
        )
    except Exception:
        raise HTTPException(502, "Unable to send contact inquiry")

    return {"message": "Contact inquiry sent successfully"}


class JobAcceptedNotification(BaseModel):
    type: str
    recipient_email: str = Field(min_length=3)
    candidate_name: str = Field(min_length=1)
    job_title: str = Field(min_length=1)
    company_name: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    accepted_at: str = Field(min_length=1)


@router.post("/api/v1/notifications/job-accepted")
async def job_accepted_notification(req: JobAcceptedNotification):
    if req.type != "job_accepted":
        raise HTTPException(400, "Invalid notification type")

    try:
        send_job_acceptance_email(
            recipient_email=req.recipient_email,
            candidate_name=req.candidate_name,
            job_title=req.job_title,
            company_name=req.company_name,
        )
    except Exception:
        logger.exception("Failed to send job acceptance email for job %s", req.job_id)
        raise HTTPException(502, "Unable to send job acceptance email")

    return {"message": "Job acceptance email sent successfully"}


class ContactReplyNotification(BaseModel):
    type: str
    recipient_email: str = Field(min_length=3)
    recipient_name: str = Field(min_length=1)
    subject: str = Field(min_length=1, max_length=255)
    message: str = Field(min_length=1, max_length=10000)


@router.post("/api/v1/notifications/contact-reply")
async def contact_reply_notification(req: ContactReplyNotification):
    if req.type != "contact_reply":
        raise HTTPException(400, "Invalid notification type")

    try:
        send_contact_reply_email(
            recipient_email=req.recipient_email,
            recipient_name=req.recipient_name,
            subject=req.subject,
            message=req.message,
        )
    except Exception:
        logger.exception("Failed to send contact reply email")
        raise HTTPException(502, "Unable to send contact reply")

    return {"message": "Contact reply sent successfully"}


@router.post("/analyze-cv")
async def analyze_cv(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    github_username: str = Form(""),
):
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
    EXTRACTED_DIR.mkdir(exist_ok=True)
    HISTORY_DIR.mkdir(exist_ok=True)
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

    cleanup_paths = [str(cv_out), str(history_out)]
    if github_info and github_info.get("saved_as"):
        cleanup_paths.append(str(github_info["saved_as"]))
    background_tasks.add_task(cleanup_temp_artifacts, *cleanup_paths)

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


JD_PROMPT_TEMPLATE = Path("prompts/generate_job_description.txt").read_text()


class GenerateJobDescriptionRequest(BaseModel):
    prompt: str
    company_name: str = ""


@router.post("/generate-job-description")
async def generate_job_description(req: GenerateJobDescriptionRequest):
    if not req.prompt.strip():
        raise HTTPException(400, "prompt is required")

    full_prompt = JD_PROMPT_TEMPLATE.format(prompt=req.prompt)
    result = await analyze(full_prompt)

    return {
        "response": result["response"],
        "engine": result["engine"],
    }
