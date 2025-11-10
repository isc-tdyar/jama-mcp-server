"""JAMA Client Wrapper

Wrapper around py_jama_rest_client with added features:
- Token bucket rate limiting (9 req/sec)
- Proactive OAuth token refresh
- Standardized error handling
"""

import os
import time
import logging
from typing import Optional, Any, Dict
from datetime import datetime, timedelta

from py_jama_rest_client.client import JamaClient as BaseJamaClient
from .utils.rate_limit import RateLimiter
from .utils.errors import handle_http_error, AuthenticationError

logger = logging.getLogger(__name__)


class JamaClientWrapper:
    """Enhanced JAMA client with rate limiting and token management.

    Wraps py_jama_rest_client.client.JamaClient with additional features:
    - Rate limiting at 9 req/sec (token bucket algorithm)
    - Proactive OAuth token refresh (5 minutes before expiry)
    - Centralized error handling
    """

    # Token refresh threshold: refresh when less than 5 minutes remaining
    TOKEN_REFRESH_THRESHOLD = timedelta(minutes=5)

    def __init__(
        self,
        host_domain: str,
        credentials: tuple[str, str],
        oauth: bool = True,
        requests_per_second: float = 9.0,
        verify_ssl: bool = True
    ):
        """Initialize JAMA client wrapper.

        Args:
            host_domain: JAMA instance URL (e.g., https://jama.example.com)
            credentials: Tuple of (client_id, client_secret) for OAuth
            oauth: Whether to use OAuth authentication (default: True)
            requests_per_second: Rate limit (default: 9.0 req/sec)
            verify_ssl: Whether to verify SSL certificates (default: True)
        """
        self.host_domain = host_domain
        self.credentials = credentials
        self.oauth = oauth
        self.verify_ssl = verify_ssl

        # Initialize rate limiter
        self.rate_limiter = RateLimiter(requests_per_second=requests_per_second)
        logger.info(f"Initialized rate limiter at {requests_per_second} req/sec")

        # Initialize base client
        self._client = BaseJamaClient(
            host_domain=host_domain,
            credentials=credentials,
            oauth=oauth,
            verify=verify_ssl
        )
        logger.info(f"Initialized JAMA client for {host_domain} (SSL verify: {verify_ssl})")

        # OAuth token tracking
        self._token_expiry: Optional[datetime] = None
        self._update_token_expiry()

    def _update_token_expiry(self) -> None:
        """Update token expiry time based on OAuth response.

        Extracts expiry from the client's OAuth token response.
        Assumes token has 1 hour validity (JAMA default).
        """
        if self.oauth and hasattr(self._client, '_JamaClient__oauth_token'):
            # Token is typically valid for 1 hour
            self._token_expiry = datetime.now() + timedelta(hours=1)
            logger.info(f"OAuth token will expire at {self._token_expiry}")
        else:
            self._token_expiry = None

    def _ensure_valid_token(self) -> None:
        """Ensure OAuth token is valid, refreshing proactively if needed.

        Refreshes token if it will expire within TOKEN_REFRESH_THRESHOLD.
        """
        if not self.oauth or not self._token_expiry:
            return

        time_remaining = self._token_expiry - datetime.now()

        if time_remaining < self.TOKEN_REFRESH_THRESHOLD:
            logger.info(
                f"OAuth token expires in {time_remaining.total_seconds():.0f}s, "
                f"refreshing proactively..."
            )
            try:
                # Re-initialize OAuth token by creating new client
                self._client = BaseJamaClient(
                    host_domain=self.host_domain,
                    credentials=self.credentials,
                    oauth=True,
                    verify=self.verify_ssl
                )
                self._update_token_expiry()
                logger.info("OAuth token refreshed successfully")
            except Exception as e:
                logger.error(f"Failed to refresh OAuth token: {e}")
                raise AuthenticationError(
                    f"Failed to refresh OAuth token: {e}",
                    details={"error": str(e)}
                )

    def _make_request(self, method_name: str, *args, **kwargs) -> Any:
        """Make rate-limited request with token refresh.

        Args:
            method_name: Name of the client method to call
            *args: Positional arguments for the method
            **kwargs: Keyword arguments for the method

        Returns:
            Method return value

        Raises:
            JamaError: On API errors (with appropriate subclass)
        """
        # Acquire rate limit token (blocks if necessary)
        self.rate_limiter.acquire()

        # Ensure token is valid before request
        self._ensure_valid_token()

        # Get the method from the base client
        method = getattr(self._client, method_name)

        try:
            return method(*args, **kwargs)
        except Exception as e:
            # Handle HTTP errors with standardized error types
            error_message = str(e)
            if "401" in error_message or "Unauthorized" in error_message:
                raise handle_http_error(401, error_message)
            elif "403" in error_message or "Forbidden" in error_message:
                raise handle_http_error(403, error_message)
            elif "404" in error_message or "Not Found" in error_message:
                raise handle_http_error(404, error_message)
            elif "409" in error_message or "Conflict" in error_message:
                raise handle_http_error(409, error_message)
            elif "429" in error_message or "Too Many Requests" in error_message:
                raise handle_http_error(429, error_message)
            elif any(x in error_message for x in ["500", "502", "503", "504"]):
                # Extract status code
                for code in [500, 502, 503, 504]:
                    if str(code) in error_message:
                        raise handle_http_error(code, error_message)

            # Re-raise original exception if not HTTP error
            raise

    # Delegate common JAMA client methods with rate limiting

    def get_projects(self, *args, **kwargs):
        """Get all projects."""
        return self._make_request('get_projects', *args, **kwargs)

    def get_project(self, *args, **kwargs):
        """Get project by ID."""
        return self._make_request('get_project', *args, **kwargs)

    def get_items(self, *args, **kwargs):
        """Get items (with filters)."""
        return self._make_request('get_items', *args, **kwargs)

    def get_item(self, *args, **kwargs):
        """Get item by ID."""
        return self._make_request('get_item', *args, **kwargs)

    def post_item(self, *args, **kwargs):
        """Create new item."""
        return self._make_request('post_item', *args, **kwargs)

    def patch_item(self, *args, **kwargs):
        """Update item (partial)."""
        return self._make_request('patch_item', *args, **kwargs)

    def put_item(self, *args, **kwargs):
        """Update item (full replacement)."""
        return self._make_request('put_item', *args, **kwargs)

    def delete_item(self, *args, **kwargs):
        """Delete item (soft delete)."""
        return self._make_request('delete_item', *args, **kwargs)

    def get_relationships(self, *args, **kwargs):
        """Get relationships for item."""
        return self._make_request('get_relationships', *args, **kwargs)

    def post_relationship(self, *args, **kwargs):
        """Create new relationship."""
        return self._make_request('post_relationship', *args, **kwargs)

    def delete_relationship(self, *args, **kwargs):
        """Delete relationship."""
        return self._make_request('delete_relationship', *args, **kwargs)

    def get_attachments(self, *args, **kwargs):
        """Get attachments for item."""
        return self._make_request('get_attachments', *args, **kwargs)

    def post_attachment(self, *args, **kwargs):
        """Create attachment."""
        return self._make_request('post_attachment', *args, **kwargs)

    def get_attachment_file(self, *args, **kwargs):
        """Download attachment file content."""
        return self._make_request('get_attachment_file', *args, **kwargs)

    def delete_attachment(self, *args, **kwargs):
        """Delete attachment."""
        return self._make_request('delete_attachment', *args, **kwargs)

    def get_item_types(self, *args, **kwargs):
        """Get item types for project."""
        return self._make_request('get_item_types', *args, **kwargs)

    def get_pick_lists(self, *args, **kwargs):
        """Get pick lists (field options)."""
        return self._make_request('get_pick_lists', *args, **kwargs)

    def get_relationship_types(self, *args, **kwargs):
        """Get relationship types."""
        return self._make_request('get_relationship_types', *args, **kwargs)

    def get_baselines(self, *args, **kwargs):
        """Get baselines for project."""
        return self._make_request('get_baselines', *args, **kwargs)

    def get_baseline(self, *args, **kwargs):
        """Get baseline by ID."""
        return self._make_request('get_baseline', *args, **kwargs)

    def get_test_plans(self, *args, **kwargs):
        """Get test plans."""
        return self._make_request('get_test_plans', *args, **kwargs)

    def get_test_cycles(self, *args, **kwargs):
        """Get test cycles."""
        return self._make_request('get_test_cycles', *args, **kwargs)

    def get_test_runs(self, *args, **kwargs):
        """Get test runs."""
        return self._make_request('get_test_runs', *args, **kwargs)

    # Add __getattr__ to delegate any other methods
    def __getattr__(self, name: str) -> Any:
        """Delegate unknown methods to base client with rate limiting.

        Args:
            name: Method name

        Returns:
            Wrapped method
        """
        if name.startswith('_'):
            # Don't wrap private methods
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

        def wrapper(*args, **kwargs):
            return self._make_request(name, *args, **kwargs)

        return wrapper


