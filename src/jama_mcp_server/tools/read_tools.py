"""JAMA MCP Server - Read Operations Tools

This module contains all read-only MCP tools for JAMA Connect:
- Search and retrieval (User Story 1)
- Relationship queries (User Story 2)
- Test management access (User Story 3)
- Project and baseline queries (User Story 7)
"""
from typing import Optional, Dict, Any, List
import logging
from mcp.server.fastmcp import Context

logger = logging.getLogger(__name__)


# ============================================================================
# User Story 1: Search and Retrieve Requirements (MVP)
# ============================================================================

async def jama_search_items(
    ctx: Context,
    query: str,
    project_id: Optional[int] = None,
    item_type_id: Optional[int] = None,
    start_at: int = 0,
    max_results: int = 20
) -> Dict[str, Any]:
    """Search for items in JAMA Connect using text query and filters.

    Args:
        ctx: MCP context with JAMA client
        query: Text search query
        project_id: Optional project ID to filter results
        item_type_id: Optional item type ID to filter results
        start_at: Pagination offset (default: 0)
        max_results: Maximum results to return (default: 20, max: 50)

    Returns:
        Dictionary with search results and pagination info:
        {
            "meta": {"pageInfo": {...}},
            "data": [...]
        }
    """
    logger.info(f"Searching items: query='{query}', project={project_id}, start_at={start_at}")
    jama_client = ctx.request_context.lifespan_context["jama_client"]

    # Build search parameters (get_abstract_items doesn't support pagination params)
    params = {
        "contains": [query]
    }

    if project_id:
        params["project"] = project_id
    if item_type_id:
        params["item_type"] = item_type_id

    # Note: py_jama_rest_client uses get_abstract_items for search
    # Pagination is handled internally by the library
    results = jama_client.get_abstract_items(**params)

    # Apply pagination manually on results
    if isinstance(results, dict) and "data" in results:
        data = results["data"]
        paginated_data = data[start_at:start_at + min(max_results, 50)]
        return {
            "meta": {
                "pageInfo": {
                    "startIndex": start_at,
                    "resultCount": len(paginated_data),
                    "totalResults": len(data)
                }
            },
            "data": paginated_data
        }

    return results


async def jama_get_item(
    ctx: Context,
    item_id: int
) -> Dict[str, Any]:
    """Get a specific JAMA item by ID with all fields and metadata.

    Args:
        ctx: MCP context with JAMA client
        item_id: Item ID to retrieve

    Returns:
        Item data including all custom fields
    """
    logger.info(f"Getting item: item_id={item_id}")
    jama_client = ctx.request_context.lifespan_context["jama_client"]

    item = jama_client.get_item(item_id)
    return item


async def jama_get_items_in_project(
    ctx: Context,
    project_id: int,
    start_at: int = 0,
    max_results: int = 20
) -> Dict[str, Any]:
    """Get all items in a specific project with pagination.

    Args:
        ctx: MCP context with JAMA client
        project_id: Project ID
        start_at: Pagination offset (default: 0)
        max_results: Maximum results to return (default: 20, max: 50)

    Returns:
        Dictionary with items and pagination info
    """
    logger.info(f"Getting items in project: project_id={project_id}, start_at={start_at}")
    jama_client = ctx.request_context.lifespan_context["jama_client"]

    items = jama_client.get_abstract_items(
        project=project_id,
        startAt=start_at,
        maxResults=min(max_results, 50)
    )
    return items


async def jama_get_item_history(
    ctx: Context,
    item_id: int,
    start_at: int = 0,
    max_results: int = 20
) -> Dict[str, Any]:
    """Get version history for a specific item.

    Args:
        ctx: MCP context with JAMA client
        item_id: Item ID
        start_at: Pagination offset (default: 0)
        max_results: Maximum results to return (default: 20)

    Returns:
        Dictionary with version history and pagination info
    """
    logger.info(f"Getting item history: item_id={item_id}")
    jama_client = ctx.request_context.lifespan_context["jama_client"]

    # py_jama_rest_client method for version history
    versions = jama_client.get_item_versions(
        item_id,
        startAt=start_at,
        maxResults=max_results
    )
    return versions


async def jama_get_projects(
    ctx: Context,
    start_at: int = 0,
    max_results: int = 20
) -> Dict[str, Any]:
    """Get all accessible JAMA projects with pagination.

    Args:
        ctx: MCP context with JAMA client
        start_at: Pagination offset (default: 0)
        max_results: Maximum results to return (default: 20)

    Returns:
        Dictionary with projects and pagination info
    """
    logger.info(f"Getting projects: start_at={start_at}, max_results={max_results}")
    jama_client = ctx.request_context.lifespan_context["jama_client"]

    projects = jama_client.get_projects(
        startAt=start_at,
        maxResults=max_results
    )
    return projects


async def jama_get_project(
    ctx: Context,
    project_id: int
) -> Dict[str, Any]:
    """Get details for a specific project by ID.

    Args:
        ctx: MCP context with JAMA client
        project_id: Project ID

    Returns:
        Project data
    """
    logger.info(f"Getting project: project_id={project_id}")
    jama_client = ctx.request_context.lifespan_context["jama_client"]

    project = jama_client.get_project(project_id)
    return project


