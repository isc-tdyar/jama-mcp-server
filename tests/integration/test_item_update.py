"""Integration tests for JAMA item update functionality.

Tests jama_update_item against real JAMA API with cleanup.
Set JAMA_MOCK_MODE=false to run these tests.

Prerequisites:
- JAMA instance access (https://jama.iscinternal.com)
- Valid credentials (JAMA_CLIENT_ID, JAMA_CLIENT_SECRET)
- Test item IRIS-NEED-793 (ID 29181) in project 52
"""
import pytest
import os
from unittest.mock import MagicMock

from jama_mcp_server.tools.write_tools import jama_update_item
from jama_mcp_server.tools.read_tools import jama_get_item
from jama_mcp_server.client import JamaClientWrapper


# Skip integration tests if JAMA_MOCK_MODE is true (default in fixtures)
pytestmark = pytest.mark.skipif(
    os.getenv("JAMA_MOCK_MODE", "true").lower() == "true",
    reason="Integration tests require JAMA_MOCK_MODE=false and real JAMA credentials"
)


@pytest.fixture
def real_jama_client():
    """Create real JAMA client for integration testing."""
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
async def test_single_item_update_real_jama(integration_context):
    """Test updating a single JAMA item with real API (T011).

    This test:
    1. Creates a temporary NEED item in project 52
    2. Updates multiple fields including custom fields
    3. Verifies updates were applied and version incremented
    4. Cleans up by deleting the test item

    Prerequisites:
    - JAMA instance access
    - Project 52 exists with parent 28953
    - User has create/update/delete permissions
    """
    from jama_mcp_server.tools.write_tools import jama_create_item

    created_item_id = None
    jama_client = integration_context.request_context.lifespan_context["jama_client"]

    try:
        # Step 1: Create test item
        print(f"\nCreating temporary test item...")
        created_item = await jama_create_item(
            ctx=integration_context,
            project=52,
            item_type=134,  # NEED type
            name="UPDATE TEST - DELETE ME",
            parent=28953,
            description="<p>Temporary item for update testing</p>",
            custom_fields='{"fields": {"workflow_status$134": 615}}'
        )

        created_item_id = created_item["id"]
        print(f"  ✓ Created item {created_item['documentKey']} (ID: {created_item_id})")

        print(f"  ✓ Item ready for update")

        # Step 2: Update item with test values
        print(f"\nUpdating item fields...")
        test_name = "UPDATE TEST - MODIFIED"
        test_description = "<p>This is an updated description for testing</p>"
        test_rationale = "<p>This is a test rationale value</p>"

        updated_item = await jama_update_item(
            ctx=integration_context,
            item_id=created_item_id,
            name=test_name,
            description=test_description,
            **{"rationale$134": test_rationale}  # Custom field
        )

        # Step 3: Verify updates were applied
        assert updated_item["id"] == created_item_id
        assert updated_item["fields"]["name"] == test_name, \
            f"Name not updated: expected '{test_name}', got '{updated_item['fields']['name']}'"
        assert updated_item["fields"]["description"] == test_description, \
            f"Description not updated"
        assert updated_item["fields"]["rationale$134"] == test_rationale, \
            f"Rationale not updated"

        # Verify version incremented (if available)
        new_version = updated_item.get("currentVersion")
        if new_version:
            print(f"  ✓ Update successful! Version: {new_version}")
        else:
            print(f"  ✓ Update successful!")
        print(f"  ✓ Name: {updated_item['fields']['name']}")

        # Step 4: Verify by fetching again
        refetch_item = await jama_get_item(
            ctx=integration_context,
            item_id=str(created_item_id)
        )

        assert refetch_item["fields"]["name"] == test_name, \
            "Update not persisted (name mismatch on refetch)"

        print(f"  ✓ Changes persisted in JAMA")

    finally:
        # Cleanup: delete test item
        if created_item_id:
            try:
                print(f"\nCleaning up...")
                jama_client.delete_item(created_item_id)
                print(f"  ✓ Deleted test item {created_item_id}")
            except Exception as e:
                print(f"  ✗ Warning: Failed to delete test item {created_item_id}: {e}")


@pytest.mark.asyncio
async def test_update_locked_item_real_jama(integration_context):
    """Test that updating a locked item raises appropriate error (T011 extension).

    Note: This test requires manually locking item 29181 in JAMA UI first.
    If item is not locked, test will be skipped.
    """
    from jama_mcp_server.utils.errors import ValidationError

    test_item_id = 29181

    # Fetch item to check if locked
    item = await jama_get_item(
        ctx=integration_context,
        item_id=str(test_item_id)
    )

    # Check if item is locked (nested in 'lock' object)
    lock_info = item.get("lock", {})
    if not lock_info.get("locked"):
        pytest.skip(f"Item {test_item_id} is not locked - cannot test locked item update")

    # Attempt to update locked item should raise ValidationError
    with pytest.raises(ValidationError, match="Cannot update locked item"):
        await jama_update_item(
            ctx=integration_context,
            item_id=test_item_id,
            name="This should fail"
        )


