import pytest
from fastapi.testclient import TestClient
import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from webui.app import app

client = TestClient(app)

def test_dashboard_endpoint():
    """Test that the main dashboard HTML serves correctly."""
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "<html" in response.text.lower()

def test_settings_endpoint():
    """Test that the settings HTML serves correctly."""
    response = client.get("/settings")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Settings Hub" in response.text or "<html" in response.text.lower()

def test_api_diagnostics():
    """Test the diagnostics API returns JSON payload."""
    response = client.get("/api/diagnostics")
    assert response.status_code == 200
    data = response.json()
    assert "model" in data
    assert "provider" in data

def test_api_history():
    """Test the history API returns memory arrays."""
    response = client.get("/api/history")
    assert response.status_code == 200
    data = response.json()
    assert "history" in data
    assert isinstance(data["history"], list)

def test_api_settings_read():
    """Test settings read API."""
    response = client.get("/api/settings/read")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
