"""Unit tests for ConfigStore."""
import threading
from typing import Dict, List

import pytest

from zk_config_starter.store import ConfigStore


def make_store(**initial: str) -> ConfigStore:
    store = ConfigStore()
    if initial:
        store.replace_all(initial)
    return store


# ---------------------------------------------------------------------------
# Basic read/write
# ---------------------------------------------------------------------------

class TestBasicAccess:
    def test_get_existing_key(self) -> None:
        store = make_store(host="localhost")
        assert store.get("host") == "localhost"

    def test_get_missing_key_returns_default(self) -> None:
        store = ConfigStore()
        assert store.get("missing") is None
        assert store.get("missing", "fallback") == "fallback"

    def test_getitem(self) -> None:
        store = make_store(port="5432")
        assert store["port"] == "5432"

    def test_getitem_missing_raises(self) -> None:
        store = ConfigStore()
        with pytest.raises(KeyError):
            _ = store["nope"]

    def test_contains(self) -> None:
        store = make_store(x="1")
        assert "x" in store
        assert "y" not in store

    def test_len(self) -> None:
        store = make_store(a="1", b="2")
        assert len(store) == 2

    def test_keys(self) -> None:
        store = make_store(a="1", b="2")
        assert sorted(store.keys()) == ["a", "b"]

    def test_iter(self) -> None:
        store = make_store(a="1", b="2")
        assert sorted(list(store)) == ["a", "b"]

    def test_repr_contains_class_name(self) -> None:
        store = ConfigStore()
        assert "ConfigStore" in repr(store)


# ---------------------------------------------------------------------------
# Mutation
# ---------------------------------------------------------------------------

class TestMutation:
    def test_update_one_set(self) -> None:
        store = ConfigStore()
        store.update_one("k", "v")
        assert store.get("k") == "v"

    def test_update_one_delete(self) -> None:
        store = make_store(k="v")
        store.update_one("k", None)
        assert "k" not in store

    def test_update_one_delete_missing_key_is_noop(self) -> None:
        store = ConfigStore()
        store.update_one("missing", None)  # must not raise

    def test_replace_all(self) -> None:
        store = make_store(a="1", b="2")
        store.replace_all({"c": "3"})
        assert store.get_all() == {"c": "3"}

    def test_replace_all_clears_previous(self) -> None:
        store = make_store(old="value")
        store.replace_all({"new": "value"})
        assert "old" not in store

    def test_get_all_returns_copy(self) -> None:
        store = make_store(a="1")
        snapshot = store.get_all()
        snapshot["injected"] = "evil"
        assert "injected" not in store


# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------

class TestSubscriptions:
    def test_subscriber_called_on_update_one(self) -> None:
        store = ConfigStore()
        received: List[Dict[str, str]] = []
        store.subscribe(received.append)
        store.update_one("k", "v")
        assert received == [{"k": "v"}]

    def test_subscriber_called_on_replace_all(self) -> None:
        store = ConfigStore()
        received: List[Dict[str, str]] = []
        store.subscribe(received.append)
        store.replace_all({"a": "1"})
        assert received == [{"a": "1"}]

    def test_unsubscribe_stops_notifications(self) -> None:
        store = ConfigStore()
        received: List[Dict[str, str]] = []
        unsub = store.subscribe(received.append)
        unsub()
        store.update_one("k", "v")
        assert received == []

    def test_unsubscribe_idempotent(self) -> None:
        store = ConfigStore()
        unsub = store.subscribe(lambda _: None)
        unsub()
        unsub()  # calling twice must not raise

    def test_subscriber_snapshot_is_isolated(self) -> None:
        store = ConfigStore()
        snapshots: List[Dict[str, str]] = []

        def capture(snap: Dict[str, str]) -> None:
            snapshots.append(snap)

        store.subscribe(capture)
        store.replace_all({"a": "1"})
        store.replace_all({"b": "2"})

        # First snapshot must still be {"a": "1"} even after the second replace
        assert snapshots[0] == {"a": "1"}
        assert snapshots[1] == {"b": "2"}

    def test_failing_subscriber_does_not_prevent_others(self) -> None:
        store = ConfigStore()
        results: List[str] = []

        def bad(_: Dict[str, str]) -> None:
            raise RuntimeError("boom")

        def good(snap: Dict[str, str]) -> None:
            results.append("ok")

        store.subscribe(bad)
        store.subscribe(good)
        store.update_one("k", "v")
        assert results == ["ok"]


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_replace_all_and_get_all(self) -> None:
        """No exception should be raised under concurrent read/write load."""
        store = ConfigStore()
        errors: List[Exception] = []
        iterations = 200

        def writer() -> None:
            for i in range(iterations):
                try:
                    store.replace_all({f"key{j}": str(j) for j in range(10)})
                except Exception as exc:
                    errors.append(exc)

        def reader() -> None:
            for _ in range(iterations):
                try:
                    _ = store.get_all()
                except Exception as exc:
                    errors.append(exc)

        threads = [threading.Thread(target=writer) for _ in range(4)]
        threads += [threading.Thread(target=reader) for _ in range(4)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []

    def test_concurrent_update_one(self) -> None:
        store = ConfigStore()
        errors: List[Exception] = []

        def worker(key: str) -> None:
            for i in range(100):
                try:
                    store.update_one(key, str(i))
                except Exception as exc:
                    errors.append(exc)

        threads = [threading.Thread(target=worker, args=(f"k{n}",)) for n in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
