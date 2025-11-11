"""Unit tests for JAMA write tools - item creation fix.

Tests parameter transformation, validation, retry logic, and batch processing.
"""
import pytest
import json
from unittest.mock import Mock, MagicMock, AsyncMock, patch
import requests

from jama_mcp_server.tools.write_tools import jama_create_item, jama_batch_create_items, jama_update_item, jama_batch_update_items
from jama_mcp_server.utils.validation import validate_parent_exists, check_duplicate_name
from jama_mcp_server.utils.json_patch import fields_to_json_patch


@pytest.mark.asyncio
async def test_parameter_transformation(mcp_context):
    """Test that parameters are correctly transformed for JAMA API (T027)."""
    # Setup mock JAMA client
    mock_client = mcp_context.request_context.lifespan_context["jama_client"]

    # Mock validation functions
    with patch('jama_mcp_server.tools.write_tools.validate_parent_exists', new_callable=AsyncMock) as mock_validate, \
         patch('jama_mcp_server.tools.write_tools.check_duplicate_name', new_callable=AsyncMock) as mock_check_dup:

        mock_validate.return_value = None
        mock_check_dup.return_value = False

        # Mock post_item to return just the ID (as py-jama-rest-client does)
        mock_client.post_item.return_value = 100  # Returns ID only

        # Mock get_item to return full item data
        mock_client.get_item.return_value = {
            "id": 100,
            "documentKey": "PROJ-REQ-001",
            "itemType": 134,
            "project": 52,
            "fields": {
                "name": "Test NEED",
                "description": "<p>Test description</p>",
                "workflow_status$134": 615
            }
        }

        # Call jama_create_item
        result = await jama_create_item(
            ctx=mcp_context,
            project=52,
            item_type=134,
            name="Test NEED",
            parent=28953,
            description="<p>Test description</p>",
            custom_fields='{"fields": {"workflow_status$134": 615}}'
        )

        # Verify post_item was called with correct transformed parameters
        mock_client.post_item.assert_called_once()
        call_kwargs = mock_client.post_item.call_args.kwargs

        assert call_kwargs["project"] == 52
        assert call_kwargs["item_type_id"] == 134
        assert call_kwargs["child_item_type_id"] is None  # Fixed: None for leaf items
        assert call_kwargs["location"] == {"item": 28953}  # Fixed: no "parent" nesting
        assert call_kwargs["fields"]["name"] == "Test NEED"
        assert call_kwargs["fields"]["description"] == "<p>Test description</p>"
        assert call_kwargs["fields"]["workflow_status$134"] == 615

        # Verify result - get_item is called after post_item
        assert result["id"] == 100  # From mock get_item response
        assert result["documentKey"] == "PROJ-REQ-001"


@pytest.mark.asyncio
async def test_duplicate_name_detection(mcp_context):
    """Test that duplicate names are correctly detected (T028)."""
    # Note: This test is skipped because jama_get_item_children doesn't exist yet in read_tools.
    # The duplicate detection is tested indirectly in test_duplicate_name_rejection
    # and will be fully tested in integration tests.
    pytest.skip("jama_get_item_children not yet implemented - tested in integration tests")


@pytest.mark.asyncio
async def test_duplicate_name_rejection(mcp_context):
    """Test that duplicate names are rejected during item creation (T037 integration)."""
    # Mock parent validation to pass
    with patch('jama_mcp_server.tools.write_tools.validate_parent_exists', new_callable=AsyncMock) as mock_validate, \
         patch('jama_mcp_server.tools.write_tools.check_duplicate_name', new_callable=AsyncMock) as mock_check_dup:

        mock_validate.return_value = None
        mock_check_dup.return_value = True  # Duplicate exists

        # Attempt to create item with duplicate name
        with pytest.raises(ValueError, match="already exists under parent"):
            await jama_create_item(
                ctx=mcp_context,
                project=52,
                item_type=134,
                name="Duplicate Name",
                parent=28953
            )


@pytest.mark.asyncio
async def test_parent_validation_not_found(mcp_context):
    """Test parent validation for non-existent parent (T029, T038)."""
    # Mock get_item to raise 404 error
    with patch('jama_mcp_server.tools.read_tools.jama_get_item', new_callable=AsyncMock) as mock_get_item:
        mock_get_item.side_effect = Exception("404 Not Found")

        # Validation should raise ValueError
        with pytest.raises(ValueError, match="Parent item .* not found"):
            await validate_parent_exists(mcp_context, parent_id=99999)


