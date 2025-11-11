"""JAMA MCP Server - Write Operations Tools

This module contains all write operation MCP tools for JAMA Connect:
- Create, update, delete items (User Story 4)
- Batch operations and validation
"""
from typing import Optional, Dict, Any, List
import logging
import json
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, wait_fixed, retry_if_exception_type

from mcp.server.fastmcp import Context
from ..models.item import ItemCreate, ItemUpdate
from ..utils.errors import (
    ValidationError,
    ConflictError,
    NotFoundError,
    ServerError
)
from ..utils.validation import validate_parent_exists, check_duplicate_name

logger = logging.getLogger(__name__)


# ============================================================================
# User Story 4: Create and Update Requirements
# ============================================================================

async def jama_create_item(
    ctx: Context,
    project: int,
    item_type: int,
    name: str,
    parent: int,
    description: str = "",
    custom_fields: str = "{}"
) -> Dict[str, Any]:
    """Create a new JAMA item with proper parameter mapping.

    This function correctly maps MCP tool parameters to the py-jama-rest-client
    post_item() signature, fixing the "missing 4 required positional arguments" error.

    Args:
        ctx: MCP context with JAMA client
        project: JAMA project ID where item will be created
        item_type: JAMA item type ID (e.g., 134 for NEED)
        name: Item name/title (required, 1-255 characters)
        parent: Parent item ID under which to create this item
        description: HTML-formatted item description (optional)
        custom_fields: JSON string containing custom field values (optional)
            Example: '{"fields": {"workflow_status$134": 615}}'

    Returns:
        Created item data with ID, documentKey, and all fields

    Raises:
        ValueError: If parent doesn't exist or duplicate name detected
        ValidationError: If required fields are missing or invalid
        requests.exceptions.Timeout: If network timeout occurs
        requests.exceptions.ConnectionError: If connection fails
    """
    logger.info(f"Creating item: project={project}, type={item_type}, name='{name}', parent={parent}")
    logger.debug(f"Parameter types: project={type(project)}, item_type={type(item_type)}, name={type(name)}, parent={type(parent)}")
    logger.debug(f"description={description}, custom_fields={custom_fields}")
    jama_client = ctx.request_context.lifespan_context["jama_client"]

    # Pre-creation validation
    logger.debug(f"Validating parent exists: {parent}")
    await validate_parent_exists(ctx, parent)

    logger.debug("Checking for duplicate name...")
    if await check_duplicate_name(ctx, parent, name):
        raise ValueError(f"Item with name '{name}' already exists under parent {parent}")

    # Parse custom_fields JSON string
    try:
        custom_fields_dict = json.loads(custom_fields) if custom_fields else {}
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in custom_fields: {e}")

    # Extract fields from custom_fields structure
    # Support both formats: {"fields": {...}} and {...} directly
    if "fields" in custom_fields_dict:
        fields_data = custom_fields_dict["fields"]
    else:
        # Assume the dict IS the fields (backward compatibility)
        fields_data = custom_fields_dict

    # Merge name and description into fields dict
    fields_data["name"] = name
    if description:
        fields_data["description"] = description

    # Construct location dict - py-jama-rest-client wraps this in {"parent": ...}
    # So we pass {"item": parent_id} which becomes {"parent": {"item": parent_id}}
    location_data = {"item": parent}

    logger.debug(f"Transformed parameters - location: {location_data}, fields count: {len(fields_data)}")

    # Call JAMA API with retry logic for network failures only
    @retry(
        stop=stop_after_attempt(2),  # Original attempt + 1 retry = 2 total
        wait=wait_fixed(2),           # 2-second wait between attempts
        retry=retry_if_exception_type((requests.exceptions.Timeout,
                                       requests.exceptions.ConnectionError))
    )
    def create_with_retry():
        # post_item returns just the item ID (integer), not a dict
        item_id = jama_client.post_item(
            project=project,
            item_type_id=item_type,
            child_item_type_id=None,  # None for leaf items (not containers)
            location=location_data,
            fields=fields_data
        )
        # Fetch the full item to return complete data
        return jama_client.get_item(item_id)

    try:
        created_item = create_with_retry()
        logger.info(f"Created item successfully: id={created_item.get('id')}, documentKey={created_item.get('documentKey')}")
        return created_item
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
        logger.error(f"Network error creating item after retry: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to create item: {e}")
        raise