async def jama_get_item_types(
    ctx: Context,
    project_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Get available item types (optionally filtered by project).

    Args:
        ctx: MCP context with JAMA client
        project_id: Optional project ID to get project-specific item types

    Returns:
        List of item type definitions
    """
    logger.info(f"Getting item types: project_id={project_id}")
    jama_client = ctx.request_context.lifespan_context["jama_client"]

    if project_id:
        item_types = jama_client.get_item_types(project_id)
    else:
        # Get all item types (global)
        item_types = jama_client.get_item_types()

    return item_types


async def jama_get_item_type_fields(
    ctx: Context,
    item_type_id: int
) -> List[Dict[str, Any]]:
    """Get field schema for a specific item type.

    Returns field definitions including custom fields for dynamic validation.

    Args:
        ctx: MCP context with JAMA client
        item_type_id: Item type ID

    Returns:
        List of field definitions with types and constraints
    """
    logger.info(f"Getting item type fields: item_type_id={item_type_id}")
    jama_client = ctx.request_context.lifespan_context["jama_client"]

    # Get pick list options and field metadata
    fields = jama_client.get_pick_lists(item_type_id)
    return fields


# ============================================================================
# User Story 2: Trace Relationships and Dependencies
# ============================================================================

async def jama_get_relationships(
    ctx: Context,
    item_id: int,
    start_at: int = 0,
    max_results: int = 20
) -> Dict[str, Any]:
    """Get all relationships for a specific item (upstream and downstream).

    Args:
        ctx: MCP context with JAMA client
        item_id: Item ID
        start_at: Pagination offset (default: 0)
        max_results: Maximum results to return (default: 20)

    Returns:
        Dictionary with relationships and pagination info
    """
    logger.info(f"Getting relationships: item_id={item_id}")
    jama_client = ctx.request_context.lifespan_context["jama_client"]

    relationships = jama_client.get_relationships(
        item_id,
        startAt=start_at,
        maxResults=max_results
    )
    return relationships


async def jama_get_upstream_relationships(
    ctx: Context,
    item_id: int,
    start_at: int = 0,
    max_results: int = 20
) -> Dict[str, Any]:
    """Get upstream (parent) relationships for an item.

    Args:
        ctx: MCP context with JAMA client
        item_id: Item ID
        start_at: Pagination offset (default: 0)
        max_results: Maximum results to return (default: 20)

    Returns:
        Dictionary with upstream relationships
    """
    logger.info(f"Getting upstream relationships: item_id={item_id}")
    jama_client = ctx.request_context.lifespan_context["jama_client"]

    relationships = jama_client.get_upstream_relationships(
        item_id,
        startAt=start_at,
        maxResults=max_results
    )
    return relationships


async def jama_get_downstream_relationships(
    ctx: Context,
    item_id: int,
    start_at: int = 0,
    max_results: int = 20
) -> Dict[str, Any]:
    """Get downstream (child) relationships for an item.

    Args:
        ctx: MCP context with JAMA client
        item_id: Item ID
        start_at: Pagination offset (default: 0)
        max_results: Maximum results to return (default: 20)

    Returns:
        Dictionary with downstream relationships
    """
    logger.info(f"Getting downstream relationships: item_id={item_id}")
    jama_client = ctx.request_context.lifespan_context["jama_client"]

    relationships = jama_client.get_downstream_relationships(
        item_id,
        startAt=start_at,
        maxResults=max_results
    )
    return relationships


async def jama_get_relationship_types(
    ctx: Context,
    project_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Get available relationship types.

    Args:
        ctx: MCP context with JAMA client
        project_id: Optional project ID to filter relationship types

    Returns:
        List of relationship type definitions
    """
    logger.info(f"Getting relationship types: project_id={project_id}")
    jama_client = ctx.request_context.lifespan_context["jama_client"]

    if project_id:
        rel_types = jama_client.get_relationship_types(project_id)
    else:
        rel_types = jama_client.get_relationship_types()

    return rel_types


# ============================================================================
# User Story 7: Project and Baseline Management
# ============================================================================

async def jama_get_baselines(
    ctx: Context,
    project_id: int,
    start_at: int = 0,
    max_results: int = 20
) -> Dict[str, Any]:
    """Get baselines for a specific project.

    Args:
        ctx: MCP context with JAMA client
        project_id: Project ID
        start_at: Pagination offset (default: 0)
        max_results: Maximum results to return (default: 20)

    Returns:
        Dictionary with baselines and pagination info
    """
    logger.info(f"Getting baselines: project_id={project_id}")
    jama_client = ctx.request_context.lifespan_context["jama_client"]

    baselines = jama_client.get_baselines(
        project_id,
        startAt=start_at,
        maxResults=max_results
    )
    return baselines


async def jama_get_baseline(
    ctx: Context,
    baseline_id: int
) -> Dict[str, Any]:
    """Get baseline metadata by ID.

    Args:
        ctx: MCP context with JAMA client
        baseline_id: Baseline ID

    Returns:
        Baseline data
    """
    logger.info(f"Getting baseline: baseline_id={baseline_id}")
    jama_client = ctx.request_context.lifespan_context["jama_client"]

    baseline = jama_client.get_baseline(baseline_id)
    return baseline


async def jama_get_baseline_items(
    ctx: Context,
    baseline_id: int,
    start_at: int = 0,
    max_results: int = 20
) -> Dict[str, Any]:
    """Get items in a baseline (frozen snapshot).

    Args:
        ctx: MCP context with JAMA client
        baseline_id: Baseline ID
        start_at: Pagination offset (default: 0)
        max_results: Maximum results to return (default: 20)

    Returns:
        Dictionary with baseline items and pagination info
    """
    logger.info(f"Getting baseline items: baseline_id={baseline_id}")
    jama_client = ctx.request_context.lifespan_context["jama_client"]

    items = jama_client.get_baseline_items(
        baseline_id,
        startAt=start_at,
        maxResults=max_results
    )
    return items
