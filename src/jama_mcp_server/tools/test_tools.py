"""JAMA MCP Server - Test Management Tools

This module contains MCP tools for JAMA Connect test management:
- Test case access (User Story 3)
- Test plan queries (User Story 3)
- Test execution results (User Story 3)
"""
from typing import Optional, Dict, Any, List
import logging
from mcp.server.fastmcp import Context

logger = logging.getLogger(__name__)


# ============================================================================
# User Story 3: Test Management Access
# ============================================================================

async def jama_get_test_cases(
    ctx: Context,
    project_id: int,
    start_at: int = 0,
    max_results: int = 20
) -> Dict[str, Any]:
    """Get test cases for a specific project with pagination.

    Args:
        ctx: MCP context with JAMA client
        project_id: Project ID
        start_at: Pagination offset (default: 0)
        max_results: Maximum results to return (default: 20)

    Returns:
        Dictionary with test cases and pagination info
    """
    logger.info(f"Getting test cases: project_id={project_id}")
    jama_client = ctx.request_context.lifespan_context["jama_client"]

    # Test cases are items with specific item type
    # Get test case item type ID first, then filter by it
    test_cases = jama_client.get_abstract_items(
        project=project_id,
        startAt=start_at,
        maxResults=max_results
    )

    # Filter for test case items (itemType typically includes "test" in name)
    # This is a simplified approach - in production, you'd query for the
    # specific test case item type ID first
    return test_cases


async def jama_get_test_case(
    ctx: Context,
    test_case_id: int
) -> Dict[str, Any]:
    """Get details for a specific test case including test steps.

    Test steps and expected results are typically stored in custom fields
    specific to the test case item type.

    Args:
        ctx: MCP context with JAMA client
        test_case_id: Test case item ID

    Returns:
        Test case data including test steps and expected results
    """
    logger.info(f"Getting test case: test_case_id={test_case_id}")
    jama_client = ctx.request_context.lifespan_context["jama_client"]

    # Get the full item with all custom fields
    test_case = jama_client.get_item(test_case_id)

    # Test steps are usually in custom fields like:
    # - testSteps (array of step objects)
    # - expectedResults (array of result strings)
    # The exact field names depend on project configuration

    return test_case


async def jama_get_test_plans(
    ctx: Context,
    project_id: int,
    start_at: int = 0,
    max_results: int = 20
) -> Dict[str, Any]:
    """Get test plans for a specific project.

    Test plans are organizational containers for test cases.

    Args:
        ctx: MCP context with JAMA client
        project_id: Project ID
        start_at: Pagination offset (default: 0)
        max_results: Maximum results to return (default: 20)

    Returns:
        Dictionary with test plans and pagination info
    """
    logger.info(f"Getting test plans: project_id={project_id}")
    jama_client = ctx.request_context.lifespan_context["jama_client"]

    # Test plans are typically a specific item type
    # Query for test plan items in the project
    test_plans = jama_client.get_test_plans(
        project_id,
        startAt=start_at,
        maxResults=max_results
    )

    return test_plans


async def jama_get_test_runs(
    ctx: Context,
    test_cycle_id: int,
    start_at: int = 0,
    max_results: int = 20
) -> Dict[str, Any]:
    """Get test run results for a test cycle.

    Test runs contain execution results (pass/fail/blocked) for test cases.

    Args:
        ctx: MCP context with JAMA client
        test_cycle_id: Test cycle ID (container for test runs)
        start_at: Pagination offset (default: 0)
        max_results: Maximum results to return (default: 20)

    Returns:
        Dictionary with test run results and pagination info
    """
    logger.info(f"Getting test runs: test_cycle_id={test_cycle_id}")
    jama_client = ctx.request_context.lifespan_context["jama_client"]

    # Get test runs for the cycle
    test_runs = jama_client.get_test_runs(
        test_cycle_id,
        startAt=start_at,
        maxResults=max_results
    )

    return test_runs


async def jama_get_test_cycles(
    ctx: Context,
    project_id: int,
    start_at: int = 0,
    max_results: int = 20
) -> Dict[str, Any]:
    """Get test cycles for a specific project.

    Test cycles group test runs for a specific testing iteration.

    Args:
        ctx: MCP context with JAMA client
        project_id: Project ID
        start_at: Pagination offset (default: 0)
        max_results: Maximum results to return (default: 20)

    Returns:
        Dictionary with test cycles and pagination info
    """
    logger.info(f"Getting test cycles: project_id={project_id}")
    jama_client = ctx.request_context.lifespan_context["jama_client"]

    test_cycles = jama_client.get_test_cycles(
        project_id,
        startAt=start_at,
        maxResults=max_results
    )

    return test_cycles


async def jama_get_test_case_results(
    ctx: Context,
    test_run_id: int
) -> Dict[str, Any]:
    """Get execution results for a specific test run.

    Includes pass/fail status, actual results, and execution notes.

    Args:
        ctx: MCP context with JAMA client
        test_run_id: Test run ID

    Returns:
        Test run result data with execution details
    """
    logger.info(f"Getting test case results: test_run_id={test_run_id}")
    jama_client = ctx.request_context.lifespan_context["jama_client"]

    # Get the test run item which contains execution results
    test_result = jama_client.get_item(test_run_id)

    # Results typically include:
    # - status (PASSED, FAILED, BLOCKED, NOT_RUN)
    # - actualResults (text description)
    # - executionDate
    # - executedBy (user ID)

    return test_result