async def jama_update_item(
    ctx: Context,
    item_id: int,
    fields: Optional[Dict[str, Any]] = None,
    **additional_fields
) -> Dict[str, Any]:
    """Update an existing JAMA item using JSON Patch (RFC 6902).

    Args:
        ctx: MCP context with JAMA client
        item_id: Item ID to update
        fields: Dictionary of fields to update (alternative to kwargs)
        **additional_fields: Fields to update as keyword arguments

    Returns:
        Updated item data

    Raises:
        ValidationError: If no fields provided or item is locked
        NotFoundError: If item doesn't exist
        ConflictError: If concurrent modification detected (409)
        ServerError: On transient server errors (with retry)

    Example:
        # Option 1: Using fields dict
        await jama_update_item(
            ctx=context,
            item_id=29181,
            fields={"name": "Updated Name", "description": "<p>Updated</p>"}
        )

        # Option 2: Using kwargs
        await jama_update_item(
            ctx=context,
            item_id=29181,
            name="Updated Name",
            description="<p>Updated description</p>"
        )
    """
    from jama_mcp_server.utils.json_patch import fields_to_json_patch

    # Merge fields dict and additional_fields kwargs
    all_fields = {}
    if fields:
        all_fields.update(fields)
    if additional_fields:
        all_fields.update(additional_fields)

    logger.info(f"Updating item: item_id={item_id}, fields={list(all_fields.keys())}")
    fields = all_fields  # Use merged fields for rest of function
    jama_client = ctx.request_context.lifespan_context["jama_client"]

    # Validate at least one field provided
    if not fields:
        raise ValidationError(
            "At least one field must be provided for update",
            details={"item_id": item_id}
        )

    # Pre-update validation: Check if item exists and is not locked
    try:
        existing_item = jama_client.get_item(item_id)
    except Exception as e:
        logger.error(f"Failed to fetch item {item_id} for pre-update check: {e}")
        raise NotFoundError(f"Item {item_id} not found", details={"item_id": item_id})

    # Check if item is locked (lock status is nested in 'lock' object)
    lock_info = existing_item.get("lock", {})
    if lock_info.get("locked"):
        raise ValidationError(
            f"Cannot update locked item {item_id}",
            details={"item_id": item_id, "locked": True, "locked_by": lock_info.get("lockedBy")}
        )

    # Store version for post-update verification
    old_version = existing_item.get("currentVersion")
    logger.debug(f"Item {item_id} current version: {old_version}")

    # Convert fields dict to JSON Patch operations (RFC 6902)
    try:
        patches = fields_to_json_patch(fields)
        logger.debug(f"Generated {len(patches)} JSON Patch operations for item {item_id}")
    except Exception as e:
        raise ValidationError(
            f"Failed to generate JSON Patch operations: {e}",
            details={"item_id": item_id, "fields": list(fields.keys())}
        )

    # Update item with retry logic (network errors and server errors)
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((ServerError, requests.exceptions.Timeout, requests.exceptions.ConnectionError)),
        reraise=True
    )
    async def _update_with_retry():
        try:
            # patch_item expects: patch_item(item_id, patches_array)
            # Returns None on success
            jama_client.patch_item(item_id, patches)
            logger.debug(f"patch_item completed for item {item_id}")
            return None
        except Exception as e:
            # Check for HTTP 409 Conflict
            if "409" in str(e) or "Conflict" in str(e):
                raise ConflictError(
                    f"Item {item_id} was modified by another user. Please refresh and try again.",
                    details={"item_id": item_id, "current_version": old_version}
                )
            # HTTP 500/503 get wrapped in ServerError for retry
            if "500" in str(e) or "503" in str(e):
                raise ServerError(f"Transient server error: {e}", details={"item_id": item_id})
            raise

    try:
        await _update_with_retry()
        logger.info(f"Updated item successfully: item_id={item_id}")

        # Post-update validation: Fetch updated item and verify version increment
        updated_item = jama_client.get_item(item_id)
        new_version = updated_item.get("currentVersion")

        if old_version and new_version:
            if new_version <= old_version:
                logger.warning(
                    f"Version did not increment for item {item_id}: old={old_version}, new={new_version}. "
                    f"Possible concurrent modification."
                )
            else:
                logger.debug(f"Version incremented: {old_version} → {new_version}")

        return updated_item

    except ConflictError:
        logger.error(f"Concurrent modification conflict for item {item_id}")
        raise
    except Exception as e:
        logger.error(f"Failed to update item {item_id}: {e}")
        raise


