"""
Configuration pytest - Fixtures globales
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Fixture TestClient FastAPI"""
    from main import app
    return TestClient(app)
