import os
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
import logging

from mcp.server.fastmcp import FastMCP, Context
from .auth import get_jama_credentials, get_bearer_token, CredentialsError
from .tools import read_tools, test_tools, write_tools

# Configure basic logging FIRST
logging.basicConfig(level=logging.INFO, format='%(asctime)s - SERVER - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Check if we need the real client or can use a mock
MOCK_MODE = os.environ.get("JAMA_MOCK_MODE", "false").lower() == "true"

if MOCK_MODE:
    from .mock_client import MockJamaClient as JamaClient
    logger.info("Using MockJamaClient due to JAMA_MOCK_MODE=true")
else:
    try:
        from .client import JamaClientWrapper as JamaClient  # Use our wrapper with rate limiting
        logger.info("Using JamaClientWrapper with rate limiting and token refresh")
    except ImportError:
        logger.error("Failed to import JamaClientWrapper. Check installation.")
        raise

@asynccontextmanager
async def jama_lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """
    Manages the JamaClient lifecycle, retrieving credentials using get_jama_credentials
    and instantiating the JamaClient.
    """
    if MOCK_MODE:
        logger.info("Jama Mock Mode enabled. Skipping real authentication.")
        try:
            mock_client = JamaClient() # Instantiate the mock client
            yield {"jama_client": mock_client}
        except Exception as e:
             logger.error(f"Failed to initialize MockJamaClient: {e}")
             raise
        finally:
             logger.info("Jama mock lifespan context manager exiting.")
        return # Exit the function here for mock mode

    # --- Real Authentication Logic (only runs if not MOCK_MODE) ---
    jama_url = os.environ.get("JAMA_URL")
    if not jama_url:
        logger.error("JAMA_URL environment variable not set. Cannot connect to Jama.")
        # Let the lifespan fail, preventing server start without URL
        raise ValueError("JAMA_URL environment variable is required.")

    # Get SSL verification setting (default to True for security)
    verify_ssl = os.environ.get("JAMA_VERIFY_SSL", "true").lower() in ("true", "1", "yes")
    logger.info(f"SSL verification {'enabled' if verify_ssl else 'disabled'}")

    jama_client = None
    try:
        # Check for bearer token first
        bearer_token = get_bearer_token()

        if bearer_token:
            # Use bearer token authentication (no OAuth flow)
            from .client import BearerTokenJamaClient
            logger.info(f"Using bearer token authentication to Jama at {jama_url}")
            jama_client = BearerTokenJamaClient(
                host_domain=jama_url,
                bearer_token=bearer_token,
                verify_ssl=verify_ssl
            )
            logger.info("Successfully configured BearerTokenJamaClient.")
        else:
            # Fall back to OAuth client credentials flow
            logger.info("Attempting to retrieve OAuth credentials...")
            client_id, client_secret = get_jama_credentials() # This handles AWS/Env Var logic and raises errors
            logger.info("Successfully retrieved OAuth credentials.")

            # Instantiate the OAuth client
            logger.info(f"Attempting OAuth authentication to Jama at {jama_url}")
            jama_client = JamaClient(host_domain=jama_url, credentials=(client_id, client_secret), oauth=True, verify_ssl=verify_ssl)
            logger.info("Successfully configured JamaClient with OAuth.")

        yield {"jama_client": jama_client}

    except CredentialsError as e: # Catch specific credential errors from auth.py
        logger.error(f"Failed to obtain Jama credentials: {e}")
        raise # Re-raise to prevent server start
    except Exception as e: # Catch other potential errors (e.g., JamaClient init)
        logger.error(f"Failed during JamaClient initialization or credential retrieval: {e}")
        # Re-raise the exception to prevent the server from starting incorrectly
        raise
    finally:
        # No explicit cleanup needed for JamaClient based on its usage pattern
        logger.info("Jama lifespan context manager exiting.")


# Instantiate the FastMCP server with the lifespan manager
mcp = FastMCP(
    "Jama Connect Server",
    lifespan=jama_lifespan,
)

# --- Tool Implementations ---

@mcp.tool()
async def get_jama_projects(ctx: Context) -> list[dict]:
    """
    Retrieves a list of projects from Jama Connect.

    Returns:
        A list of dictionaries representing projects.

    Raises:
        APIException: If an error occurs during the Jama API call.
    """
    logger.info("Executing get_jama_projects tool")
    jama_client: JamaClient = ctx.request_context.lifespan_context["jama_client"]
    # Let exceptions from the client propagate
    projects = jama_client.get_projects()
    return projects

@mcp.tool()
async def get_jama_item(item_id: str, ctx: Context) -> dict:
    """
    Retrieves details for a specific item from Jama Connect by its ID.

    Args:
        item_id: The ID (as a string) of the Jama item to retrieve.

    Returns:
        A dictionary representing the item.

    Raises:
        APIException: If the item is not found or an error occurs.
    """
    logger.info(f"Executing get_jama_item tool for item_id: {item_id}")
    jama_client: JamaClient = ctx.request_context.lifespan_context["jama_client"]
    item = jama_client.get_item(item_id)
    # Let the client raise ResourceNotFoundException if applicable
    if not item and MOCK_MODE: # Handle mock case explicitly if needed
        raise ValueError(f"Mock Item with ID {item_id} not found.")
    return item

@mcp.tool()
async def get_jama_project_items(project_id: str, ctx: Context) -> list[dict]:
    """
    Retrieves a list of items for a specific project from Jama Connect.

    Args:
        project_id: The ID (as a string) of the Jama project.

    Returns:
        A list of dictionaries representing items in the project.

    Raises:
        APIException: If an error occurs during the Jama API call.
    """
    logger.info(f"Executing get_jama_project_items tool for project_id: {project_id}")
    jama_client: JamaClient = ctx.request_context.lifespan_context["jama_client"]
    items = jama_client.get_items(project_id=project_id)
    return items if items else []

@mcp.tool()
async def get_jama_item_children(item_id: str, ctx: Context) -> list[dict]:
    """
    Retrieves child items for a specific Jama item.

    Args:
        item_id: The ID (as a string) of the parent Jama item.

    Returns:
        A list of dictionaries representing child items.

    Raises:
        APIException: If an error occurs during the Jama API call.
    """
    logger.info(f"Executing get_jama_item_children tool for parent_id: {item_id}")
    jama_client: JamaClient = ctx.request_context.lifespan_context["jama_client"]
    children = jama_client.get_item_children(item_id=item_id)
    return children if children else []

@mcp.tool()
async def get_jama_relationships(project_id: str, ctx: Context) -> list[dict]:
    """
    Retrieves all relationships within a specific Jama project.

    Args:
        project_id: The ID (as a string) of the Jama project.

    Returns:
        A list of dictionaries representing relationships.

    Raises:
        APIException: If an error occurs during the Jama API call.
    """
    logger.info(f"Executing get_jama_relationships tool for project_id: {project_id}")
    jama_client: JamaClient = ctx.request_context.lifespan_context["jama_client"]
    relationships = jama_client.get_relationships(project_id=project_id)
    return relationships if relationships else []

@mcp.tool()
async def get_jama_relationship(relationship_id: str, ctx: Context) -> dict:
    """
    Retrieves details for a specific relationship by its ID.

    Args:
        relationship_id: The ID (as a string) of the relationship.

    Returns:
        A dictionary representing the relationship.

    Raises:
        APIException: If the relationship is not found or an error occurs.
    """
    logger.info(f"Executing get_jama_relationship tool for relationship_id: {relationship_id}")
    jama_client: JamaClient = ctx.request_context.lifespan_context["jama_client"]
    relationship = jama_client.get_relationship(relationship_id=relationship_id)
    # Let py-jama-rest-client raise ResourceNotFoundException if applicable
    if not relationship and MOCK_MODE: # Handle mock case explicitly if needed
         raise ValueError(f"Mock Relationship with ID {relationship_id} not found.")
    return relationship

@mcp.tool()
async def get_jama_item_upstream_relationships(item_id: str, ctx: Context) -> list[dict]:
    """
    Retrieves upstream relationships for a specific Jama item.

    Args:
        item_id: The ID (as a string) of the Jama item.

    Returns:
        A list of dictionaries representing upstream relationships.

    Raises:
        APIException: If an error occurs during the Jama API call.
    """
    logger.info(f"Executing get_jama_item_upstream_relationships tool for item_id: {item_id}")
    jama_client: JamaClient = ctx.request_context.lifespan_context["jama_client"]
    relationships = jama_client.get_items_upstream_relationships(item_id=item_id)
    return relationships if relationships else []

@mcp.tool()
async def get_jama_item_downstream_relationships(item_id: str, ctx: Context) -> list[dict]:
    """
    Retrieves downstream relationships for a specific Jama item.

    Args:
        item_id: The ID (as a string) of the Jama item.

    Returns:
        A list of dictionaries representing downstream relationships.

    Raises:
        APIException: If an error occurs during the Jama API call.
    """
    logger.info(f"Executing get_jama_item_downstream_relationships tool for item_id: {item_id}")
    jama_client: JamaClient = ctx.request_context.lifespan_context["jama_client"]
    relationships = jama_client.get_items_downstream_relationships(item_id=item_id)
    return relationships if relationships else []

@mcp.tool()
async def get_jama_item_upstream_related(item_id: str, ctx: Context) -> list[dict]:
    """
    Retrieves upstream related items for a specific Jama item.

    Args:
        item_id: The ID (as a string) of the Jama item.

    Returns:
        A list of dictionaries representing upstream related items.

    Raises:
        APIException: If an error occurs during the Jama API call.
    """
    logger.info(f"Executing get_jama_item_upstream_related tool for item_id: {item_id}")
    jama_client: JamaClient = ctx.request_context.lifespan_context["jama_client"]
    items = jama_client.get_items_upstream_related(item_id=item_id)
    return items if items else []

@mcp.tool()
async def get_jama_item_downstream_related(item_id: str, ctx: Context) -> list[dict]:
    """
    Retrieves downstream related items for a specific Jama item.

    Args:
        item_id: The ID (as a string) of the Jama item.

    Returns:
        A list of dictionaries representing downstream related items.

    Raises:
        APIException: If an error occurs during the Jama API call.
    """
    logger.info(f"Executing get_jama_item_downstream_related tool for item_id: {item_id}")
    jama_client: JamaClient = ctx.request_context.lifespan_context["jama_client"]
    items = jama_client.get_items_downstream_related(item_id=item_id)
    return items if items else []

@mcp.tool()
async def get_jama_item_types(ctx: Context) -> list[dict]:
    """
    Retrieves all item types from Jama Connect.

    Returns:
        A list of dictionaries representing item types.

    Raises:
        APIException: If an error occurs during the Jama API call.
    """
    logger.info("Executing get_jama_item_types tool")
    jama_client: JamaClient = ctx.request_context.lifespan_context["jama_client"]
    item_types = jama_client.get_item_types()
    return item_types if item_types else []

@mcp.tool()
async def get_jama_item_type(item_type_id: str, ctx: Context) -> dict:
    """
    Retrieves details for a specific item type by its ID.

    Args:
        item_type_id: The ID (as a string) of the item type.

    Returns:
        A dictionary representing the item type.

    Raises:
        APIException: If the item type is not found or an error occurs.
    """
    logger.info(f"Executing get_jama_item_type tool for item_type_id: {item_type_id}")
    jama_client: JamaClient = ctx.request_context.lifespan_context["jama_client"]
    item_type = jama_client.get_item_type(item_type_id=item_type_id)
    if not item_type and MOCK_MODE:
         raise ValueError(f"Mock Item type with ID {item_type_id} not found.")
    return item_type

@mcp.tool()
async def get_jama_pick_lists(ctx: Context) -> list[dict]:
    """
    Retrieves all pick lists from Jama Connect.

    Returns:
        A list of dictionaries representing pick lists.

    Raises:
        APIException: If an error occurs during the Jama API call.
    """
    logger.info("Executing get_jama_pick_lists tool")
    jama_client: JamaClient = ctx.request_context.lifespan_context["jama_client"]
    pick_lists = jama_client.get_pick_lists()
    return pick_lists if pick_lists else []

@mcp.tool()
async def get_jama_pick_list(pick_list_id: str, ctx: Context) -> dict:
    """
    Retrieves details for a specific pick list by its ID.

    Args:
        pick_list_id: The ID (as a string) of the pick list.

    Returns:
        A dictionary representing the pick list.

    Raises:
        APIException: If the pick list is not found or an error occurs.
    """
    logger.info(f"Executing get_jama_pick_list tool for pick_list_id: {pick_list_id}")
    jama_client: JamaClient = ctx.request_context.lifespan_context["jama_client"]
    pick_list = jama_client.get_pick_list(pick_list_id=pick_list_id)
    if not pick_list and MOCK_MODE:
         raise ValueError(f"Mock Pick list with ID {pick_list_id} not found.")
    return pick_list

@mcp.tool()
async def get_jama_pick_list_options(pick_list_id: str, ctx: Context) -> list[dict]:
    """
    Retrieves options for a specific pick list.

    Args:
        pick_list_id: The ID (as a string) of the pick list.

    Returns:
        A list of dictionaries representing pick list options.

    Raises:
        APIException: If an error occurs during the Jama API call.
    """
    logger.info(f"Executing get_jama_pick_list_options tool for pick_list_id: {pick_list_id}")
    jama_client: JamaClient = ctx.request_context.lifespan_context["jama_client"]
    options = jama_client.get_pick_list_options(pick_list_id=pick_list_id)
    return options if options else []

@mcp.tool()
async def get_jama_pick_list_option(pick_list_option_id: str, ctx: Context) -> dict:
    """
    Retrieves details for a specific pick list option by its ID.

    Args:
        pick_list_option_id: The ID (as a string) of the pick list option.

    Returns:
        A dictionary representing the pick list option.

    Raises:
        APIException: If the pick list option is not found or an error occurs.
    """
    logger.info(f"Executing get_jama_pick_list_option tool for pick_list_option_id: {pick_list_option_id}")
    jama_client: JamaClient = ctx.request_context.lifespan_context["jama_client"]
    option = jama_client.get_pick_list_option(pick_list_option_id=pick_list_option_id)
    if not option and MOCK_MODE:
         raise ValueError(f"Mock Pick list option with ID {pick_list_option_id} not found.")
    return option

@mcp.tool()
async def get_jama_tags(project_id: str, ctx: Context) -> list[dict]:
    """
    Retrieves all tags for a specific project.

    Args:
        project_id: The ID (as a string) of the Jama project.

    Returns:
        A list of dictionaries representing tags.

    Raises:
        APIException: If an error occurs during the Jama API call.
    """
    logger.info(f"Executing get_jama_tags tool for project_id: {project_id}")
    jama_client: JamaClient = ctx.request_context.lifespan_context["jama_client"]
    tags = jama_client.get_tags(project=project_id) # Param name is 'project' in client
    return tags if tags else []

@mcp.tool()
async def get_jama_tagged_items(tag_id: str, ctx: Context) -> list[dict]:
    """
    Retrieves items associated with a specific tag.

    Args:
        tag_id: The ID (as a string) of the tag.

    Returns:
        A list of dictionaries representing items associated with the tag.

    Raises:
        APIException: If an error occurs during the Jama API call.
    """
    logger.info(f"Executing get_jama_tagged_items tool for tag_id: {tag_id}")
    jama_client: JamaClient = ctx.request_context.lifespan_context["jama_client"]
    items = jama_client.get_tagged_items(tag_id=tag_id)
    return items if items else []

@mcp.tool()
async def get_jama_test_cycle(test_cycle_id: str, ctx: Context) -> dict:
    """
    Retrieves details for a specific test cycle by its ID.

    Args:
        test_cycle_id: The ID (as a string) of the test cycle.

    Returns:
        A dictionary representing the test cycle.

    Raises:
        APIException: If the test cycle is not found or an error occurs.
    """
    logger.info(f"Executing get_jama_test_cycle tool for test_cycle_id: {test_cycle_id}")
    jama_client: JamaClient = ctx.request_context.lifespan_context["jama_client"]
    cycle = jama_client.get_test_cycle(test_cycle_id=test_cycle_id)
    if not cycle and MOCK_MODE:
         raise ValueError(f"Mock Test cycle with ID {test_cycle_id} not found.")
    return cycle

@mcp.tool()
async def get_jama_test_runs(test_cycle_id: str, ctx: Context) -> list[dict]:
    """
    Retrieves test runs associated with a specific test cycle.

    Args:
        test_cycle_id: The ID (as a string) of the test cycle.

    Returns:
        A list of dictionaries representing test runs.

    Raises:
        APIException: If an error occurs during the Jama API call.
    """
    logger.info(f"Executing get_jama_test_runs tool for test_cycle_id: {test_cycle_id}")
    jama_client: JamaClient = ctx.request_context.lifespan_context["jama_client"]
    runs = jama_client.get_testruns(test_cycle_id=test_cycle_id)
    return runs if runs else []



@mcp.tool()
async def test_jama_connection(ctx: Context) -> dict:
    """
    Tests the connection and authentication to the Jama Connect API.
    Attempts to fetch available API endpoints as a lightweight check.

    Returns:
        A dictionary containing the result of the get_available_endpoints call.

    Raises:
        APIException: If the connection test fails.
        ValueError: If the JamaClient is not found in the context.
    """
    logger.info("Executing test_jama_connection tool")
    jama_client: JamaClient = ctx.request_context.lifespan_context.get("jama_client")
    if not jama_client:
        raise ValueError("JamaClient not found in context for connection test.")

    # Attempt a simple API call to verify connection further
    # Let any exceptions propagate
    endpoints = jama_client.get_available_endpoints()
    return endpoints # Return the actual result or let exception indicate failure


# ============================================================================
# User Story 1: Search and Retrieve (MVP) - New Tools
# ============================================================================

@mcp.tool()
async def jama_search_items(
    query: str,
    ctx: Context,
    project_id: int | None = None,
    item_type_id: int | None = None,
    start_at: int = 0,
    max_results: int = 20
) -> dict:
    """Search for items in JAMA Connect using text query with optional filters.

    Args:
        query: Text search query
        ctx: MCP context
        project_id: Optional project ID to filter results
        item_type_id: Optional item type ID to filter results
        start_at: Pagination offset (default: 0)
        max_results: Maximum results (default: 20, max: 50)

    Returns:
        Search results with pagination info
    """
    return await read_tools.jama_search_items(
        ctx, query, project_id, item_type_id, start_at, max_results
    )


@mcp.tool()
async def jama_get_item_history(
    item_id: int,
    ctx: Context,
    start_at: int = 0,
    max_results: int = 20
) -> dict:
    """Get version history for a specific JAMA item.

    Args:
        item_id: Item ID
        ctx: MCP context
        start_at: Pagination offset (default: 0)
        max_results: Maximum results (default: 20)

    Returns:
        Version history with pagination info
    """
    return await read_tools.jama_get_item_history(ctx, item_id, start_at, max_results)


@mcp.tool()
async def jama_get_project(project_id: int, ctx: Context) -> dict:
    """Get details for a specific JAMA project by ID.

    Args:
        project_id: Project ID
        ctx: MCP context

    Returns:
        Project data
    """
    return await read_tools.jama_get_project(ctx, project_id)


@mcp.tool()
async def jama_get_item_types(ctx: Context, project_id: int | None = None) -> list[dict]:
    """Get available item types, optionally filtered by project.

    Args:
        ctx: MCP context
        project_id: Optional project ID

    Returns:
        List of item type definitions
    """
    return await read_tools.jama_get_item_types(ctx, project_id)


@mcp.tool()
async def jama_get_item_type_fields(item_type_id: int, ctx: Context) -> list[dict]:
    """Get field schema for a specific item type including custom fields.

    Args:
        item_type_id: Item type ID
        ctx: MCP context

    Returns:
        List of field definitions
    """
    return await read_tools.jama_get_item_type_fields(ctx, item_type_id)


# ============================================================================
# User Story 2: Trace Relationships and Dependencies
# ============================================================================

@mcp.tool()
async def jama_get_relationships(
    item_id: int,
    ctx: Context,
    start_at: int = 0,
    max_results: int = 20
) -> dict:
    """Get all relationships for a specific item (upstream and downstream).

    Args:
        item_id: Item ID
        ctx: MCP context
        start_at: Pagination offset (default: 0)
        max_results: Maximum results (default: 20)

    Returns:
        Relationships with pagination info
    """
    return await read_tools.jama_get_relationships(ctx, item_id, start_at, max_results)


@mcp.tool()
async def jama_get_upstream_relationships(
    item_id: int,
    ctx: Context,
    start_at: int = 0,
    max_results: int = 20
) -> dict:
    """Get upstream (parent) relationships for an item.

    Args:
        item_id: Item ID
        ctx: MCP context
        start_at: Pagination offset (default: 0)
        max_results: Maximum results (default: 20)

    Returns:
        Upstream relationships with pagination info
    """
    return await read_tools.jama_get_upstream_relationships(ctx, item_id, start_at, max_results)


@mcp.tool()
async def jama_get_downstream_relationships(
    item_id: int,
    ctx: Context,
    start_at: int = 0,
    max_results: int = 20
) -> dict:
    """Get downstream (child) relationships for an item.

    Args:
        item_id: Item ID
        ctx: MCP context
        start_at: Pagination offset (default: 0)
        max_results: Maximum results (default: 20)

    Returns:
        Downstream relationships with pagination info
    """
    return await read_tools.jama_get_downstream_relationships(ctx, item_id, start_at, max_results)


@mcp.tool()
async def jama_get_relationship_types(ctx: Context, project_id: int | None = None) -> list[dict]:
    """Get available relationship types.

    Args:
        ctx: MCP context
        project_id: Optional project ID to filter relationship types

    Returns:
        List of relationship type definitions
    """
    return await read_tools.jama_get_relationship_types(ctx, project_id)


# ============================================================================
# User Story 7: Project and Baseline Management
# ============================================================================

@mcp.tool()
async def jama_get_baselines(
    project_id: int,
    ctx: Context,
    start_at: int = 0,
    max_results: int = 20
) -> dict:
    """Get baselines for a specific project.

    Args:
        project_id: Project ID
        ctx: MCP context
        start_at: Pagination offset (default: 0)
        max_results: Maximum results (default: 20)

    Returns:
        Baselines with pagination info
    """
    return await read_tools.jama_get_baselines(ctx, project_id, start_at, max_results)


@mcp.tool()
async def jama_get_baseline(baseline_id: int, ctx: Context) -> dict:
    """Get baseline metadata by ID.

    Args:
        baseline_id: Baseline ID
        ctx: MCP context

    Returns:
        Baseline data
    """
    return await read_tools.jama_get_baseline(ctx, baseline_id)


@mcp.tool()
async def jama_get_baseline_items(
    baseline_id: int,
    ctx: Context,
    start_at: int = 0,
    max_results: int = 20
) -> dict:
    """Get items in a baseline (frozen snapshot).

    Args:
        baseline_id: Baseline ID
        ctx: MCP context
        start_at: Pagination offset (default: 0)
        max_results: Maximum results (default: 20)

    Returns:
        Baseline items with pagination info
    """
    return await read_tools.jama_get_baseline_items(ctx, baseline_id, start_at, max_results)


# ============================================================================
# User Story 3: Test Management Access
# ============================================================================

@mcp.tool()
async def jama_get_test_cases(
    project_id: int,
    ctx: Context,
    start_at: int = 0,
    max_results: int = 20
) -> dict:
    """Get test cases for a specific project.

    Args:
        project_id: Project ID
        ctx: MCP context
        start_at: Pagination offset (default: 0)
        max_results: Maximum results (default: 20)

    Returns:
        Test cases with pagination info
    """
    return await test_tools.jama_get_test_cases(ctx, project_id, start_at, max_results)


@mcp.tool()
async def jama_get_test_case(test_case_id: int, ctx: Context) -> dict:
    """Get details for a specific test case including test steps.

    Args:
        test_case_id: Test case item ID
        ctx: MCP context

    Returns:
        Test case data with steps and expected results
    """
    return await test_tools.jama_get_test_case(ctx, test_case_id)


@mcp.tool()
async def jama_get_test_plans(
    project_id: int,
    ctx: Context,
    start_at: int = 0,
    max_results: int = 20
) -> dict:
    """Get test plans for a specific project.

    Args:
        project_id: Project ID
        ctx: MCP context
        start_at: Pagination offset (default: 0)
        max_results: Maximum results (default: 20)

    Returns:
        Test plans with pagination info
    """
    return await test_tools.jama_get_test_plans(ctx, project_id, start_at, max_results)


@mcp.tool()
async def jama_get_test_runs(
    test_cycle_id: int,
    ctx: Context,
    start_at: int = 0,
    max_results: int = 20
) -> dict:
    """Get test run results for a test cycle.

    Args:
        test_cycle_id: Test cycle ID
        ctx: MCP context
        start_at: Pagination offset (default: 0)
        max_results: Maximum results (default: 20)

    Returns:
        Test run results with pagination info
    """
    return await test_tools.jama_get_test_runs(ctx, test_cycle_id, start_at, max_results)


@mcp.tool()
async def jama_get_test_cycles(
    project_id: int,
    ctx: Context,
    start_at: int = 0,
    max_results: int = 20
) -> dict:
    """Get test cycles for a specific project.

    Args:
        project_id: Project ID
        ctx: MCP context
        start_at: Pagination offset (default: 0)
        max_results: Maximum results (default: 20)

    Returns:
        Test cycles with pagination info
    """
    return await test_tools.jama_get_test_cycles(ctx, project_id, start_at, max_results)


@mcp.tool()
async def jama_get_test_case_results(test_run_id: int, ctx: Context) -> dict:
    """Get execution results for a specific test run.

    Args:
        test_run_id: Test run ID
        ctx: MCP context

    Returns:
        Test run result data with execution details
    """
    return await test_tools.jama_get_test_case_results(ctx, test_run_id)


# ============================================================================
# User Story 4: Create and Update Requirements (Write Operations)
# ============================================================================

@mcp.tool()
async def jama_create_item(
    project: int,
    item_type: int,
    name: str,
    ctx: Context,
    parent: int | None = None,
    description: str | None = None,
    **custom_fields
) -> dict:
    """Create a new JAMA item with validation.

    Args:
        project: Project ID
        item_type: Item type ID
        name: Item name/title (required)
        ctx: MCP context
        parent: Parent item ID for hierarchy (optional)
        description: Item description (optional)
        **custom_fields: Additional custom fields

    Returns:
        Created item data with ID
    """
    return await write_tools.jama_create_item(
        ctx, project, item_type, parent, name, description, **custom_fields
    )


@mcp.tool()
async def jama_update_item(
    item_id: int,
    ctx: Context,
    fields: dict,
    **additional_fields
) -> dict:
    """Update an existing JAMA item using JSON Patch (RFC 6902).

    Args:
        item_id: Item ID to update
        ctx: MCP context
        fields: Dictionary of fields to update
        **additional_fields: Additional fields as keyword arguments

    Returns:
        Updated item data

    Example:
        await jama_update_item(
            item_id=29181,
            ctx=context,
            fields={"name": "Updated Name", "description": "<p>Updated</p>"}
        )
    """
    return await write_tools.jama_update_item(ctx, item_id, fields, **additional_fields)


@mcp.tool()
async def jama_delete_item(item_id: int, ctx: Context) -> dict:
    """Delete a JAMA item (soft delete).

    Args:
        item_id: Item ID to delete
        ctx: MCP context

    Returns:
        Deletion confirmation
    """
    return await write_tools.jama_delete_item(ctx, item_id)


@mcp.tool()
async def jama_batch_create_items(items: list[dict], ctx: Context) -> dict:
    """Create multiple JAMA items in batch.

    Args:
        items: List of item data dictionaries
        ctx: MCP context

    Returns:
        Batch creation results
    """
    return await write_tools.jama_batch_create_items(ctx, items)


@mcp.tool()
async def jama_validate_item_fields(
    item_type_id: int,
    fields: dict,
    ctx: Context
) -> dict:
    """Validate item fields against item type schema.

    Args:
        item_type_id: Item type ID
        fields: Fields to validate
        ctx: MCP context

    Returns:
        Validation results
    """
    return await write_tools.jama_validate_item_fields(ctx, item_type_id, fields)


def main():
    """Entry point for the jama-mcp-server script."""
    logger.info("Starting Jama MCP server...")

    if not MOCK_MODE and not os.environ.get("JAMA_URL"):
        logger.error("JAMA_URL environment variable is not set when not in MOCK_MODE.")
        print("\nERROR: JAMA_URL environment variable is not set.")
        print("Please set JAMA_URL and OAuth authentication variables (JAMA_CLIENT_ID, JAMA_CLIENT_SECRET),")
        print("or run in mock mode by setting JAMA_MOCK_MODE=true.")
        exit(1) # Exit if essential config is missing for non-mock mode

    # Run the MCP server (uses uvicorn defaults)
    mcp.run()

if __name__ == "__main__":
    # This allows running the server directly with `python -m jama_mcp_server.server`
    main()
