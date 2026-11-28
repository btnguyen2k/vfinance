"""Private, domain-based storage for reusable temporary values."""

from dataclasses import dataclass, field
from threading import RLock
from time import monotonic
from typing import Any

import cachetools

__all__ = [
    "Cache",
    "CacheEntry",
    "create_domain",
    "delete_domain",
    "set",
    "get",
    "delete",
]

_DEFAULT_MAX_SIZE = 1000


@dataclass(frozen=True, slots=True)
class CacheEntry:
    """A cached value and its lifetime.

    Attributes:
        value (Any): The original value, held by reference.
        ttl (int): Lifetime in seconds. Non-positive integers disable expiry;
            non-integers, including booleans, become 0.
        expires_at (float | None): Monotonic-clock deadline, or None when expiry
            is disabled. This is not a Unix timestamp.
    """

    value: Any
    ttl: int = 0
    expires_at: float | None = field(init=False)

    def __post_init__(self) -> None:
        ttl = self.ttl
        if isinstance(ttl, bool) or not isinstance(ttl, int):
            ttl = 0
        expires_at = None
        if ttl > 0:
            try:
                expires_at = monotonic() + ttl
            except OverflowError:
                # This clock cannot reach an unrepresentably long lifetime.
                expires_at = float("inf")
        object.__setattr__(self, "ttl", ttl)
        object.__setattr__(self, "expires_at", expires_at)

    def is_expired(self) -> bool:
        """Check whether this value has reached the end of its lifetime.

        Returns:
            bool: True at or after the deadline; False when expiry is disabled
                or the deadline has not been reached.
        """
        return self.expires_at is not None and monotonic() >= self.expires_at


class Cache:
    """Reuse values within one bounded cache domain.

    Notes:
        Each instance owns one LRU store. Access is synchronized across threads,
        but stored values are not copied or protected against external mutation.
        Expired entries are removed when read; there is no background cleanup.
    """

    def __init__(self, max_size: int = _DEFAULT_MAX_SIZE) -> None:
        """Create bounded storage for one independent cache domain.

        Args:
            max_size (int): Maximum number of entries, default 1000.
                Non-positive or non-integer values, including booleans, use
                1000 instead.

        Notes:
            The capacity is fixed for the lifetime of this instance.
            Constructing an instance does not register a named domain.
        """
        if isinstance(max_size, bool) or not isinstance(max_size, int) or max_size <= 0:
            max_size = _DEFAULT_MAX_SIZE
        self._cache: cachetools.LRUCache[str, CacheEntry] = cachetools.LRUCache(
            maxsize=max_size
        )
        self._lock = RLock()

    def set(self, key: str, value: Any, ttl: int = 0) -> None:
        """Store a reusable value or remove it when None is supplied.

        Args:
            key (str): Cache key, used unchanged within the domain.
            value (Any): Value to retain by reference. None deletes the key.
            ttl (int): Lifetime in seconds, default 0. Non-positive or
                non-integer values, including booleans, disable expiry.

        Returns:
            None: The value is stored, or the key is silently removed.

        Notes:
            Every write restarts the lifetime, even for the same key and value.
            When full, the domain evicts its least recently used entry.
        """
        with self._lock:
            if value is None:
                self._cache.pop(key, None)
            else:
                self._cache[key] = CacheEntry(value=value, ttl=ttl)

    def get(self, key: str) -> Any | None:
        """Retrieve a retained value while its lifetime remains valid.

        Args:
            key (str): Cache key, used unchanged within the domain.

        Returns:
            Any | None: The original value, or None when the key is missing or
                the entry has expired. Expired entries are removed.

        Notes:
            A successful read marks the entry as recently used without
            extending its lifetime.
        """
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            if entry.is_expired():
                del self._cache[key]
                return None
            return entry.value

    def delete(self, key: str) -> None:
        """Discard a value without requiring it to exist.

        Args:
            key (str): Cache key, used unchanged within the domain.

        Returns:
            None: The key is removed; a missing key is ignored.
        """
        with self._lock:
            self._cache.pop(key, None)


_domains: dict[str, Cache] = {}
_domains_lock = RLock()


def create_domain(domain: str, max_size: int = _DEFAULT_MAX_SIZE) -> None:
    """Reserve shared storage for a named group of related values.

    Args:
        domain (str): Domain name, used unchanged.
        max_size (int): Maximum number of entries, default 1000. Non-positive
            or non-integer values, including booleans, use 1000 instead.

    Returns:
        None: A Cache instance is registered, or the existing one is retained.

    Notes:
        Named domains are shared by all callers in this process. cachetools
        exposes a read-only maxsize, so existing contents and capacity remain
        unchanged. Delete and recreate a domain to change its limit.
    """
    with _domains_lock:
        if domain not in _domains:
            _domains[domain] = Cache(max_size=max_size)


def delete_domain(domain: str) -> None:
    """Discard a named domain and all values owned by it.

    Args:
        domain (str): Domain name, used unchanged.

    Returns:
        None: The registered Cache instance is removed; a missing domain is
            ignored.
    """
    with _domains_lock:
        _domains.pop(domain, None)


def set(domain: str, key: str, value: Any, ttl: int = 0) -> None:
    """Store a reusable value in a shared domain or remove it when None is supplied.

    Args:
        domain (str): Domain name, used unchanged. A missing domain is created
            with a capacity of 1000, even when value is None.
        key (str): Cache key, used unchanged within the domain.
        value (Any): Value to retain by reference. None deletes the key.
        ttl (int): Lifetime in seconds, default 0. Non-positive or non-integer
            values, including booleans, disable expiry.

    Returns:
        None: The value is stored, or the key is silently removed.

    Notes:
        Every write restarts the lifetime, even for the same key and value.
        When full, the domain evicts its least recently used entry.
    """
    with _domains_lock:
        create_domain(domain)
        cache = _domains[domain]
    cache.set(key, value, ttl=ttl)


def get(domain: str, key: str) -> Any | None:
    """Retrieve a retained value from a shared domain while it remains valid.

    Args:
        domain (str): Domain name, used unchanged.
        key (str): Cache key, used unchanged within the domain.

    Returns:
        Any | None: The original value, or None when the domain or key is missing
            or the entry has expired. Expired entries are removed.

    Notes:
        A successful read updates LRU order without extending the lifetime.
        Missing domains are not created.
    """
    with _domains_lock:
        cache = _domains.get(domain)
    return cache.get(key) if cache is not None else None


def delete(domain: str, key: str) -> None:
    """Discard a value from a shared domain without requiring it to exist.

    Args:
        domain (str): Domain name, used unchanged.
        key (str): Cache key, used unchanged within the domain.

    Returns:
        None: The key is removed; a missing domain or key is ignored.
            Missing domains are not created.
    """
    with _domains_lock:
        cache = _domains.get(domain)
    if cache is not None:
        cache.delete(key)