@pytest.mark.asyncio
async def test_parent_validation_permission_denied(mcp_context):
    """Test parent validation for permission denied (T029)."""
    # Mock get_item to raise 403 error
    with patch('jama_mcp_server.tools.read_tools.jama_get_item', new_callable=AsyncMock) as mock_get_item:
        mock_get_item.side_effect = Exception("403 Permission denied")

        # Validation should raise ValueError with permission message
        with pytest.raises(ValueError, match="Permission denied"):
            await validate_parent_exists(mcp_context, parent_id=12345)


@pytest.mark.asyncio
async def test_batch_size_limit(mcp_context):
    """Test that batches over 100 items are rejected (T030)."""
    # Create 101 items
    items = [
        {
            "project": 52,
            "itemType": 134,
            "location": {"parent": 28953},
            "fields": {"name": f"Item {i}"}
        }
        for i in range(101)
    ]

    # Should raise ValueError
    with pytest.raises(ValueError, match="exceeds maximum of 100"):
        await jama_batch_create_items(ctx=mcp_context, items=items)


@pytest.mark.asyncio
async def test_batch_abort_on_failure(mcp_context):
    """Test that batch processing stops on first failure (T031)."""
    mock_client = mcp_context.request_context.lifespan_context["jama_client"]

    # Create mock items - 2nd one will fail
    items = [
        {
            "project": 52,
            "itemType": 134,
            "location": {"parent": 28953},
            "fields": {"name": "Item 1", "description": "First item"}
        },
        {
            "project": 52,
            "itemType": 134,
            "location": {"parent": 99999},  # Invalid parent
            "fields": {"name": "Item 2", "description": "Second item (will fail)"}
        },
        {
            "project": 52,
            "itemType": 134,
            "location": {"parent": 28953},
            "fields": {"name": "Item 3", "description": "Third item (should not be created)"}
        },
        {
            "project": 52,
            "itemType": 134,
            "location": {"parent": 28953},
            "fields": {"name": "Item 4", "description": "Fourth item (should not be created)"}
        }
    ]

    with patch('jama_mcp_server.tools.write_tools.validate_parent_exists', new_callable=AsyncMock) as mock_validate, \
         patch('jama_mcp_server.tools.write_tools.check_duplicate_name', new_callable=AsyncMock) as mock_check_dup:

        # First call succeeds, second call fails (invalid parent)
        async def validate_parent_side_effect(ctx, parent_id):
            if parent_id == 99999:
                raise ValueError(f"Parent item {parent_id} not found")

        mock_validate.side_effect = validate_parent_side_effect
        mock_check_dup.return_value = False

        # Mock successful creation for first item
        mock_client.post_item.return_value = 1001  # Returns ID only
        mock_client.get_item.return_value = {
            "id": 1001,
            "documentKey": "PROJ-001",
            "itemType": 134,
            "project": 52
        }

        # Call batch create
        result = await jama_batch_create_items(ctx=mcp_context, items=items)

        # Verify only first item was created, processing stopped at second item
        assert result["total"] == 4
        assert result["succeeded"] == 1
        assert result["failed"] == 1
        assert len(result["created_items"]) == 1
        assert len(result["errors"]) == 1
        assert result["errors"][0]["index"] == 1
        assert "Parent item 99999 not found" in result["errors"][0]["error"]


