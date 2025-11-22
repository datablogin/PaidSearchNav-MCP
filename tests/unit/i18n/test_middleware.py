"""Tests for i18n middleware."""

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from paidsearchnav_mcp.api.middleware_i18n import (
    I18nMiddleware,
    get_language,
    get_request_translator,
)
from paidsearchnav_mcp.i18n import get_translator


@pytest.fixture
def app():
    """Create a test FastAPI app with i18n middleware."""
    app = FastAPI()
    app.add_middleware(I18nMiddleware)

    @app.get("/test")
    async def test_endpoint(request: Request):
        language = get_language(request)
        translator = get_request_translator(request)
        return {
            "language": language,
            "translator_language": translator.current_language,
        }

    @app.get("/translate")
    async def translate_endpoint(request: Request):
        translator = get_request_translator(request)
        return {"message": translator.gettext("Hello, world!")}

    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


class TestI18nMiddleware:
    """Test i18n middleware functionality."""

    def test_default_language(self, client):
        """Test default language when no header provided."""
        response = client.get("/test")
        assert response.status_code == 200
        data = response.json()
        assert data["language"] == "en-US"
        assert data["translator_language"] == "en-US"
        assert response.headers["Content-Language"] == "en-US"

    def test_accept_language_header(self, client):
        """Test language detection from Accept-Language header."""
        response = client.get("/test", headers={"Accept-Language": "es-ES"})
        assert response.status_code == 200
        data = response.json()
        assert data["language"] == "es-ES"
        assert data["translator_language"] == "es-ES"
        assert response.headers["Content-Language"] == "es-ES"

    def test_complex_accept_language(self, client):
        """Test complex Accept-Language header parsing."""
        headers = {"Accept-Language": "fr-FR, fr;q=0.9, en;q=0.8"}
        response = client.get("/test", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["language"] == "fr-FR"
        assert response.headers["Content-Language"] == "fr-FR"

    def test_query_param_override(self, client):
        """Test language override via query parameter."""
        headers = {"Accept-Language": "es-ES"}
        response = client.get("/test?lang=de-DE", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["language"] == "de-DE"
        assert response.headers["Content-Language"] == "de-DE"

    def test_unsupported_language_fallback(self, client):
        """Test fallback for unsupported language."""
        headers = {"Accept-Language": "zh-CN"}
        response = client.get("/test", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["language"] == "en-US"  # Falls back to default

    def test_partial_language_match(self, client):
        """Test partial language code matching."""
        # Request Spanish without specific region
        headers = {"Accept-Language": "es"}
        response = client.get("/test", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["language"] == "es-ES"  # Matches es-ES

    def test_translation_in_endpoint(self, client):
        """Test that translation works in endpoints."""
        response = client.get("/translate", headers={"Accept-Language": "es-ES"})
        assert response.status_code == 200
        data = response.json()
        # Without actual translation files, it returns the original
        assert data["message"] == "Hello, world!"


def test_get_language_function():
    """Test get_language helper function."""
    # Mock request with language
    request = type("Request", (), {})()
    request.state = type("State", (), {})()
    request.state.language = "fr-FR"

    assert get_language(request) == "fr-FR"

    # Request without language
    request_no_lang = type("Request", (), {})()
    request_no_lang.state = type("State", (), {})()

    assert get_language(request_no_lang) == "en-US"  # Default


def test_get_request_translator_function():
    """Test get_request_translator helper function."""
    # Mock request with translator
    request = type("Request", (), {})()
    request.state = type("State", (), {})()
    translator = get_translator()
    request.state.translator = translator

    assert get_request_translator(request) == translator

    # Request without translator
    request_no_trans = type("Request", (), {})()
    request_no_trans.state = type("State", (), {})()

    # Should return global translator
    assert isinstance(get_request_translator(request_no_trans), type(translator))
