"""Unit tests for ZkConfigClient (mocked Kazoo — no live ZK required)."""
from unittest.mock import MagicMock, call, patch

import pytest

from zk_config_starter.client import ZkConfigClient
from zk_config_starter.exceptions import ZkConnectionError
from zk_config_starter.modes import StorageMode
from zk_config_starter.watchers.children import ChildrenWatcher
from zk_config_starter.watchers.properties import PropertiesWatcher


@pytest.fixture()
def mock_kazoo():
    """Patch KazooClient so tests never open a real socket."""
    with patch("zk_config_starter.client.KazooClient") as MockKazoo:
        instance = MagicMock()
        MockKazoo.return_value = instance
        yield MockKazoo, instance


class TestZkConfigClientInit:
    def test_default_mode_is_children(self) -> None:
        client = ZkConfigClient(hosts="localhost:2181", path="/cfg")
        assert client._mode is StorageMode.CHILDREN_AS_KEYS

    def test_properties_mode_creates_properties_watcher(self) -> None:
        client = ZkConfigClient(
            hosts="localhost:2181",
            path="/cfg",
            mode=StorageMode.PROPERTIES_FILE,
        )
        assert isinstance(client._watcher, PropertiesWatcher)

    def test_children_mode_creates_children_watcher(self) -> None:
        client = ZkConfigClient(hosts="localhost:2181", path="/cfg")
        assert isinstance(client._watcher, ChildrenWatcher)

    def test_trailing_slash_stripped_from_path(self) -> None:
        client = ZkConfigClient(hosts="localhost:2181", path="/cfg/")
        assert client._path == "/cfg"


class TestZkConfigClientLifecycle:
    def test_start_calls_kazoo_start(self, mock_kazoo: tuple) -> None:
        MockKazoo, zk_instance = mock_kazoo
        client = ZkConfigClient(hosts="localhost:2181", path="/cfg")
        client._watcher = MagicMock()

        client.start()

        MockKazoo.assert_called_once_with(hosts="localhost:2181", timeout=10.0)
        zk_instance.start.assert_called_once()

    def test_start_is_idempotent(self, mock_kazoo: tuple) -> None:
        MockKazoo, zk_instance = mock_kazoo
        client = ZkConfigClient(hosts="localhost:2181", path="/cfg")
        client._watcher = MagicMock()

        client.start()
        client.start()

        assert zk_instance.start.call_count == 1

    def test_start_raises_connection_error_on_failure(self, mock_kazoo: tuple) -> None:
        MockKazoo, zk_instance = mock_kazoo
        zk_instance.start.side_effect = Exception("timeout")

        client = ZkConfigClient(hosts="bad:9999", path="/cfg")
        with pytest.raises(ZkConnectionError, match="bad:9999"):
            client.start()

    def test_close_calls_watcher_stop_and_kazoo_close(self, mock_kazoo: tuple) -> None:
        _, zk_instance = mock_kazoo
        client = ZkConfigClient(hosts="localhost:2181", path="/cfg")
        mock_watcher = MagicMock()
        client._watcher = mock_watcher

        client.start()
        client.close()

        mock_watcher.stop.assert_called_once()
        zk_instance.stop.assert_called_once()
        zk_instance.close.assert_called_once()

    def test_close_before_start_is_safe(self) -> None:
        client = ZkConfigClient(hosts="localhost:2181", path="/cfg")
        client.close()  # must not raise

    def test_context_manager_starts_and_closes(self, mock_kazoo: tuple) -> None:
        _, zk_instance = mock_kazoo
        client = ZkConfigClient(hosts="localhost:2181", path="/cfg")
        client._watcher = MagicMock()

        with client:
            assert client._started is True

        assert client._started is False

    def test_auth_data_passed_to_kazoo(self, mock_kazoo: tuple) -> None:
        _, zk_instance = mock_kazoo
        cred = ("digest", b"user:pass")
        client = ZkConfigClient(
            hosts="localhost:2181", path="/cfg", auth_data=[cred]
        )
        client._watcher = MagicMock()
        client.start()

        zk_instance.add_auth.assert_called_once_with("digest", b"user:pass")


class TestZkConfigClientConfig:
    def test_config_property_returns_store(self, mock_kazoo: tuple) -> None:
        _, _ = mock_kazoo
        client = ZkConfigClient(hosts="localhost:2181", path="/cfg")
        from zk_config_starter.store import ConfigStore
        assert isinstance(client.config, ConfigStore)

    def test_subscribe_delegates_to_store(self, mock_kazoo: tuple) -> None:
        _, _ = mock_kazoo
        client = ZkConfigClient(hosts="localhost:2181", path="/cfg")
        received = []
        unsub = client.subscribe(received.append)
        client.config.update_one("k", "v")
        assert received == [{"k": "v"}]
        unsub()
        client.config.update_one("k", "v2")
        assert len(received) == 1  # no second notification