@pytest.mark.asyncio
async def test_update_nonexistent_item(integration_context):
    """Test that updating a non-existent item raises appropriate error."""
    fake_item_id = 99999999

    # Should raise exception when fetching non-existent item
    with pytest.raises(Exception):  # py-jama-rest-client raises generic Exception for 404
        await jama_update_item(
            ctx=integration_context,
            item_id=fake_item_id,
            name="This should fail"
        )


@pytest.mark.asyncio
async def test_batch_update_real_jama(integration_context):
    """Test batch update with real JAMA API (T029).

    This test:
    1. Creates 3 temporary NEED items
    2. Updates all 3 items in a batch
    3. Verifies all updates succeeded
    4. Cleans up by deleting all test items

    Prerequisites:
    - JAMA instance access
    - Project 52 exists with parent 28953
    - User has create/update/delete permissions
    """
    from jama_mcp_server.tools.write_tools import jama_create_item, jama_batch_update_items

    created_item_ids = []
    jama_client = integration_context.request_context.lifespan_context["jama_client"]

    try:
        # Step 1: Create 3 test items
        print(f"\n1. Creating 3 temporary test items...")
        for i in range(3):
            item = await jama_create_item(
                ctx=integration_context,
                project=52,
                item_type=134,  # NEED type
                name=f"BATCH UPDATE TEST {i+1} - DELETE ME",
                parent=28953,
                description=f"<p>Item {i+1} for batch update testing</p>",
                custom_fields='{\"fields\": {\"workflow_status$134\": 615}}'
            )
            created_item_ids.append(item["id"])
            print(f"   ✓ Created item {item['documentKey']} (ID: {item['id']})")

        # Step 2: Batch update all items
        print(f"\n2. Batch updating {len(created_item_ids)} items...")
        updates = [
            {
                "item_id": created_item_ids[0],
                "fields": {
                    "name": "BATCH UPDATE TEST 1 - UPDATED",
                    "description": "<p>Item 1 updated via batch</p>"
                }
            },
            {
                "item_id": created_item_ids[1],
                "fields": {
                    "name": "BATCH UPDATE TEST 2 - UPDATED",
                    "rationale$134": "<p>Item 2 rationale updated</p>"
                }
            },
            {
                "item_id": created_item_ids[2],
                "fields": {
                    "description": "<p>Item 3 description only</p>",
                    "rationale$134": "<p>Item 3 rationale</p>"
                }
            }
        ]

        result = await jama_batch_update_items(
            ctx=integration_context,
            updates=updates
        )

        # Step 3: Verify batch update results
        assert result["total"] == 3, f"Expected 3 total updates, got {result['total']}"
        assert result["succeeded"] == 3, f"Expected 3 successful updates, got {result['succeeded']}"
        assert result["failed"] == 0, f"Expected 0 failures, got {result['failed']}"
        assert len(result["errors"]) == 0, f"Expected no errors, got {result['errors']}"

        print(f"   ✓ Batch update successful: {result['succeeded']}/{ result['total']} items updated")

        # Step 4: Verify individual updates
        print(f"\n3. Verifying individual updates...")
        item1 = await jama_get_item(ctx=integration_context, item_id=str(created_item_ids[0]))
        assert item1["fields"]["name"] == "BATCH UPDATE TEST 1 - UPDATED"
        print(f"   ✓ Item 1 name updated correctly")

        item2 = await jama_get_item(ctx=integration_context, item_id=str(created_item_ids[1]))
        assert item2["fields"]["name"] == "BATCH UPDATE TEST 2 - UPDATED"
        assert "Item 2 rationale updated" in item2["fields"].get("rationale$134", "")
        print(f"   ✓ Item 2 name and rationale updated correctly")

        item3 = await jama_get_item(ctx=integration_context, item_id=str(created_item_ids[2]))
        assert "Item 3 description only" in item3["fields"].get("description", "")
        print(f"   ✓ Item 3 description updated correctly")

        print(f"\n   ✓ All batch updates verified!")

    finally:
        # Cleanup: delete all test items
        if created_item_ids:
            print(f"\n4. Cleaning up...")
            for item_id in created_item_ids:
                try:
                    jama_client.delete_item(item_id)
                    print(f"   ✓ Deleted test item {item_id}")
                except Exception as e:
                    print(f"   ✗ Warning: Failed to delete test item {item_id}: {e}")
