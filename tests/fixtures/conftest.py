"""Pytest fixtures for JAMA MCP Server tests.

Common fixtures for mocking JAMA client and responses.
"""

import pytest
from unittest.mock import Mock, MagicMock
from typing import Dict, Any

from jama_mcp_server.client import JamaClientWrapper
from jama_mcp_server.utils.rate_limit import RateLimiter
from . import jama_responses


@pytest.fixture
def mock_rate_limiter():
    """Mock rate limiter that doesn't actually limit."""
    limiter = Mock(spec=RateLimiter)
    limiter.acquire = Mock(return_value=None)
    limiter.try_acquire = Mock(return_value=True)
    return limiter


@pytest.fixture
def mock_jama_client():
    """Mock JAMA client with common methods."""
    client = MagicMock(spec=JamaClientWrapper)

    # Configure default return values for common methods
    client.get_projects.return_value = jama_responses.MOCK_PROJECTS_LIST
    client.get_project.return_value = jama_responses.MOCK_PROJECT_1
    client.get_items.return_value = jama_responses.MOCK_ITEMS_LIST
    client.get_item.return_value = jama_responses.MOCK_ITEM_1
    client.get_relationships.return_value = jama_responses.MOCK_RELATIONSHIPS_LIST
    client.get_attachments.return_value = jama_responses.MOCK_ATTACHMENTS_LIST
    client.get_item_types.return_value = jama_responses.MOCK_ITEM_TYPES_LIST
    client.get_baselines.return_value = jama_responses.MOCK_BASELINES_LIST

    return client


@pytest.fixture
def mock_project():
    """Mock project data."""
    return jama_responses.MOCK_PROJECT_1.copy()


@pytest.fixture
def mock_item():
    """Mock item data."""
    return jama_responses.MOCK_ITEM_1.copy()


@pytest.fixture
def mock_relationship():
    """Mock relationship data."""
    return jama_responses.MOCK_RELATIONSHIP_1.copy()


@pytest.fixture
def mock_attachment():
    """Mock attachment data."""
    return jama_responses.MOCK_ATTACHMENT_1.copy()


@pytest.fixture
def sample_item_create_data():
    """Sample data for creating an item."""
    return {
        "project": 123,
        "itemType": 45,
        "location": {"parent": None},
        "fields": {
            "name": "Test Requirement",
            "description": "A test requirement for unit tests"
        }
    }


@pytest.fixture
def sample_relationship_create_data():
    """Sample data for creating a relationship."""
    return {
        "fromItem": 100,
        "toItem": 200,
        "relationshipType": 5
    }


@pytest.fixture
def sample_attachment_metadata():
    """Sample attachment metadata."""
    return {
        "fileName": "test-document.pdf",
        "mimeType": "application/pdf"
    }


@pytest.fixture(autouse=True)
def reset_environment_for_tests(monkeypatch):
    """Reset environment variables for each test.

    This fixture automatically runs before each test to ensure
    a clean environment state.
    """
    # Set JAMA_MOCK_MODE for all tests by default
    monkeypatch.setenv("JAMA_MOCK_MODE", "true")
    monkeypatch.setenv("JAMA_URL", "https://jama.test.example.com")
    monkeypatch.setenv("JAMA_CLIENT_ID", "test_client_id")
    monkeypatch.setenv("JAMA_CLIENT_SECRET", "test_client_secret")


@pytest.fixture
def mcp_context(mock_jama_client):
    """Mock MCP context with JAMA client."""
    context = MagicMock()
    context.request_context.lifespan_context = {"jama_client": mock_jama_client}
    return context
