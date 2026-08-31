"""
Tests for Internal Service Authentication Middleware.

Covers:
  - Valid token → request passes through
  - Missing token → 401 Unauthorized
  - Invalid token → 401 Unauthorized
  - Exempt paths (/, /docs, /openapi.json) → no auth required
  - Protected endpoints require token
  - Token not leaked in error responses
"""

import os
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

# Set test token before importing app modules
os.environ["INTERNAL_SERVICE_TOKEN"] = "test-secret-token-abc123"

from app.auth import InternalServiceAuthMiddleware, get_internal_token, _constant_time_compare

TEST_TOKEN = "test-secret-token-abc123"


# ---------------------------------------------------------------------------
# Helper: create a minimal FastAPI app with the middleware applied
# ---------------------------------------------------------------------------

def create_test_app():
    """Create a minimal FastAPI app with the auth middleware for testing."""
    app = FastAPI()

    # Apply the middleware
    token = get_internal_token()
    app.add_middleware(InternalServiceAuthMiddleware, token=token)

    @app.get("/")
    async def root():
        return {"status": "ok"}

    @app.get("/protected")
    async def protected():
        return {"data": "secret"}

    @app.post("/analyze-cv")
    async def analyze_cv():
        return {"analysis": "result"}

    @app.post("/generate-job-description")
    async def generate_jd():
        return {"description": "generated"}

    @app.post("/generate-questions")
    async def generate_questions():
        return {"questions": []}

    @app.get("/docs")
    async def docs():
        return {"docs": "page"}

    @app.get("/openapi.json")
    async def openapi():
        return {"openapi": "spec"}

    return app


@pytest.fixture
def client():
    """Create a test client with the auth middleware."""
    app = create_test_app()
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Tests: Valid Token
# ---------------------------------------------------------------------------

class TestValidToken:
    def test_valid_token_on_protected_endpoint(self, client):
        """Request with valid token should pass through."""
        response = client.get(
            "/protected",
            headers={"X-Internal-Service-Token": TEST_TOKEN},
        )
        assert response.status_code == 200
        assert response.json() == {"data": "secret"}

    def test_valid_token_on_analyze_cv(self, client):
        """POST /analyze-cv with valid token should be accepted."""
        response = client.post(
            "/analyze-cv",
            headers={"X-Internal-Service-Token": TEST_TOKEN},
        )
        assert response.status_code == 200

    def test_valid_token_on_generate_job_description(self, client):
        """POST /generate-job-description with valid token should be accepted."""
        response = client.post(
            "/generate-job-description",
            headers={"X-Internal-Service-Token": TEST_TOKEN},
        )
        assert response.status_code == 200

    def test_valid_token_on_generate_questions(self, client):
        """POST /generate-questions with valid token should be accepted."""
        response = client.post(
            "/generate-questions",
            headers={"X-Internal-Service-Token": TEST_TOKEN},
        )
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Tests: Missing Token
# ---------------------------------------------------------------------------

class TestMissingToken:
    def test_missing_token_returns_401(self, client):
        """Request without token header should return 401."""
        response = client.get("/protected")
        assert response.status_code == 401

    def test_missing_token_on_analyze_cv(self, client):
        """POST /analyze-cv without token should return 401."""
        response = client.post("/analyze-cv")
        assert response.status_code == 401

    def test_missing_token_on_generate_job_description(self, client):
        """POST /generate-job-description without token should return 401."""
        response = client.post("/generate-job-description")
        assert response.status_code == 401

    def test_missing_token_on_generate_questions(self, client):
        """POST /generate-questions without token should return 401."""
        response = client.post("/generate-questions")
        assert response.status_code == 401

    def test_empty_token_returns_401(self, client):
        """Request with empty token header should return 401."""
        response = client.get(
            "/protected",
            headers={"X-Internal-Service-Token": ""},
        )
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Tests: Invalid Token
# ---------------------------------------------------------------------------

