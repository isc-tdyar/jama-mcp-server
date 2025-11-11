"""Integration tests for JAMA item creation with real JAMA API.

These tests require:
- JAMA instance access (https://jama.iscinternal.com)
- Valid credentials (JAMA_CLIENT_ID, JAMA_CLIENT_SECRET)
- Test project ID 52 with parent item 28953
- Set JAMA_MOCK_MODE=false to run against real API

Run with: pytest tests/integration/test_item_creation.py -v
"""
import pytest
import os
import json
from unittest.mock import MagicMock

from jama_mcp_server.tools.write_tools import jama_create_item, jama_batch_create_items
from jama_mcp_server.client import JamaClientWrapper


# Skip integration tests if JAMA_MOCK_MODE is true (default in fixtures)
pytestmark = pytest.mark.skipif(
    os.getenv("JAMA_MOCK_MODE", "true").lower() == "true",
    reason="Integration tests require JAMA_MOCK_MODE=false and real JAMA credentials"
)


@pytest.fixture
def real_jama_client():
    """Create real JAMA client for integration testing."""
    # Get real JAMA credentials from environment
    jama_url = os.getenv("JAMA_URL")
    jama_client_id = os.getenv("JAMA_CLIENT_ID")
    jama_client_secret = os.getenv("JAMA_CLIENT_SECRET")

    # Verify required environment variables
    required_env = {"JAMA_URL": jama_url, "JAMA_CLIENT_ID": jama_client_id, "JAMA_CLIENT_SECRET": jama_client_secret}
    missing = [var for var, value in required_env.items() if not value]
    if missing:
        pytest.skip(f"Missing required environment variables: {missing}")

    client = JamaClientWrapper(
        host_domain=jama_url,
        credentials=(jama_client_id, jama_client_secret),
        oauth=True,
        verify_ssl=os.getenv("JAMA_VERIFY_SSL", "true").lower() == "true"
    )
    return client


@pytest.fixture
def integration_context(real_jama_client):
    """Create MCP context with real JAMA client."""
    context = MagicMock()
    context.request_context.lifespan_context = {"jama_client": real_jama_client}
    return context


@pytest.mark.asyncio
async def test_single_item_creation_real_jama(integration_context):
    """Test creating a single JAMA item with real API (T034).

    This test:
    1. Creates a NEED item in project 52 under parent 28953
    2. Verifies the item is created with correct fields
    3. Cleans up by deleting the test item
    """
    created_item_id = None

    try:
        # Create test item
        result = await jama_create_item(
            ctx=integration_context,
            project=52,
            item_type=134,  # NEED type
            name="Integration Test NEED - DELETE ME",
            parent=28953,
            description="<p>Integration test item created by automated tests</p>",
            custom_fields='{"fields": {"workflow_status$134": 615}}'
        )

        # Verify creation
        assert result is not None
        assert "id" in result
        assert "documentKey" in result
        created_item_id = result["id"]

        print(f"\n✓ Created item {result['documentKey']} (ID: {created_item_id})")

        # Verify item exists in JAMA
        jama_client = integration_context.request_context.lifespan_context["jama_client"]
        fetched_item = jama_client.get_item(created_item_id)
        assert fetched_item["id"] == created_item_id
        assert fetched_item["fields"]["name"] == "Integration Test NEED - DELETE ME"

    finally:
        # Cleanup: delete test item
        if created_item_id:
            try:
                jama_client = integration_context.request_context.lifespan_context["jama_client"]
                jama_client.delete_item(created_item_id)
                print(f"✓ Cleaned up test item {created_item_id}")
            except Exception as e:
                print(f"⚠ Failed to cleanup item {created_item_id}: {e}")


@pytest.mark.asyncio
async def test_batch_creation_success(integration_context):
    """Test batch creation of 4 items successfully (T035).

    This test:
    1. Creates 4 NEED items in batch
    2. Verifies all 4 are created successfully
    3. Cleans up all test items
    """
    created_item_ids = []

    try:
        # Create batch items
        items = [
            {
                "project": 52,
                "itemType": 134,
                "location": {"parent": 28953},
                "fields": {
                    "name": f"Integration Test Batch Item {i} - DELETE ME",
                    "description": f"<p>Batch test item {i}</p>",
                    "workflow_status$134": 615
                }
            }
            for i in range(1, 5)
        ]

        result = await jama_batch_create_items(ctx=integration_context, items=items)

        # Verify all succeeded
        assert result["total"] == 4
        assert result["succeeded"] == 4
        assert result["failed"] == 0
        assert len(result["created_items"]) == 4
        assert len(result["errors"]) == 0

        created_item_ids = [item["id"] for item in result["created_items"]]
        print(f"\n✓ Created {len(created_item_ids)} items in batch")

        # Verify all items exist in JAMA
        jama_client = integration_context.request_context.lifespan_context["jama_client"]
        for item_id in created_item_ids:
            fetched_item = jama_client.get_item(item_id)
            assert fetched_item["id"] == item_id
            assert "Integration Test Batch Item" in fetched_item["fields"]["name"]

    finally:
        # Cleanup: delete all test items
        if created_item_ids:
            jama_client = integration_context.request_context.lifespan_context["jama_client"]
            for item_id in created_item_ids:
                try:
                    jama_client.delete_item(item_id)
                    print(f"✓ Cleaned up test item {item_id}")
                except Exception as e:
                    print(f"⚠ Failed to cleanup item {item_id}: {e}")


