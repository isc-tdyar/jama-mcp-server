"""JAMA API Rate Limiting Utilities

Token bucket rate limiter to stay under JAMA's 10 requests/second limit.
Configured for 9 req/sec to provide safety margin.
"""

import time
import threading
from typing import Optional


class RateLimiter:
    """Thread-safe token bucket rate limiter.

    Ensures API requests stay under JAMA's rate limits (10 req/sec).
    Configured for 9 req/sec to provide safety margin.
    """

    def __init__(self, requests_per_second: float = 9.0):
        """Initialize rate limiter.

        Args:
            requests_per_second: Maximum requests allowed per second (default: 9.0)
        """
        self.rate = requests_per_second
        self.capacity = requests_per_second  # Maximum tokens
        self.tokens = requests_per_second    # Current tokens available
        self.last_update = time.time()
        self.lock = threading.Lock()

    def _refill_tokens(self) -> None:
        """Refill tokens based on elapsed time since last update."""
        now = time.time()
        elapsed = now - self.last_update

        # Add tokens based on elapsed time
        new_tokens = elapsed * self.rate
        self.tokens = min(self.capacity, self.tokens + new_tokens)
        self.last_update = now

    def acquire(self, tokens: int = 1) -> None:
        """Acquire tokens from the bucket, blocking if necessary.

        Args:
            tokens: Number of tokens to acquire (default: 1)
        """
        with self.lock:
            while True:
                self._refill_tokens()

                if self.tokens >= tokens:
                    # Enough tokens available
                    self.tokens -= tokens
                    return

                # Calculate wait time needed for enough tokens
                tokens_needed = tokens - self.tokens
                wait_time = tokens_needed / self.rate

                # Release lock while waiting to avoid blocking other threads
                self.lock.release()
                time.sleep(wait_time)
                self.lock.acquire()

    def try_acquire(self, tokens: int = 1) -> bool:
        """Try to acquire tokens without blocking.

        Args:
            tokens: Number of tokens to acquire (default: 1)

        Returns:
            True if tokens were acquired, False otherwise
        """
        with self.lock:
            self._refill_tokens()

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True

            return False
