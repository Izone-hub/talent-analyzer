"""
Quick test script to verify the Analyzer AI endpoint works.

Usage:
  1. Start the Analyzer:
     cd /home/meka/temp/talent-analyzer
     INTERNAL_SERVICE_TOKEN=my-secret uvicorn main:app --port 8000

  2. Run this script:
     python test_endpoint.py
"""

import requests
import json
import time

BASE_URL = "http://localhost:8000"
TOKEN = "my-secret"  # Must match INTERNAL_SERVICE_TOKEN in .env


def test_health():
    """Test 1: Health check (no token needed)"""
    print("=" * 50)
    print("TEST 1: Health check (no auth)")
    resp = requests.get(f"{BASE_URL}/health")
    print(f"  Status: {resp.status_code}")
    print(f"  Body:   {resp.json()}")
    assert resp.status_code == 200, "Health check failed!"
    print("  ✅ PASS\n")


def test_without_token():
    """Test 2: Protected endpoint without token → should fail"""
    print("TEST 2: /generate-questions without token (should 401)")
    resp = requests.post(f"{BASE_URL}/generate-questions", json={"prompt": "test"})
    print(f"  Status: {resp.status_code}")
    print(f"  Body:   {resp.json()}")
    assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
    print("  ✅ PASS — blocked without token\n")


def test_with_wrong_token():
    """Test 3: Protected endpoint with wrong token → should fail"""
    print("TEST 3: /generate-questions with wrong token (should 401)")
    resp = requests.post(
        f"{BASE_URL}/generate-questions",
        json={"prompt": "test"},
        headers={"X-Internal-Service-Token": "wrong-token-xyz"},
    )
    print(f"  Status: {resp.status_code}")
    print(f"  Body:   {resp.json()}")
    assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
    print("  ✅ PASS — blocked with wrong token\n")


def test_generate_questions():
    """Test 4: Generate questions with valid token"""
    print("TEST 4: /generate-questions with valid token")
    print("  (This calls DeepSeek — may take 30-60 seconds)")
    start = time.time()
    resp = requests.post(
        f"{BASE_URL}/generate-questions",
        json={
            "prompt": "Generate 2 simple JavaScript questions about arrays",
            "question_type": "multiple_choice",
            "difficulty": "easy",
        },
        headers={"X-Internal-Service-Token": TOKEN},
        timeout=120,
    )
    elapsed = time.time() - start
    print(f"  Status: {resp.status_code} ({elapsed:.1f}s)")
    if resp.status_code == 200:
        data = resp.json()
        print(f"  Engine: {data.get('engine', 'unknown')}")
        print(f"  Questions: {json.dumps(data.get('questions', {}), indent=2)[:500]}")
        print("  ✅ PASS\n")
    else:
        print(f"  Body: {resp.text}")
        print("  ❌ FAIL\n")
        return False
    return True


def test_generate_job_description():
    """Test 5: Generate job description with valid token"""
    print("TEST 5: /generate-job-description with valid token")
    print("  (This calls DeepSeek — may take 30-60 seconds)")
    start = time.time()
    resp = requests.post(
        f"{BASE_URL}/generate-job-description",
        json={
            "prompt": "Senior React developer with 5 years experience, remote, full-time",
            "company_name": "TechCorp",
        },
        headers={"X-Internal-Service-Token": TOKEN},
        timeout=120,
    )
    elapsed = time.time() - start
    print(f"  Status: {resp.status_code} ({elapsed:.1f}s)")
    if resp.status_code == 200:
        data = resp.json()
        print(f"  Engine: {data.get('engine', 'unknown')}")
        desc = data.get("response", {})
        if isinstance(desc, dict):
            print(f"  Title: {desc.get('title', 'N/A')}")
            print(f"  Description: {str(desc.get('description', 'N/A'))[:200]}...")
        else:
            print(f"  Response: {str(desc)[:300]}...")
        print("  ✅ PASS\n")
    else:
        print(f"  Body: {resp.text}")
        print("  ❌ FAIL\n")
        return False
    return True


if __name__ == "__main__":
    print("🧪 Talent Analyzer — Endpoint Tests")
    print(f"   Target: {BASE_URL}")
    print(f"   Token:  {'*' * 8}...{TOKEN[-4:]}")
    print()

    # Auth tests (instant)
    test_health()
    test_without_token()
    test_with_wrong_token()

    # AI tests (slow — calls DeepSeek)
    q_ok = test_generate_questions()
    jd_ok = test_generate_job_description()

    # Summary
    print("=" * 50)
    print("SUMMARY")
    print("=" * 50)
    print("  Health check:          ✅")
    print("  Missing token block:   ✅")
    print("  Wrong token block:     ✅")
    print(f"  Generate questions:    {'✅' if q_ok else '❌'}")
    print(f"  Generate job desc:     {'✅' if jd_ok else '❌'}")
