import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx
# 1. Import and load the .env configurations immediately
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# 2. Safely extract values from the loaded environment variables
ENVIRONMENT = os.environ.get("ENVIRONMENT", "development") 
OPENCODE_URL = os.environ.get("OPENCODE_URL", "http://localhost:4096")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

class GenerationRequest(BaseModel):
    prompt: str

@app.get("/")
def read_root():
    mode = "Production (Gemini)" if ENVIRONMENT == "production" else "Development (Local OpenCode)"
    return {"message": f"FastAPI is running safely. Current Mode: {mode}"}

async def generate_with_local_opencode(client: httpx.AsyncClient, prompt: str):
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
        
        return {"response": "✅ Response received", "engine": "local_opencode"}
        
    finally:
        try:
            await client.delete(f"{OPENCODE_URL}/session/{session_id}")
        except Exception:
            pass

async def generate_with_gemini(client: httpx.AsyncClient, prompt: str):
    if not GEMINI_API_KEY:
        raise HTTPException(500, "Gemini API Key is missing from environment configurations.")
        
    url = f"https://googleapis.com{GEMINI_API_KEY}"
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    
    response = await client.post(url, json=payload)
    if response.status_code != 200:
        raise HTTPException(502, f"Gemini API Error: {response.text}")
        
    try:
        data = response.json()
        text_output = data["candidates"]["content"]["parts"]["text"]
        return {"response": text_output, "engine": "gemini_cloud"}
    except (KeyError, IndexError):
        raise HTTPException(502, "Failed to parse text from Gemini response structure.")


@app.post("/generate")
async def generate_text(request: GenerationRequest):
    timeout = httpx.Timeout(300.0, connect=30.0)

    async with httpx.AsyncClient(timeout=timeout) as client:
        if ENVIRONMENT == "production":
            return await generate_with_gemini(client, request.prompt)
            
        try:
            return await generate_with_local_opencode(client, request.prompt)
            
        except (httpx.ConnectError, httpx.TimeoutException):
            print("⚠️ Local OpenCode unavailable. Falling back to Gemini cloud...")
            if GEMINI_API_KEY:
                return await generate_with_gemini(client, request.prompt)
            else:
                raise HTTPException(503, "Local OpenCode is down, and GEMINI_API_KEY is not configured in .env.")
        except Exception as exc:
            raise HTTPException(502, str(exc))
