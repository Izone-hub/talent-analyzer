import json
from openai import OpenAI
from fastapi import HTTPException

from .config import NVIDIA_API_KEY

# NVIDIA API — Nemotron model (fast + capable)
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
NVIDIA_MODEL = "nvidia/nemotron-3.5-lightning-30b-a3b"


def _get_client() -> OpenAI:
    """Create an OpenAI client pointing to the NVIDIA API."""
    if not NVIDIA_API_KEY:
        raise HTTPException(
            500, "NVIDIA_API_KEY is not configured. Set it in your .env file."
        )
    return OpenAI(
        base_url=NVIDIA_BASE_URL,
        api_key=NVIDIA_API_KEY,
    )


async def analyze(prompt: str) -> dict:
    """
    Send a prompt to Nemotron via NVIDIA API and return the parsed response.
    Uses streaming for faster time-to-first-token.
    """
    import asyncio

    result = await asyncio.to_thread(_call_nemotron, prompt)

    raw = result["response"]
    parsed = _try_parse_json(raw)

    return {
        "response": parsed if parsed else {"raw": raw},
        "engine": result["engine"],
    }


def _call_nemotron(prompt: str) -> dict:
    """Call the Nemotron model via NVIDIA API with streaming."""
    client = _get_client()

    try:
        completion = client.chat.completions.create(
            model=NVIDIA_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=1,
            top_p=0.95,
            max_tokens=16384,
            extra_body={
                "chat_template_kwargs": {"enable_thinking": True},
                "reasoning_budget": 16384,
            },
            stream=True,
        )

        # Collect streamed response
        content = ""
        for chunk in completion:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content is not None:
                content += delta.content

        return {"response": content, "engine": "nemotron-3.5-lightning"}
    except Exception as e:
        raise HTTPException(502, f"NVIDIA API error: {e}")


def _try_parse_json(raw: str):
    """Try to parse a JSON response from the AI. Returns None if not valid JSON."""
    if not raw or not raw.strip():
        return None
    cleaned = raw.strip()
    # Strip markdown code fences if present
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        cleaned = cleaned.rsplit("```", 1)[0]
    cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return None
