import os
import html
import logging
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
import resend

ANALYZER_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ANALYZER_DIR / ".env")

email_api = os.environ.get("resend_api_key", "")
email_from = os.environ.get("resend_email_from", "")
acceptance_job_link = os.environ.get("ACCEPTANCE_JOB_LINK", "")
resend.api_key = email_api

logger = logging.getLogger(__name__)


def send_contact_email(
    first_name: str,
    last_name: str,
    email: str,
    company: str,
    budget_range: str,
    project_details: str,
) -> None:
    if not email_api or not email_from:
        logger.error("Contact email configuration is incomplete")
        raise RuntimeError("Contact email is not configured")

    submitted_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    fields = {
        "Name": f"{first_name} {last_name}".strip(),
        "Email": email,
        "Company": company or "Not provided",
        "Budget range": budget_range or "Not provided",
        "Project details": project_details,
        "Submitted": submitted_at,
    }
    rows = "".join(
        f"<tr><th style='padding:8px 16px;text-align:left;vertical-align:top'>{html.escape(label)}</th>"
        f"<td style='padding:8px 16px;white-space:pre-wrap'>{html.escape(value)}</td></tr>"
        for label, value in fields.items()
    )

    try:
        resend.Emails.send({
            "from": email_from,
            "to": [email],
            "reply_to": email,
            "subject": f"New Contact Us Inquiry - {fields['Name']}",
            "html": (
                "<div style='font-family:Arial,sans-serif;color:#172033'>"
                "<h2>New Contact Us Inquiry</h2>"
                f"<table style='border-collapse:collapse'>{rows}</table>"
                "</div>"
            ),
        })
    except Exception:
        logger.exception("Failed to send Contact Us email")
        raise


def send_job_acceptance_email(
    recipient_email: str,
    candidate_name: str,
    job_title: str,
    company_name: str,
) -> None:
    if not email_api or not email_from or not acceptance_job_link:
        logger.error("Acceptance email configuration is incomplete")
        raise RuntimeError("Acceptance email is not configured")

    subject = f"Congratulations! You have been accepted for {job_title}"
    safe_name = html.escape(candidate_name)
    safe_title = html.escape(job_title)
    safe_company = html.escape(company_name)
    safe_acceptance_job_link = html.escape(acceptance_job_link, quote=True)
    resend.Emails.send({
        "from": email_from,
        "to": [recipient_email],
        "subject": subject,
        "html": (
            "<div style='font-family:Arial,sans-serif;color:#172033'>"
            f"<p>Congratulations, {safe_name}!</p>"
            f"<p>We are pleased to let you know that you have been accepted for the "
            f"<strong>{safe_title}</strong> position at <strong>{safe_company}</strong>.</p>"
            "<p>Please use the button below to review your application and complete your next steps.</p>"
            f"<p><a href='{safe_acceptance_job_link}' "
            "style='display:inline-block;padding:12px 20px;background:#172033;color:#ffffff;"
            "text-decoration:none;border-radius:4px;font-weight:bold'>View Your Application</a></p>"
            "<p>Best regards,<br>Izone Technologies</p>"
            "</div>"
        ),
    })


def send_contact_reply_email(
    recipient_email: str,
    recipient_name: str,
    subject: str,
    message: str,
) -> None:
    if not email_api or not email_from:
        logger.error("Contact reply email configuration is incomplete")
        raise RuntimeError("Contact reply email is not configured")

    safe_name = html.escape(recipient_name)
    safe_message = html.escape(message).replace("\n", "<br>")
    resend.Emails.send({
        "from": email_from,
        "to": [recipient_email],
        "subject": subject,
        "html": (
            "<div style='font-family:Arial,sans-serif;color:#172033'>"
            f"<p>Hello {safe_name},</p>"
            f"<p style='white-space:normal'>{safe_message}</p>"
            "<p>Best regards,<br>Izone Technologies</p>"
            "</div>"
        ),
    })
