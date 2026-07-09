import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ENVIRONMENT = os.environ.get("ENVIRONMENT", "development")
OPENCODE_URL = os.environ.get("OPENCODE_URL", "http://localhost:4096")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

STATIC_DIR = Path("static")
STATIC_DIR.mkdir(exist_ok=True)

MAX_CV_CHARS = 2500
