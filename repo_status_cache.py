import time
from typing import Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class CachedRepoStatus:
    """Container for cached repository status information."""
    data: Dict[str, Any]
    timestamp: datetime
    ttl_seconds: int

    def is_expired(self) -> bool:
        """Check if cached data has exceeded its time-to-live."""
        return datetime.now() - self.timestamp > timedelta(seconds=self.ttl_seconds)


class RepoStatusCache:
    """In-memory cache for GitHub repository status to reduce API calls."""

    def __init__(self, default_ttl: int = 300):
        """
        Initialize the cache.

        Args:
            default_ttl: Default time-to-live in seconds (default: 5 minutes)
        """
        self._cache: Dict[str, CachedRepoStatus] = {}
        self._default_ttl = default_ttl

    def get(self, repo_key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached repository status if valid.

        Args:
            repo_key: Unique identifier for the repository

        Returns:
            Cached data if available and not expired, None otherwise
        """
        if repo_key not in self._cache:
            return None

        cached = self._cache[repo_key]
        if cached.is_expired():
            del self._cache[repo_key]
            return None

        return cached.data

    def set(self, repo_key: str, data: Dict[str, Any], ttl: Optional[int] = None) -> None:
        """
        Store repository status in cache.

        Args:
            repo_key: Unique identifier for the repository
            data: Status data to cache
            ttl: Time-to-live in seconds (uses default if None)
        """
        ttl_seconds = ttl or self._default_ttl
        self._cache[repo_key] = CachedRepoStatus(
            data=data,
            timestamp=datetime.now(),
            ttl_seconds=ttl_seconds
        )

    def invalidate(self, repo_key: str) -> None:
        """
        Manually invalidate cache entry for a repository.

        Args:
            repo_key: Unique identifier for the repository
        """
        if repo_key in self._cache:
            del self._cache[repo_key]

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()

    def get_cache_stats(self) -> Dict[str, int]:
        """
        Get cache statistics.

        Returns:
            Dictionary with total entries and expired entries count
        """
        total = len(self._cache)
        expired = sum(1 for cached in self._cache.values() if cached.is_expired())
        return {"total_entries": total, "expired_entries": expired}