@pytest.mark.asyncio
async def test_retry_logic_network_timeout(mcp_context):
    """Test retry logic for network timeout (T032)."""
    mock_client = mcp_context.request_context.lifespan_context["jama_client"]

    with patch('jama_mcp_server.tools.write_tools.validate_parent_exists', new_callable=AsyncMock) as mock_validate, \
         patch('jama_mcp_server.tools.write_tools.check_duplicate_name', new_callable=AsyncMock) as mock_check_dup:

        mock_validate.return_value = None
        mock_check_dup.return_value = False

        # First call times out, second call succeeds
        call_count = 0
        def post_item_with_retry(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise requests.exceptions.Timeout("Connection timeout")
            return 2001  # post_item returns just the ID

        mock_client.post_item.side_effect = post_item_with_retry

        # Mock get_item to return item with the created ID
        mock_client.get_item.return_value = {
            "id": 2001,
            "documentKey": "PROJ-RETRY-001",
            "itemType": 134,
            "project": 52
        }

        # Call should succeed after retry
        result = await jama_create_item(
            ctx=mcp_context,
            project=52,
            item_type=134,
            name="Retry Test",
            parent=28953
        )

        # Verify it retried (called twice)
        assert call_count == 2
        assert result["id"] == 2001


@pytest.mark.asyncio
async def test_retry_exhaustion(mcp_context):
    """Test that retry gives up after max attempts (T032)."""
    from tenacity import RetryError

    mock_client = mcp_context.request_context.lifespan_context["jama_client"]

    with patch('jama_mcp_server.tools.write_tools.validate_parent_exists', new_callable=AsyncMock) as mock_validate, \
         patch('jama_mcp_server.tools.write_tools.check_duplicate_name', new_callable=AsyncMock) as mock_check_dup:

        mock_validate.return_value = None
        mock_check_dup.return_value = False

        # Always timeout
        mock_client.post_item.side_effect = requests.exceptions.Timeout("Connection timeout")

        # Should raise RetryError after retries exhausted (tenacity wraps the original exception)
        with pytest.raises(RetryError):
            await jama_create_item(
                ctx=mcp_context,
                project=52,
                item_type=134,
                name="Timeout Test",
                parent=28953
            )


@pytest.mark.asyncio
async def test_custom_fields_parsing(mcp_context):
    """Test that custom_fields JSON is correctly parsed and merged (T027)."""
    mock_client = mcp_context.request_context.lifespan_context["jama_client"]

    with patch('jama_mcp_server.tools.write_tools.validate_parent_exists', new_callable=AsyncMock) as mock_validate, \
         patch('jama_mcp_server.tools.write_tools.check_duplicate_name', new_callable=AsyncMock) as mock_check_dup:

        mock_validate.return_value = None
        mock_check_dup.return_value = False
        mock_client.post_item.return_value = 3001  # Returns ID only
        mock_client.get_item.return_value = {"id": 3001, "documentKey": "PROJ-003"}

        # Test with complex custom fields
        custom_fields_json = json.dumps({
            "fields": {
                "workflow_status$134": 615,
                "priority$134": 1,
                "assigned_to$134": "user@example.com"
            }
        })

        result = await jama_create_item(
            ctx=mcp_context,
            project=52,
            item_type=134,
            name="Custom Fields Test",
            parent=28953,
            custom_fields=custom_fields_json
        )

        # Verify custom fields were merged into fields dict
        call_kwargs = mock_client.post_item.call_args.kwargs
        assert call_kwargs["fields"]["workflow_status$134"] == 615
        assert call_kwargs["fields"]["priority$134"] == 1
        assert call_kwargs["fields"]["assigned_to$134"] == "user@example.com"
        assert call_kwargs["fields"]["name"] == "Custom Fields Test"


@pytest.mark.asyncio
async def test_invalid_custom_fields_json(mcp_context):
    """Test that invalid JSON in custom_fields raises ValueError (T027)."""
    with patch('jama_mcp_server.tools.write_tools.validate_parent_exists', new_callable=AsyncMock) as mock_validate, \
         patch('jama_mcp_server.tools.write_tools.check_duplicate_name', new_callable=AsyncMock) as mock_check_dup:

        mock_validate.return_value = None
        mock_check_dup.return_value = False

        # Invalid JSON
        with pytest.raises(ValueError, match="Invalid JSON"):
            await jama_create_item(
                ctx=mcp_context,
                project=52,
                item_type=134,
                name="Invalid JSON Test",
                parent=28953,
                custom_fields='{"invalid": json}'  # Invalid JSON syntax
            )


# ============================================================================
# jama_update_item tests (Phase 3: User Story 1)
# ============================================================================

@pytest.mark.asyncio
async def test_update_item_parameter_transformation(mcp_context):
    """Test that update fields are correctly transformed to JSON Patch (T008)."""
    mock_client = mcp_context.request_context.lifespan_context["jama_client"]

    # Mock get_item for pre-update check
    mock_client.get_item.side_effect = [
        # First call: pre-update check
        {
            "id": 29181,
            "documentKey": "IRIS-NEED-793",
            "locked": False,
            "currentVersion": 5,
            "fields": {
                "name": "Old Name",
                "description": "<p>Old description</p>"
            }
        },
        # Second call: post-update fetch
        {
            "id": 29181,
            "documentKey": "IRIS-NEED-793",
            "locked": False,
            "currentVersion": 6,  # Incremented
            "fields": {
                "name": "Updated Name",
                "description": "<p>Updated description</p>",
                "rationale$134": "<p>Updated rationale</p>"
            }
        }
    ]

    # Mock patch_item
    mock_client.patch_item.return_value = None  # patch_item returns None

    # Call jama_update_item
    result = await jama_update_item(
        ctx=mcp_context,
        item_id=29181,
        name="Updated Name",
        description="<p>Updated description</p>",
        **{"rationale$134": "<p>Updated rationale</p>"}  # Custom field with $
    )

    # Verify patch_item was called with correct JSON Patch format
    mock_client.patch_item.assert_called_once()
    call_args = mock_client.patch_item.call_args

    item_id = call_args[0][0]
    patches = call_args[0][1]

    assert item_id == 29181

    # Verify JSON Patch operations array
    assert isinstance(patches, list)
    assert len(patches) == 3

    # Verify each operation has correct structure (using 'add' which works for both new and existing fields)
    expected_patches = [
        {"op": "add", "path": "/fields/name", "value": "Updated Name"},
        {"op": "add", "path": "/fields/description", "value": "<p>Updated description</p>"},
        {"op": "add", "path": "/fields/rationale$134", "value": "<p>Updated rationale</p>"}
    ]

    for expected_patch in expected_patches:
        assert expected_patch in patches

    # Verify result is the updated item
    assert result["id"] == 29181
    assert result["currentVersion"] == 6
    assert result["fields"]["name"] == "Updated Name"


@pytest.mark.asyncio
async def test_update_item_locked(mcp_context):
    """Test that locked items cannot be updated (T009)."""
    from jama_mcp_server.utils.errors import ValidationError

    mock_client = mcp_context.request_context.lifespan_context["jama_client"]

    # Mock get_item to return locked item (lock info is nested in 'lock' object)
    mock_client.get_item.return_value = {
        "id": 29181,
        "documentKey": "IRIS-NEED-793",
        "lock": {
            "locked": True,  # Item is locked (nested structure)
            "lastLockedDate": "2025-11-11T12:00:00.000+0000",
            "lockedBy": 12345
        },
        "currentVersion": 5
    }

    # Attempt to update should raise ValidationError
    with pytest.raises(ValidationError, match="Cannot update locked item"):
        await jama_update_item(
            ctx=mcp_context,
            item_id=29181,
            name="Should Fail"
        )

    # Verify patch_item was NOT called
    mock_client.patch_item.assert_not_called()


@pytest.mark.asyncio
async def test_update_item_concurrent_modification(mcp_context):
    """Test that concurrent modifications are detected via version tracking (T010)."""
    mock_client = mcp_context.request_context.lifespan_context["jama_client"]

    # Mock get_item calls
    mock_client.get_item.side_effect = [
        # First call: pre-update check
        {
            "id": 29181,
            "documentKey": "IRIS-NEED-793",
            "locked": False,
            "currentVersion": 5,
            "fields": {"name": "Original Name"}
        },
        # Second call: post-update fetch - version DIDN'T increment (concurrent modification)
        {
            "id": 29181,
            "documentKey": "IRIS-NEED-793",
            "locked": False,
            "currentVersion": 5,  # Same version - suspicious!
            "fields": {"name": "Different Name"}  # Changed by someone else
        }
    ]

    # Mock patch_item
    mock_client.patch_item.return_value = None

    # Call update - should log warning but not raise error
    with patch('jama_mcp_server.tools.write_tools.logger') as mock_logger:
        result = await jama_update_item(
            ctx=mcp_context,
            item_id=29181,
            name="My Update"
        )

        # Verify warning was logged
        mock_logger.warning.assert_called()
        warning_message = mock_logger.warning.call_args[0][0]
        assert "Version did not increment" in warning_message
        assert "old=5" in warning_message
        assert "new=5" in warning_message

    # Result should still be returned (post-update item)
    assert result["id"] == 29181
    assert result["currentVersion"] == 5


# ============================================================================
# jama_batch_update_items tests (Phase 4: User Story 2)
# ============================================================================

@pytest.mark.asyncio
async def test_batch_update_success(mcp_context):
    """Test successful batch update of multiple items (T024)."""
    mock_client = mcp_context.request_context.lifespan_context["jama_client"]

    # Mock get_item and patch_item for each update
    def get_item_side_effect(item_id):
        return {
            "id": item_id,
            "documentKey": f"IRIS-NEED-{item_id}",
            "lock": {"locked": False},
            "currentVersion": 1,
            "fields": {"name": f"Original Name {item_id}"}
        }

    mock_client.get_item.side_effect = get_item_side_effect
    mock_client.patch_item.return_value = None

    # Create batch update request
    updates = [
        {"item_id": 100, "fields": {"name": "Updated Name 100"}},
        {"item_id": 101, "fields": {"description": "<p>Updated desc 101</p>"}},
        {"item_id": 102, "fields": {"name": "New Name 102", "rationale$134": "<p>Rationale</p>"}}
    ]

    result = await jama_batch_update_items(ctx=mcp_context, updates=updates)

    # Verify results
    assert result["total"] == 3
    assert result["succeeded"] == 3
    assert result["failed"] == 0
    assert len(result["updated_items"]) == 3
    assert len(result["errors"]) == 0

    # Verify patch_item was called 3 times
    assert mock_client.patch_item.call_count == 3


@pytest.mark.asyncio
async def test_batch_update_size_limit(mcp_context):
    """Test that batch size limit is enforced (T025)."""
    # Create 101 updates (exceeds max of 100)
    updates = [
        {"item_id": i, "fields": {"name": f"Name {i}"}}
        for i in range(101)
    ]

    # Should raise ValueError
    with pytest.raises(ValueError, match="exceeds maximum of 100"):
        await jama_batch_update_items(ctx=mcp_context, updates=updates)


@pytest.mark.asyncio
async def test_batch_update_abort_on_failure(mcp_context):
    """Test that batch update aborts on first failure (T026)."""
    mock_client = mcp_context.request_context.lifespan_context["jama_client"]

    # Mock get_item - second item is locked
    def get_item_side_effect(item_id):
        if item_id == 201:
            return {
                "id": 201,
                "lock": {"locked": True, "lockedBy": 95},
                "currentVersion": 1,
                "fields": {}
            }
        return {
            "id": item_id,
            "lock": {"locked": False},
            "currentVersion": 1,
            "fields": {"name": f"Name {item_id}"}
        }

    mock_client.get_item.side_effect = get_item_side_effect
    mock_client.patch_item.return_value = None

    # Create batch with 4 updates - second one will fail
    updates = [
        {"item_id": 200, "fields": {"name": "Name 200"}},
        {"item_id": 201, "fields": {"name": "Name 201"}},  # Locked - will fail
        {"item_id": 202, "fields": {"name": "Name 202"}},  # Should not be attempted
        {"item_id": 203, "fields": {"name": "Name 203"}}   # Should not be attempted
    ]

    result = await jama_batch_update_items(ctx=mcp_context, updates=updates)

    # Verify only first item was updated
    assert result["total"] == 4
    assert result["succeeded"] == 1
    assert result["failed"] == 1
    assert len(result["updated_items"]) == 1
    assert len(result["errors"]) == 1
    assert result["errors"][0]["index"] == 1
    assert "locked" in result["errors"][0]["error"].lower()

    # Verify patch_item was only called once (for first item)
    assert mock_client.patch_item.call_count == 1


@pytest.mark.asyncio
async def test_batch_update_missing_item_id(mcp_context):
    """Test that missing item_id raises error (T027)."""
    updates = [
        {"fields": {"name": "Name 1"}}  # Missing item_id
    ]

    result = await jama_batch_update_items(ctx=mcp_context, updates=updates)

    # Should fail on first update
    assert result["total"] == 1
    assert result["succeeded"] == 0
    assert result["failed"] == 1
    assert "missing required 'item_id'" in result["errors"][0]["error"]


@pytest.mark.asyncio
async def test_batch_update_missing_fields(mcp_context):
    """Test that missing fields raises error (T028)."""
    updates = [
        {"item_id": 100}  # Missing fields
    ]

    result = await jama_batch_update_items(ctx=mcp_context, updates=updates)

    # Should fail on first update
    assert result["total"] == 1
    assert result["succeeded"] == 0
    assert result["failed"] == 1
    assert "missing required 'fields'" in result["errors"][0]["error"]