class TestInvalidToken:
    def test_wrong_token_returns_401(self, client):
        """Request with wrong token should return 401."""
        response = client.get(
            "/protected",
            headers={"X-Internal-Service-Token": "wrong-token-xyz"},
        )
        assert response.status_code == 401

    def test_similar_token_returns_401(self, client):
        """Request with a similar-but-wrong token should return 401."""
        response = client.get(
            "/protected",
            headers={"X-Internal-Service-Token": TEST_TOKEN + "x"},
        )
        assert response.status_code == 401

    def test_partial_token_returns_401(self, client):
        """Request with partial token should return 401."""
        response = client.get(
            "/protected",
            headers={"X-Internal-Service-Token": "test-secret"},
        )
        assert response.status_code == 401

    def test_empty_string_token_returns_401(self, client):
        """Request with completely wrong token should return 401."""
        response = client.get(
            "/protected",
            headers={"X-Internal-Service-Token": "completely-different-value"},
        )
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Tests: Exempt Paths
# ---------------------------------------------------------------------------

class TestExemptPaths:
    def test_root_without_token(self, client):
        """GET / should work without token (health/status check)."""
        response = client.get("/")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_docs_without_token(self, client):
        """GET /docs should work without token."""
        response = client.get("/docs")
        assert response.status_code == 200

    def test_openapi_without_token(self, client):
        """GET /openapi.json should work without token."""
        response = client.get("/openapi.json")
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Tests: Security — No Token Leakage
# ---------------------------------------------------------------------------

class TestSecurityNoLeakage:
    def test_error_response_does_not_leak_token(self, client):
        """401 error should not contain the token value."""
        response = client.get(
            "/protected",
            headers={"X-Internal-Service-Token": "wrong-token"},
        )
        assert response.status_code == 401
        body = response.json()
        # The error detail should be generic
        assert "detail" in body
        assert body["detail"] == "Unauthorized"
        # Token should NOT appear in the response
        assert TEST_TOKEN not in str(body)
        assert "wrong-token" not in str(body)

    def test_error_response_is_generic(self, client):
        """401 error should be generic — not reveal why it failed."""
        # Missing token
        resp1 = client.get("/protected")
        # Invalid token
        resp2 = client.get(
            "/protected",
            headers={"X-Internal-Service-Token": "bad"},
        )
        # Both should return the same generic error
        assert resp1.json() == resp2.json()


# ---------------------------------------------------------------------------
# Tests: Constant-Time Compare
# ---------------------------------------------------------------------------

class TestConstantTimeCompare:
    def test_identical_strings_match(self):
        assert _constant_time_compare("abc", "abc") is True

    def test_different_strings_dont_match(self):
        assert _constant_time_compare("abc", "abd") is False

    def test_different_lengths_dont_match(self):
        assert _constant_time_compare("abc", "abcd") is False

    def test_empty_strings_match(self):
        assert _constant_time_compare("", "") is True

    def test_empty_vs_nonempty(self):
        assert _constant_time_compare("", "a") is False


# ---------------------------------------------------------------------------
# Tests: Token Loading
# ---------------------------------------------------------------------------

class TestTokenLoading:
    def test_get_internal_token_returns_env_value(self):
        """get_internal_token should return the env var value."""
        token = get_internal_token()
        assert token == TEST_TOKEN

    def test_get_internal_token_raises_when_missing(self):
        """get_internal_token should raise ValueError when not set."""
        # Temporarily unset the env var
        old = os.environ.pop("INTERNAL_SERVICE_TOKEN", None)
        try:
            with pytest.raises(ValueError, match="INTERNAL_SERVICE_TOKEN"):
                get_internal_token()
        finally:
            if old:
                os.environ["INTERNAL_SERVICE_TOKEN"] = old


# ---------------------------------------------------------------------------
# Tests: Full Flow — Simulate Backend Request
# ---------------------------------------------------------------------------

class TestFullFlow:
    def test_backend_call_flow(self, client):
        """
        Simulate the exact flow the Backend uses:
        1. Backend creates request with X-Internal-Service-Token header
        2. Analyzer validates token and processes the request
        """
        response = client.post(
            "/analyze-cv",
            headers={
                "X-Internal-Service-Token": TEST_TOKEN,
                "Content-Type": "application/json",
            },
        )
        assert response.status_code == 200
        assert response.json() == {"analysis": "result"}

    def test_direct_public_access_blocked(self, client):
        """
        Simulate a direct public access attempt (no token).
        This should be blocked — the Analyzer is not publicly accessible.
        """
        response = client.post("/analyze-cv")
        assert response.status_code == 401