async def jama_delete_item(
    ctx: Context,
    item_id: int
) -> Dict[str, Any]:
    """Delete a JAMA item (soft delete - marks as inactive).

    JAMA uses soft delete to preserve relationships and history.

    Args:
        ctx: MCP context with JAMA client
        item_id: Item ID to delete

    Returns:
        Deletion confirmation

    Raises:
        NotFoundError: If item doesn't exist
        PermissionError: If item is locked or cannot be deleted
        ServerError: On transient server errors (with retry)
    """
    logger.info(f"Deleting item: item_id={item_id}")
    jama_client = ctx.request_context.lifespan_context["jama_client"]

    # Check if item exists and is not locked
    try:
        existing_item = jama_client.get_item(item_id)
    except Exception as e:
        raise NotFoundError(f"Item {item_id} not found", details={"item_id": item_id})

    if existing_item.get("locked"):
        raise ValidationError(
            f"Cannot delete locked item {item_id}",
            details={"item_id": item_id, "locked": True}
        )

    # Delete with retry logic
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(ServerError),
        reraise=True
    )
    async def _delete_with_retry():
        return jama_client.delete_item(item_id)

    try:
        result = await _delete_with_retry()
        logger.info(f"Deleted item successfully: item_id={item_id}")
        return {"success": True, "item_id": item_id, "result": result}
    except Exception as e:
        logger.error(f"Failed to delete item {item_id}: {e}")
        raise


