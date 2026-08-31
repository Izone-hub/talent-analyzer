import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# NVIDIA API — DeepSeek model via OpenAI-compatible endpoint.
NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "")

# Internal service token — shared secret between Backend and Analyzer.
# The Backend sends this in X-Internal-Service-Token header.
# Must be set in both Backend .env and Analyzer .env.
INTERNAL_SERVICE_TOKEN = os.environ.get("INTERNAL_SERVICE_TOKEN", "")

STATIC_DIR = Path("static")
STATIC_DIR.mkdir(exist_ok=True)

MAX_CV_CHARS = 2500