class BearerTokenJamaClient:
    """JAMA client using pre-existing bearer token (no OAuth flow).

    This client accepts a bearer token directly instead of using OAuth
    client credentials flow. Useful when you already have a valid token.
    """

    def __init__(
        self,
        host_domain: str,
        bearer_token: str,
        requests_per_second: float = 9.0,
        verify_ssl: bool = True
    ):
        """Initialize JAMA client with bearer token.

        Args:
            host_domain: JAMA instance URL (e.g., https://jama.example.com)
            bearer_token: Pre-existing bearer token
            requests_per_second: Rate limit (default: 9.0 req/sec)
            verify_ssl: Whether to verify SSL certificates (default: True)
        """
        import requests

        self.host_domain = host_domain.rstrip('/') + '/rest/v1'
        self.bearer_token = bearer_token
        self.verify_ssl = verify_ssl
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {bearer_token}',
            'Content-Type': 'application/json'
        })

        # Initialize rate limiter
        self.rate_limiter = RateLimiter(requests_per_second=requests_per_second)
        logger.info(f"Initialized bearer token client for {host_domain} (SSL verify: {verify_ssl})")

    def _make_request(self, method: str, endpoint: str, **kwargs):
        """Make rate-limited HTTP request."""
        self.rate_limiter.acquire()

        url = f"{self.host_domain}/{endpoint.lstrip('/')}"
        kwargs['verify'] = self.verify_ssl

        response = self.session.request(method, url, **kwargs)
        response.raise_for_status()

        if response.content:
            return response.json()
        return None

    # Implement common JAMA API methods to match py-jama-rest-client interface

    def get_projects(self):
        """Get all projects."""
        return self._make_request('GET', 'projects')

    def get_project(self, project_id):
        """Get project by ID."""
        return self._make_request('GET', f'projects/{project_id}')

    def get_items(self, **params):
        """Get items with filters."""
        return self._make_request('GET', 'abstractitems', params=params)

    def get_abstract_items(self, **params):
        """Get abstract items (alias for get_items)."""
        return self.get_items(**params)

    def get_item(self, item_id):
        """Get item by ID."""
        return self._make_request('GET', f'items/{item_id}')

    def post_item(self, item_data):
        """Create new item."""
        return self._make_request('POST', 'items', json=item_data)

    def patch_item(self, item_id, patches):
        """Update item (partial)."""
        return self._make_request('PATCH', f'items/{item_id}', json=patches)

    def put_item(self, item_id, item_data):
        """Update item (full replacement)."""
        return self._make_request('PUT', f'items/{item_id}', json=item_data)

    def delete_item(self, item_id):
        """Delete item."""
        return self._make_request('DELETE', f'items/{item_id}')

    def get_relationships(self, item_id):
        """Get relationships for item."""
        return self._make_request('GET', f'items/{item_id}/relationships')

    def post_relationship(self, relationship_data):
        """Create new relationship."""
        return self._make_request('POST', 'relationships', json=relationship_data)

    def delete_relationship(self, relationship_id):
        """Delete relationship."""
        return self._make_request('DELETE', f'relationships/{relationship_id}')

    def get_item_types(self, project_id):
        """Get item types for project."""
        return self._make_request('GET', f'projects/{project_id}/itemtypes')

    def get_baselines(self, project_id):
        """Get baselines for project."""
        return self._make_request('GET', f'projects/{project_id}/baselines')

    def get_baseline(self, baseline_id):
        """Get baseline by ID."""
        return self._make_request('GET', f'baselines/{baseline_id}')
