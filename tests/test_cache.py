from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import pytest

from vfinance import _cache


@pytest.fixture(autouse=True)
def reset_domains(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_cache, "_domains", {})


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Mock:
    clock = Mock(return_value=100.0)
    monkeypatch.setattr(_cache, "monotonic", clock)
    return clock


@pytest.mark.parametrize("value", [0, False, "", [], {"symbol": "FPT"}, object()])
def test_set_creates_a_domain_and_preserves_values(value: object) -> None:
    _cache.set("profiles", "FPT", value)

    assert _cache.get("profiles", "FPT") is value
    assert _cache._domains["profiles"].get("FPT") is value


def test_named_domains_are_independent() -> None:
    _cache.set("profiles", "FPT", "profile")
    _cache.set("quotes", "FPT", "quote")

    assert _cache.get("profiles", "FPT") == "profile"
    assert _cache.get("quotes", "FPT") == "quote"


def test_cache_instances_are_independent_domains() -> None:
    cache = _cache.Cache(max_size=1)
    other = _cache.Cache(max_size=1)
    cache.set("FPT", "profile")
    other.set("FPT", "other profile")

    assert cache.get("FPT") == "profile"
    assert other.get("FPT") == "other profile"

    cache.set("BID", "next profile")
    assert cache.get("FPT") is None
    assert other.get("FPT") == "other profile"

    cache.delete("BID")
    assert cache.get("BID") is None
    assert not _cache._domains


def test_module_operations_dispatch_to_the_registered_cache() -> None:
    domain = Mock(spec=_cache.Cache)
    domain.get.return_value = "profile"
    _cache._domains["profiles"] = domain

    _cache.set("profiles", "FPT", "profile", ttl=5)
    assert _cache.get("profiles", "FPT") == "profile"
    _cache.delete("profiles", "FPT")

    domain.set.assert_called_once_with("FPT", "profile", ttl=5)
    domain.get.assert_called_once_with("FPT")
    domain.delete.assert_called_once_with("FPT")
    assert _cache._domains["profiles"] is domain


@pytest.mark.parametrize("max_size", [0, -1, None, "2", 2.0, True, False])
def test_invalid_domain_size_uses_default_capacity(max_size: object) -> None:
    _cache.create_domain("profiles", max_size=max_size)  # type: ignore[arg-type]
    for index in range(1001):
        _cache.set("profiles", str(index), index)

    assert _cache.get("profiles", "0") is None
    assert _cache.get("profiles", "1") == 1
    assert _cache.get("profiles", "1000") == 1000


def test_domain_evicts_least_recently_used_values() -> None:
    _cache.create_domain("profiles", max_size=2)
    _cache.set("profiles", "first", "a")
    _cache.set("profiles", "second", "b")
    assert _cache.get("profiles", "first") == "a"

    _cache.set("profiles", "third", "c")

    assert _cache.get("profiles", "second") is None
    assert _cache.get("profiles", "first") == "a"
    assert _cache.get("profiles", "third") == "c"


@pytest.mark.parametrize("new_size", [1, 10])
def test_existing_domain_keeps_its_contents_and_capacity(new_size: int) -> None:
    _cache.create_domain("profiles", max_size=2)
    domain = _cache._domains["profiles"]
    _cache.set("profiles", "first", "a")
    _cache.set("profiles", "second", "b")

    _cache.create_domain("profiles", max_size=new_size)
    assert _cache._domains["profiles"] is domain
    _cache.set("profiles", "third", "c")

    assert _cache.get("profiles", "first") is None
    assert _cache.get("profiles", "second") == "b"
    assert _cache.get("profiles", "third") == "c"


def test_delete_domain_discards_only_its_values_and_allows_reconfiguration() -> None:
    _cache.set("profiles", "FPT", "profile")
    _cache.set("quotes", "FPT", "quote")
    _cache.delete_domain("missing")
    _cache.delete_domain("profiles")
    _cache.delete_domain("profiles")

    assert _cache.get("profiles", "FPT") is None
    assert _cache.get("quotes", "FPT") == "quote"

    _cache.create_domain("profiles", max_size=1)
    _cache.set("profiles", "first", "a")
    _cache.set("profiles", "second", "b")
    assert _cache.get("profiles", "first") is None
    assert _cache.get("profiles", "second") == "b"


