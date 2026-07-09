import io
from pathlib import Path
from fastapi import UploadFile, HTTPException

from .condense import condense_cv_text


async def extract_text_from_file(file: UploadFile) -> str:
    ext = Path(file.filename).suffix.lower()
    content = await file.read()

    if ext == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(content))
        raw = "\n".join(page.extract_text() or "" for page in reader.pages)
    elif ext == ".docx":
        from docx import Document
        doc = Document(io.BytesIO(content))
        raw = "\n".join(p.text for p in doc.paragraphs)
    elif ext == ".txt":
        raw = content.decode("utf-8")
    else:
        raise HTTPException(400, f"Unsupported file type: {ext}. Use PDF, DOCX, or TXT.")

    return condense_cv_text(raw)
