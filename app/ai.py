import json
import httpx
from fastapi import HTTPException

from .config import ENVIRONMENT, OPENCODE_URL, GEMINI_API_KEY


async def analyze(prompt: str) -> dict:
    timeout = httpx.Timeout(300.0, connect=30.0)

    async with httpx.AsyncClient(timeout=timeout) as client:
        if ENVIRONMENT == "production":
            result = await _call_gemini(client, prompt)
        else:
            try:
                result = await _call_opencode(client, prompt)
            except (httpx.ConnectError, httpx.TimeoutException):
                print("Local OpenCode unavailable. Falling back to Gemini cloud...")
                if GEMINI_API_KEY:
                    result = await _call_gemini(client, prompt)
                else:
                    raise HTTPException(
                        503, "Local OpenCode is down, and GEMINI_API_KEY is not configured."
                    )
            except Exception as exc:
                raise HTTPException(502, str(exc))

    raw = result["response"]
    parsed = _try_parse_json(raw)

    return {
        "response": parsed if parsed else {"raw": raw},
        "engine": result["engine"],
    }


def _try_parse_json(raw: str):
    if not raw.strip():
        return None
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        cleaned = cleaned.rsplit("```", 1)[0]
    cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return None


async def _call_opencode(client: httpx.AsyncClient, prompt: str):
    sess_resp = await client.post(f"{OPENCODE_URL}/session")
    if sess_resp.status_code != 200:
        raise HTTPException(502, "Failed to create OpenCode session")
    session_id = sess_resp.json()["id"]

    try:
        msg_resp = await client.post(
            f"{OPENCODE_URL}/session/{session_id}/message",
            json={"parts": [{"type": "text", "text": prompt}]},
        )
        if msg_resp.status_code != 200:
            raise HTTPException(502, f"OpenCode error: {msg_resp.status_code}")

        data = msg_resp.json()
        parts = data.get("parts", [])
        for part in parts:
            if part.get("type") == "text":
                return {"response": part.get("text", ""), "engine": "local_opencode"}

        return {"response": "Response received", "engine": "local_opencode"}

    finally:
        try:
            await client.delete(f"{OPENCODE_URL}/session/{session_id}")
        except Exception:
            pass


async def _call_gemini(client: httpx.AsyncClient, prompt: str):
    if not GEMINI_API_KEY:
        raise HTTPException(
            500, "Gemini API Key is missing from environment configurations."
        )

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"

    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    response = await client.post(url, json=payload)
    if response.status_code != 200:
        raise HTTPException(502, f"Gemini API Error: {response.text}")

    try:
        data = response.json()
        text_output = data["candidates"]["content"]["parts"]["text"]
        return {"response": text_output, "engine": "gemini_cloud"}
    except (KeyError, IndexError):
        raise HTTPException(502, "Failed to parse text from Gemini response structure.")
