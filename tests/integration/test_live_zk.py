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

from zk_config_starter import (
    StorageMode,
    ZkConfigClient,
    ZkNodeNotFoundError,
    ZkReader,
)

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


class TestReadOnlyMode:
    def test_read_preserves_data_and_metadata(
        self,
        test_path: str,
        zk_admin: KazooClient,
    ) -> None:
        node_path = f"{test_path}/node"
        zk_admin.create(node_path, b"value")

        with ZkReader(ZK_HOSTS) as reader:
            node = reader.read(node_path)

        assert node.path == node_path
        assert node.data == b"value"
        assert node.version == 0
        assert node.cversion == 0

    def test_missing_read_does_not_create_node(
        self,
        test_path: str,
        zk_admin: KazooClient,
    ) -> None:
        missing_path = f"{test_path}/missing"

        with ZkReader(ZK_HOSTS) as reader:
            with pytest.raises(ZkNodeNotFoundError):
                reader.read(missing_path)

        assert zk_admin.exists(missing_path) is None

    def test_stable_read_returns_ordered_nodes(
        self,
        test_path: str,
        zk_admin: KazooClient,
    ) -> None:
        first_path = f"{test_path}/first"
        second_path = f"{test_path}/second"
        zk_admin.create(first_path, b"first")
        zk_admin.create(second_path, b"second")

        with ZkReader(ZK_HOSTS) as reader:
            nodes = reader.read_stable([first_path, second_path])

        assert [node.path for node in nodes] == [first_path, second_path]