@pytest.mark.asyncio
async def test_batch_abort_scenario(integration_context):
    """Test batch creation aborts on failure (T036).

    This test:
    1. Creates batch with 3 items, 2nd item has invalid parent
    2. Verifies only 1st item created, processing stopped
    3. Cleans up successfully created item
    """
    created_item_ids = []

    try:
        # Create batch with invalid 2nd item
        items = [
            {
                "project": 52,
                "itemType": 134,
                "location": {"parent": 28953},
                "fields": {
                    "name": "Batch Abort Test Item 1 - DELETE ME",
                    "description": "<p>First item (should succeed)</p>",
                    "workflow_status$134": 615
                }
            },
            {
                "project": 52,
                "itemType": 134,
                "location": {"parent": 99999},  # Invalid parent
                "fields": {
                    "name": "Batch Abort Test Item 2 - SHOULD FAIL",
                    "description": "<p>Second item (should fail)</p>",
                    "workflow_status$134": 615
                }
            },
            {
                "project": 52,
                "itemType": 134,
                "location": {"parent": 28953},
                "fields": {
                    "name": "Batch Abort Test Item 3 - SHOULD NOT BE CREATED",
                    "description": "<p>Third item (should not be created)</p>",
                    "workflow_status$134": 615
                }
            }
        ]

        result = await jama_batch_create_items(ctx=integration_context, items=items)

        # Verify abort behavior
        assert result["total"] == 3
        assert result["succeeded"] == 1  # Only first item
        assert result["failed"] == 1
        assert len(result["created_items"]) == 1
        assert len(result["errors"]) == 1
        assert result["errors"][0]["index"] == 1
        assert "Parent item 99999 not found" in result["errors"][0]["error"]

        created_item_ids = [item["id"] for item in result["created_items"]]
        print(f"\n✓ Batch correctly aborted after 1st item, created {len(created_item_ids)} items")

    finally:
        # Cleanup: delete successfully created item
        if created_item_ids:
            jama_client = integration_context.request_context.lifespan_context["jama_client"]
            for item_id in created_item_ids:
                try:
                    jama_client.delete_item(item_id)
                    print(f"✓ Cleaned up test item {item_id}")
                except Exception as e:
                    print(f"⚠ Failed to cleanup item {item_id}: {e}")


@pytest.mark.asyncio
async def test_duplicate_name_rejection_integration(integration_context):
    """Test duplicate name rejection with real JAMA (T037).

    This test:
    1. Creates an item with a specific name
    2. Attempts to create another item with same name under same parent
    3. Verifies duplicate is rejected
    4. Cleans up test item
    """
    created_item_id = None

    try:
        # Create first item
        result1 = await jama_create_item(
            ctx=integration_context,
            project=52,
            item_type=134,
            name="Duplicate Test Name - DELETE ME",
            parent=28953,
            description="<p>First item</p>",
            custom_fields='{"fields": {"workflow_status$134": 615}}'
        )

        created_item_id = result1["id"]
        print(f"\n✓ Created first item {result1['documentKey']}")

        # Attempt to create duplicate (should fail)
        with pytest.raises(ValueError, match="already exists under parent"):
            await jama_create_item(
                ctx=integration_context,
                project=52,
                item_type=134,
                name="Duplicate Test Name - DELETE ME",  # Same name
                parent=28953,  # Same parent
                description="<p>Duplicate attempt</p>",
                custom_fields='{"fields": {"workflow_status$134": 615}}'
            )

        print("✓ Duplicate name correctly rejected")

    finally:
        # Cleanup
        if created_item_id:
            try:
                jama_client = integration_context.request_context.lifespan_context["jama_client"]
                jama_client.delete_item(created_item_id)
                print(f"✓ Cleaned up test item {created_item_id}")
            except Exception as e:
                print(f"⚠ Failed to cleanup item {created_item_id}: {e}")


@pytest.mark.asyncio
async def test_parent_not_found_integration(integration_context):
    """Test parent not found error with real JAMA (T038).

    This test verifies that attempting to create an item with
    a non-existent parent fails with appropriate error message.
    """
    # Attempt to create item with invalid parent
    with pytest.raises(ValueError, match="Parent item 99999 not found"):
        await jama_create_item(
            ctx=integration_context,
            project=52,
            item_type=134,
            name="Parent Not Found Test",
            parent=99999,  # Non-existent parent
            description="<p>This should fail</p>",
            custom_fields='{"fields": {"workflow_status$134": 615}}'
        )

    print("\n✓ Parent not found error correctly raised")


@pytest.mark.asyncio
async def test_retry_on_network_failure_integration(integration_context):
    """Test that network failures trigger retry (T032 integration).

    Note: This test is difficult to trigger reliably with real API.
    Retry logic is better tested in unit tests with mocked timeouts.
    This test just verifies the retry decorator doesn't break normal operation.
    """
    created_item_id = None

    try:
        # Normal creation should work with retry decorator in place
        result = await jama_create_item(
            ctx=integration_context,
            project=52,
            item_type=134,
            name="Retry Test - DELETE ME",
            parent=28953,
            description="<p>Retry test</p>",
            custom_fields='{"fields": {"workflow_status$134": 615}}'
        )

        created_item_id = result["id"]
        print(f"\n✓ Item created successfully with retry decorator: {result['documentKey']}")

    finally:
        if created_item_id:
            try:
                jama_client = integration_context.request_context.lifespan_context["jama_client"]
                jama_client.delete_item(created_item_id)
                print(f"✓ Cleaned up test item {created_item_id}")
            except Exception as e:
                print(f"⚠ Failed to cleanup item {created_item_id}: {e}")
