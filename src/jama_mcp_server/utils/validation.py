"""JAMA Field Validation Utilities

Utilities for validating JAMA item fields before create/update operations.
Includes dynamic schema validation for custom fields and parent/duplicate checks.
"""
import logging
from typing import Dict, Any, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import Context

logger = logging.getLogger(__name__)


async def validate_parent_exists(ctx: "Context", parent_id: int) -> None:
    """Validate that parent item exists and user has access.

    Args:
        ctx: MCP context with JAMA client
        parent_id: JAMA parent item ID

    Raises:
        ValueError: If parent doesn't exist or permission denied
    """
    from ..tools.read_tools import jama_get_item

    logger.debug(f"Validating parent exists: parent_id={parent_id} (type: {type(parent_id)})")

    try:
        # jama_get_item expects int, not string
        parent_item = await jama_get_item(ctx, item_id=int(parent_id))
        if not parent_item:
            raise ValueError(f"Parent item {parent_id} not found")
        logger.debug(f"Parent validation successful: {parent_id}")
    except Exception as e:
        logger.error(f"Parent validation failed for {parent_id}: {e}")
        error_str = str(e).lower()
        if "404" in str(e) or "not found" in error_str:
            raise ValueError(f"Parent item {parent_id} not found")
        elif "403" in str(e) or "permission" in error_str:
            raise ValueError(f"Permission denied for parent item {parent_id}")
        else:
            raise ValueError(f"Unable to validate parent item {parent_id}: {e}")


async def check_duplicate_name(
    ctx: "Context",
    parent_id: int,
    item_name: str
) -> bool:
    """Check if item with given name already exists under parent.

    Args:
        ctx: MCP context with JAMA client
        parent_id: Parent item ID
        item_name: Name to check for duplicates

    Returns:
        True if duplicate exists, False otherwise
    """
    logger.debug(f"Checking duplicate name: parent_id={parent_id}, name='{item_name}'")

    try:
        # Call JAMA client directly to get children
        jama_client = ctx.request_context.lifespan_context["jama_client"]
        children = jama_client.get_item_children(item_id=str(parent_id))

        # Extract names from children
        existing_names = {
            child.get('fields', {}).get('name')
            for child in children
            if isinstance(child, dict) and child.get('fields', {}).get('name')
        }

        is_duplicate = item_name in existing_names
        if is_duplicate:
            logger.warning(f"Duplicate name found: '{item_name}' under parent {parent_id}")
        else:
            logger.debug(f"No duplicate found for: '{item_name}'")

        return is_duplicate
    except Exception as e:
        # If we can't check, err on the side of caution and allow creation
        logger.warning(f"Failed to check duplicate name: {e}")
        return False


# Will be implemented in Phase 6 (User Story 4 - T050)
# Dynamic field validation based on item type schemas