def test_get_and_delete_misses_do_not_create_domains() -> None:
    assert _cache.get("profiles", "missing") is None
    _cache.delete("profiles", "missing")
    assert not _cache._domains
    _cache.create_domain("profiles", max_size=1)
    assert _cache.get("profiles", "missing") is None

    _cache.set("profiles", "first", "a")
    _cache.set("profiles", "second", "b")
    assert _cache.get("profiles", "first") is None


def test_none_value_removes_only_the_selected_key() -> None:
    _cache.set("profiles", "FPT", "profile")
    _cache.set("profiles", "BID", "other")
    _cache.set("profiles", "FPT", None)
    _cache.set("profiles", "FPT", None)

    assert _cache.get("profiles", "FPT") is None
    assert _cache.get("profiles", "BID") == "other"


def test_setting_none_still_creates_a_missing_domain() -> None:
    _cache.set("profiles", "missing", None)
    _cache.create_domain("profiles", max_size=1)
    _cache.set("profiles", "first", "a")
    _cache.set("profiles", "second", "b")

    assert _cache.get("profiles", "first") == "a"
    assert _cache.get("profiles", "second") == "b"


def test_delete_is_idempotent_and_preserves_other_keys() -> None:
    _cache.set("profiles", "FPT", "profile")
    _cache.set("profiles", "BID", "other")
    _cache.delete("profiles", "FPT")
    _cache.delete("profiles", "FPT")

    assert _cache.get("profiles", "FPT") is None
    assert _cache.get("profiles", "BID") == "other"


def test_entry_captures_its_lifetime_and_deadline(clock: Mock) -> None:
    entry = _cache.CacheEntry(value="profile", ttl=5)

    assert entry.ttl == 5
    assert entry.expires_at == 105.0
    assert not entry.is_expired()
    clock.return_value = 105.0
    assert entry.is_expired()


def test_ttl_is_per_entry_and_reads_do_not_extend_it(clock: Mock) -> None:
    _cache.set("profiles", "short", "a", ttl=1)
    _cache.set("profiles", "long", "b", ttl=2)
    clock.return_value = 101.0

    assert _cache.get("profiles", "short") is None
    assert "short" not in _cache._domains["profiles"]._cache
    assert _cache.get("profiles", "long") == "b"

    clock.return_value = 102.0
    assert _cache.get("profiles", "long") is None


def test_setting_the_same_value_restarts_its_ttl(clock: Mock) -> None:
    value = object()
    _cache.set("profiles", "FPT", value, ttl=10)
    clock.return_value = 105.0
    _cache.set("profiles", "FPT", value, ttl=10)
    clock.return_value = 110.0

    assert _cache.get("profiles", "FPT") is value
    clock.return_value = 115.0
    assert _cache.get("profiles", "FPT") is None


def test_setting_without_ttl_removes_a_previous_deadline(clock: Mock) -> None:
    _cache.set("profiles", "FPT", "profile", ttl=1)
    _cache.set("profiles", "FPT", "profile")
    clock.return_value = 10000.0

    assert _cache.get("profiles", "FPT") == "profile"


@pytest.mark.parametrize(
    "ttl", [0, -1, None, "5", 2.5, float("inf"), float("nan"), True, False]
)
def test_non_positive_or_non_integer_ttl_disables_expiry(
    ttl: object, clock: Mock
) -> None:
    _cache.set("profiles", "FPT", "profile", ttl=ttl)  # type: ignore[arg-type]
    clock.return_value = 10000.0

    assert _cache.get("profiles", "FPT") == "profile"


def test_very_large_integer_ttl_remains_valid(clock: Mock) -> None:
    _cache.set("profiles", "FPT", "profile", ttl=10**1000)
    clock.return_value = 10000.0

    assert _cache.get("profiles", "FPT") == "profile"


def test_concurrent_cache_operations_are_safe() -> None:
    _cache.create_domain("profiles", max_size=2)

    def use_cache(worker: int) -> None:
        for index in range(100):
            key = f"{worker}:{index}"
            value = (worker, index)
            _cache.set("profiles", key, value)
            result = _cache.get("profiles", key)
            assert result is None or result == value
            _cache.delete("profiles", key)

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(use_cache, range(4)))


def test_concurrent_sets_share_a_new_domain() -> None:
    def store_value(worker: int) -> None:
        _cache.set("profiles", str(worker), worker)

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(store_value, range(4)))

    for worker in range(4):
        assert _cache.get("profiles", str(worker)) == worker