async def jama_batch_create_items(
    ctx: Context,
    items: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Create multiple JAMA items in batch with abort-on-failure behavior.

    Processes items sequentially and aborts on first failure. Successfully
    created items before failure are NOT rolled back.

    Args:
        ctx: MCP context with JAMA client
        items: List of item specifications (max 100 items). Each item should contain:
            - project (int): JAMA project ID
            - itemType (int): Item type ID
            - location (dict): {"parent": parent_id}
            - fields (dict): {"name": str, "description": str (optional), ...custom fields}

    Returns:
        Batch creation results with structure:
        {
            "total": Total number of items in batch,
            "succeeded": Number of successfully created items,
            "failed": Number of failed items (0 or 1 due to abort-on-failure),
            "created_items": List of created item details,
            "errors": List with error details for failed item (empty if all succeeded)
        }

    Raises:
        ValueError: If batch size exceeds 100 items
    """
    logger.info(f"Batch creating {len(items)} items")

    # Validate batch size (FR-012)
    if len(items) > 100:
        raise ValueError(
            f"Batch size ({len(items)}) exceeds maximum of 100 items. "
            f"Please split into multiple batches."
        )

    created_items = []
    failed_item = None

    for index, item_spec in enumerate(items):
        try:
            # Extract parameters from batch item spec
            project = item_spec["project"]
            item_type = item_spec["itemType"]
            parent = item_spec.get("location", {}).get("parent")
            fields = item_spec["fields"]

            # Extract name and description from fields
            name = fields.get("name")
            if not name:
                raise ValueError("Item name is required")

            description = fields.get("description", "")

            # Build custom_fields JSON from remaining fields
            custom_fields_dict = {
                "fields": {k: v for k, v in fields.items() if k not in ["name", "description"]}
            }
            custom_fields_json = json.dumps(custom_fields_dict)

            # Create single item (reuse US1 logic)
            logger.debug(f"Creating batch item {index + 1}/{len(items)}: '{name}'")
            created = await jama_create_item(
                ctx=ctx,
                project=project,
                item_type=item_type,
                name=name,
                parent=parent,
                description=description,
                custom_fields=custom_fields_json
            )

            created_items.append(created)
            logger.debug(f"Batch item {index + 1} created: {created.get('documentKey')}")

        except Exception as e:
            # Abort on first failure
            logger.error(f"Batch failed at index {index}: {e}")
            failed_item = {
                "index": index,
                "error": str(e),
                "item_data": item_spec
            }
            break

    # Build response structure
    result = {
        "total": len(items),
        "succeeded": len(created_items),
        "failed": 1 if failed_item else 0,
        "created_items": created_items,
        "errors": [failed_item] if failed_item else []
    }

    logger.info(f"Batch create complete: {result['succeeded']}/{result['total']} succeeded")
    if failed_item:
        logger.warning(f"Batch aborted at item {failed_item['index']} due to: {failed_item['error']}")

    return result


async def jama_batch_update_items(
    ctx: Context,
    updates: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Update multiple JAMA items in batch with abort-on-failure behavior.

    Processes updates sequentially and aborts on first failure. Successfully
    updated items before failure are NOT rolled back.

    Args:
        ctx: MCP context with JAMA client
        updates: List of update specifications (max 100 items). Each update should contain:
            - item_id (int): Item ID to update
            - fields (dict): Fields to update {field_name: value}

    Returns:
        Batch update results with structure:
        {
            "total": Total number of updates in batch,
            "succeeded": Number of successfully updated items,
            "failed": Number of failed updates (0 or 1 due to abort-on-failure),
            "updated_items": List of updated item details,
            "errors": List with error details for failed update (empty if all succeeded)
        }

    Raises:
        ValueError: If batch size exceeds 100 items

    Example:
        updates = [
            {"item_id": 29181, "fields": {"name": "Updated Name 1"}},
            {"item_id": 29182, "fields": {"description": "<p>New desc</p>"}},
            {"item_id": 29183, "fields": {"name": "New Name", "rationale$134": "<p>Rationale</p>"}}
        ]
        result = await jama_batch_update_items(ctx=context, updates=updates)
    """
    logger.info(f"Batch updating {len(updates)} items")

    # Validate batch size (FR-012)
    if len(updates) > 100:
        raise ValueError(
            f"Batch size ({len(updates)}) exceeds maximum of 100 items. "
            f"Please split into multiple batches."
        )

    updated_items = []
    failed_update = None

    for index, update_spec in enumerate(updates):
        try:
            # Extract parameters from batch update spec
            item_id = update_spec.get("item_id")
            if not item_id:
                raise ValueError(f"Update at index {index} missing required 'item_id' field")

            fields = update_spec.get("fields")
            if not fields:
                raise ValueError(f"Update at index {index} missing required 'fields' field")

            # Update single item (reuse US1 logic)
            logger.debug(f"Updating batch item {index + 1}/{len(updates)}: item_id={item_id}")
            updated = await jama_update_item(
                ctx=ctx,
                item_id=item_id,
                **fields
            )

            updated_items.append(updated)
            logger.debug(f"Batch item {index + 1} updated: item_id={item_id}")

        except Exception as e:
            # Abort on first failure
            logger.error(f"Batch failed at index {index}: {e}")
            failed_update = {
                "index": index,
                "error": str(e),
                "update_data": update_spec
            }
            break

    # Build response structure
    result = {
        "total": len(updates),
        "succeeded": len(updated_items),
        "failed": 1 if failed_update else 0,
        "updated_items": updated_items,
        "errors": [failed_update] if failed_update else []
    }

    logger.info(f"Batch update complete: {result['succeeded']}/{result['total']} succeeded")
    if failed_update:
        logger.warning(f"Batch aborted at item {failed_update['index']} due to: {failed_update['error']}")

    return result


async def jama_validate_item_fields(
    ctx: Context,
    item_type_id: int,
    fields: Dict[str, Any]
) -> Dict[str, Any]:
    """Validate item fields against item type schema.

    Performs dynamic validation using JAMA's field definitions for the item type.

    Args:
        ctx: MCP context with JAMA client
        item_type_id: Item type ID
        fields: Fields to validate

    Returns:
        Validation results with any errors or warnings

    Raises:
        ValidationError: If validation fails
    """
    logger.info(f"Validating fields for item type: {item_type_id}")
    jama_client = ctx.request_context.lifespan_context["jama_client"]

    # Get field schema for item type
    try:
        field_schema = jama_client.get_pick_lists(item_type_id)
    except Exception as e:
        raise ValidationError(
            f"Failed to retrieve field schema for item type {item_type_id}",
            details={"item_type_id": item_type_id, "error": str(e)}
        )

    validation_results = {
        "valid": True,
        "errors": [],
        "warnings": []
    }

    # Check required field 'name'
    if "name" not in fields or not fields["name"]:
        validation_results["valid"] = False
        validation_results["errors"].append({
            "field": "name",
            "message": "Field 'name' is required"
        })

    # TODO: Add more comprehensive validation based on field_schema
    # - Check field types (string, number, date, picklist, etc.)
    # - Check required fields
    # - Check picklist values
    # - Check field constraints (min/max length, etc.)

    logger.info(f"Validation complete: valid={validation_results['valid']}")
    return validation_results
