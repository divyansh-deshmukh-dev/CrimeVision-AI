"""
services/rate_limiter.py — In-memory sliding-window rate limiter for authentication endpoints.

Prevents credential brute-forcing by tracking failed attempts per IP and username.
"""

from collections import defaultdict
import threading
import time
from typing import Any


def get_client_ip(
    req: Any = None,
    trusted_proxies: set[str] | frozenset[str] | list[str] | None = None,
) -> str:
    """Extract client IP, trusting forwarded proxy headers ONLY if immediate remote_addr is trusted.

    Parameters
    ----------
    req:
        Optional request object (defaults to flask.request).
    trusted_proxies:
        Optional collection of trusted proxy IP strings. If None, reads from
        current_app.config["TRUSTED_PROXIES"].
    """
    from flask import current_app, request as flask_request

    r = req or flask_request
    remote_addr = (getattr(r, "remote_addr", None) or "127.0.0.1").strip()

    if trusted_proxies is None:
        try:
            trusted_proxies = current_app.config.get("TRUSTED_PROXIES", frozenset())
        except RuntimeError:
            trusted_proxies = frozenset()

    trusted_set = set(trusted_proxies) if trusted_proxies else set()

    # If the direct peer is not in the trusted proxies set, never trust forwarded headers
    if remote_addr not in trusted_set:
        return remote_addr

    # Direct peer is a trusted proxy: parse X-Forwarded-For
    headers = getattr(r, "headers", {})
    forwarded = headers.get("X-Forwarded-For")
    if not forwarded:
        return remote_addr

    ips = [ip.strip() for ip in forwarded.split(",") if ip.strip()]
    if not ips:
        return remote_addr

    # Walk backwards (from right to left) and return the first untrusted IP
    for ip in reversed(ips):
        if ip not in trusted_set:
            return ip

    return ips[0]


class LoginRateLimiter:
    """Sliding-window rate limiter for login attempts."""

    def __init__(self, max_attempts: int = 5, window_seconds: int = 900):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._attempts: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def _clean_window(self, key: str, now: float) -> list[float]:
        cutoff = now - self.window_seconds
        valid = [t for t in self._attempts[key] if t > cutoff]
        if valid:
            self._attempts[key] = valid
        else:
            self._attempts.pop(key, None)
        return valid

    def is_rate_limited(self, key: str) -> bool:
        """Return True if the key has exceeded max failed attempts within the window."""
        with self._lock:
            now = time.time()
            valid = self._clean_window(key, now)
            return len(valid) >= self.max_attempts

    def get_retry_after(self, key: str) -> int:
        """Return number of seconds remaining before the lockout window expires."""
        with self._lock:
            now = time.time()
            valid = self._clean_window(key, now)
            if not valid:
                return 0
            oldest = min(valid)
            remaining = int(self.window_seconds - (now - oldest))
            return max(remaining, 1)

    def record_failure(self, key: str) -> None:
        """Record a failed login attempt timestamp for key."""
        with self._lock:
            now = time.time()
            self._clean_window(key, now)
            self._attempts[key].append(now)

    def record_success(self, key: str) -> None:
        """Clear recorded failures on successful authentication."""
        with self._lock:
            self._attempts.pop(key, None)

    def reset(self) -> None:
        """Clear all tracked attempts (useful for testing)."""
        with self._lock:
            self._attempts.clear()


# Global rate limiter instance
login_limiter = LoginRateLimiter(max_attempts=5, window_seconds=900)
