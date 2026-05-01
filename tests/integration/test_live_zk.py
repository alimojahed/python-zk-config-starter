"""Integration tests for zk-config-starter against a live Zookeeper instance.

Requirements:
    - A running Zookeeper accessible at the host(s) defined by the ZK_HOSTS
      environment variable (default: ``localhost:2181``).
    - Run with: ``ZK_HOSTS=localhost:2181 pytest --run-integration``

These tests create temporary znodes under ``/zk_config_starter_test/<uuid>``
and clean up after themselves.
"""
import os
import time
import uuid
from typing import Generator

import pytest
from kazoo.client import KazooClient

from zk_config_starter import StorageMode, ZkConfigClient

pytestmark = pytest.mark.integration

ZK_HOSTS = os.environ.get("ZK_HOSTS", "localhost:2181")
BASE_PATH = "/zk_config_starter_test"


@pytest.fixture()
def zk_admin() -> Generator[KazooClient, None, None]:
    """A raw KazooClient for test setup and teardown."""
    zk = KazooClient(hosts=ZK_HOSTS)
    zk.start(timeout=10)
    yield zk
    zk.stop()
    zk.close()


@pytest.fixture()
def test_path(zk_admin: KazooClient) -> Generator[str, None, None]:
    """A unique temporary znode path cleaned up after each test."""
    path = f"{BASE_PATH}/{uuid.uuid4().hex}"
    zk_admin.ensure_path(path)
    yield path
    if zk_admin.exists(path):
        zk_admin.delete(path, recursive=True)


def _wait(condition: object, timeout: float = 3.0, interval: float = 0.1) -> bool:
    """Poll *condition* callable until it returns truthy or *timeout* expires."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():  # type: ignore[operator]
            return True
        time.sleep(interval)
    return False


# ---------------------------------------------------------------------------
# CHILDREN_AS_KEYS mode
# ---------------------------------------------------------------------------

class TestChildrenMode:
    def test_initial_load(self, test_path: str, zk_admin: KazooClient) -> None:
        zk_admin.create(f"{test_path}/db.host", b"localhost")
        zk_admin.create(f"{test_path}/db.port", b"5432")

        with ZkConfigClient(ZK_HOSTS, test_path, StorageMode.CHILDREN_AS_KEYS) as c:
            assert _wait(lambda: c.config.get("db.host") == "localhost")
            assert c.config.get("db.port") == "5432"

    def test_live_update(self, test_path: str, zk_admin: KazooClient) -> None:
        zk_admin.create(f"{test_path}/key", b"original")

        with ZkConfigClient(ZK_HOSTS, test_path, StorageMode.CHILDREN_AS_KEYS) as c:
            assert _wait(lambda: c.config.get("key") == "original")
            zk_admin.set(f"{test_path}/key", b"updated")
            assert _wait(lambda: c.config.get("key") == "updated")

    def test_new_child_appears(self, test_path: str, zk_admin: KazooClient) -> None:
        with ZkConfigClient(ZK_HOSTS, test_path, StorageMode.CHILDREN_AS_KEYS) as c:
            zk_admin.create(f"{test_path}/new_key", b"new_value")
            assert _wait(lambda: c.config.get("new_key") == "new_value")

    def test_child_deletion(self, test_path: str, zk_admin: KazooClient) -> None:
        zk_admin.create(f"{test_path}/key", b"value")

        with ZkConfigClient(ZK_HOSTS, test_path, StorageMode.CHILDREN_AS_KEYS) as c:
            assert _wait(lambda: "key" in c.config)
            zk_admin.delete(f"{test_path}/key")
            assert _wait(lambda: "key" not in c.config)

    def test_change_subscriber_fires(self, test_path: str, zk_admin: KazooClient) -> None:
        snapshots = []

        with ZkConfigClient(ZK_HOSTS, test_path, StorageMode.CHILDREN_AS_KEYS) as c:
            c.subscribe(snapshots.append)
            zk_admin.create(f"{test_path}/k", b"v")
            assert _wait(lambda: len(snapshots) > 0)
            assert snapshots[-1].get("k") == "v"


# ---------------------------------------------------------------------------
# PROPERTIES_FILE mode
# ---------------------------------------------------------------------------

class TestPropertiesFileMode:
    def test_initial_load(self, test_path: str, zk_admin: KazooClient) -> None:
        zk_admin.set(test_path, b"db.host=localhost\ndb.port=5432\n")

        with ZkConfigClient(ZK_HOSTS, test_path, StorageMode.PROPERTIES_FILE) as c:
            assert _wait(lambda: c.config.get("db.host") == "localhost")
            assert c.config.get("db.port") == "5432"

    def test_live_update(self, test_path: str, zk_admin: KazooClient) -> None:
        zk_admin.set(test_path, b"key=original\n")

        with ZkConfigClient(ZK_HOSTS, test_path, StorageMode.PROPERTIES_FILE) as c:
            assert _wait(lambda: c.config.get("key") == "original")
            zk_admin.set(test_path, b"key=updated\n")
            assert _wait(lambda: c.config.get("key") == "updated")

    def test_node_cleared_clears_store(self, test_path: str, zk_admin: KazooClient) -> None:
        zk_admin.set(test_path, b"key=value\n")

        with ZkConfigClient(ZK_HOSTS, test_path, StorageMode.PROPERTIES_FILE) as c:
            assert _wait(lambda: "key" in c.config)
            zk_admin.set(test_path, b"")
            assert _wait(lambda: "key" not in c.config)
