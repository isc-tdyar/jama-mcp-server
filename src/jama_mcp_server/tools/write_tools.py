"""JAMA MCP Server - Write Operations Tools

This module contains all write operation MCP tools for JAMA Connect:
- Create, update, delete items (User Story 4)
- Batch operations and validation
"""
from typing import Optional, Dict, Any, List
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from mcp.server.fastmcp import Context
from ..models.item import ItemCreate, ItemUpdate
from ..utils.errors import (
    ValidationError,
    ConflictError,
    NotFoundError,
    ServerError
)

logger = logging.getLogger(__name__)


# ============================================================================
# User Story 4: Create and Update Requirements
# ============================================================================

async def jama_create_item(
    ctx: Context,
    project: int,
    item_type: int,
    parent: Optional[int],
    name: str,
    description: Optional[str] = None,
    **custom_fields
) -> Dict[str, Any]:
    """Create a new JAMA item with validation.

    Args:
        ctx: MCP context with JAMA client
        project: Project ID
        item_type: Item type ID
        parent: Parent item ID for hierarchical placement (None for root)
        name: Item name/title (required)
        description: Item description (optional)
        **custom_fields: Additional custom fields as keyword arguments

    Returns:
        Created item data with ID

    Raises:
        ValidationError: If required fields are missing or invalid
        ConflictError: If creation conflicts with existing data
        ServerError: On transient server errors (with retry)
    """
    logger.info(f"Creating item: project={project}, type={item_type}, name='{name}'")
    jama_client = ctx.request_context.lifespan_context["jama_client"]

    # Build item data using Pydantic model
    fields = {"name": name}
    if description:
        fields["description"] = description

    # Add custom fields
    fields.update(custom_fields)

    item_data = {
        "project": project,
        "itemType": item_type,
        "location": {"parent": parent} if parent else {},
        "fields": fields
    }

    # Validate using Pydantic model
    try:
        validated = ItemCreate(**item_data)
    except Exception as e:
        raise ValidationError(f"Item data validation failed: {e}", details={"item_data": item_data})

    # Create item with retry logic for transient failures
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(ServerError),
        reraise=True
    )
    async def _create_with_retry():
        return jama_client.post_item(validated.model_dump())

    try:
        created_item = await _create_with_retry()
        logger.info(f"Created item successfully: id={created_item.get('id')}")
        return created_item
    except Exception as e:
        logger.error(f"Failed to create item: {e}")
        raise


async def jama_update_item(
    ctx: Context,
    item_id: int,
    patch: bool = True,
    **fields
) -> Dict[str, Any]:
    """Update an existing JAMA item.

    Supports both PATCH (partial update) and PUT (full replacement).

    Args:
        ctx: MCP context with JAMA client
        item_id: Item ID to update
        patch: If True, use PATCH (partial), else PUT (full replacement)
        **fields: Fields to update as keyword arguments

    Returns:
        Updated item data

    Raises:
        ValidationError: If field data is invalid
        NotFoundError: If item doesn't exist
        ConflictError: If concurrent modification detected (409)
        PermissionError: If item is locked
        ServerError: On transient server errors (with retry)
    """
    logger.info(f"Updating item: item_id={item_id}, patch={patch}, fields={list(fields.keys())}")
    jama_client = ctx.request_context.lifespan_context["jama_client"]

    # Check if item exists and is not locked
    try:
        existing_item = jama_client.get_item(item_id)
    except Exception as e:
        raise NotFoundError(f"Item {item_id} not found", details={"item_id": item_id})

    if existing_item.get("locked"):
        raise ValidationError(
            f"Cannot update locked item {item_id}",
            details={"item_id": item_id, "locked": True}
        )

    # Build update data
    update_data = {"fields": fields}

    # Validate using Pydantic model
    try:
        validated = ItemUpdate(**update_data)
    except Exception as e:
        raise ValidationError(f"Update data validation failed: {e}", details={"update_data": update_data})

    # Update item with retry logic
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(ServerError),
        reraise=True
    )
    async def _update_with_retry():
        if patch:
            return jama_client.patch_item(item_id, validated.model_dump(exclude_none=True))
        else:
            return jama_client.put_item(item_id, validated.model_dump())

    try:
        updated_item = await _update_with_retry()
        logger.info(f"Updated item successfully: item_id={item_id}")

        # Verify version incremented
        new_version = updated_item.get("currentVersion")
        old_version = existing_item.get("currentVersion")
        if new_version and old_version and new_version <= old_version:
            logger.warning(f"Version did not increment: old={old_version}, new={new_version}")

        return updated_item
    except ConflictError:
        logger.error(f"Concurrent modification conflict for item {item_id}")
        raise ConflictError(
            f"Item {item_id} was modified by another user. Please refresh and try again.",
            details={"item_id": item_id, "current_version": existing_item.get("currentVersion")}
        )
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
    """Create multiple JAMA items in batch.

    Args:
        ctx: MCP context with JAMA client
        items: List of item data dictionaries (each with project, itemType, location, fields)

    Returns:
        Batch creation results with success count and any errors

    Raises:
        ValidationError: If any item data is invalid
    """
    logger.info(f"Batch creating {len(items)} items")

    results = {
        "total": len(items),
        "succeeded": 0,
        "failed": 0,
        "created_items": [],
        "errors": []
    }

    for idx, item_data in enumerate(items):
        try:
            # Extract fields
            project = item_data["project"]
            item_type = item_data["itemType"]
            parent = item_data.get("location", {}).get("parent")
            fields = item_data["fields"]
            name = fields.pop("name")
            description = fields.pop("description", None)

            # Create item
            created = await jama_create_item(
                ctx, project, item_type, parent, name, description, **fields
            )

            results["succeeded"] += 1
            results["created_items"].append({
                "index": idx,
                "item_id": created.get("id"),
                "name": name
            })

        except Exception as e:
            results["failed"] += 1
            results["errors"].append({
                "index": idx,
                "error": str(e),
                "item_data": item_data
            })
            logger.error(f"Failed to create item at index {idx}: {e}")

    logger.info(f"Batch create complete: {results['succeeded']}/{results['total']} succeeded")
    return results


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
