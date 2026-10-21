"""Unit tests for the read-only ZooKeeper facade."""
from typing import Any, Tuple
from unittest.mock import MagicMock, call, patch

import pytest
from kazoo.exceptions import (
    AuthFailedError,
    ConnectionLoss,
    KazooException,
    NoNodeError,
    OperationTimeoutError,
    SessionExpiredError,
)

from zk_config_starter import (
    ZkAuthenticationError,
    ZkConnectionError,
    ZkNode,
    ZkNodeNotFoundError,
    ZkOperationError,
    ZkReader,
    ZkSnapshotChangedError,
)


@pytest.fixture()
def mock_kazoo():
    with patch("zk_config_starter.connection.KazooClient") as factory:
        client = MagicMock()
        factory.return_value = client
        yield factory, client


def result(
    data: bytes,
    version: int = 1,
    cversion: int = 2,
) -> Tuple[bytes, MagicMock]:
    stat = MagicMock(version=version, cversion=cversion)
    return data, stat


class TestZkReaderLifecycle:
    def test_start_and_close_are_idempotent(self, mock_kazoo: tuple) -> None:
        factory, client = mock_kazoo
        reader = ZkReader("localhost:2181")

        reader.start()
        reader.start()
        reader.close()
        reader.close()

        factory.assert_called_once_with(hosts="localhost:2181", timeout=10.0)
        client.start.assert_called_once_with(timeout=10.0)
        client.stop.assert_called_once()
        client.close.assert_called_once()

    def test_context_manager_closes_connection(self, mock_kazoo: tuple) -> None:
        _, client = mock_kazoo
        reader = ZkReader("localhost:2181")

        with reader:
            client.start.assert_called_once_with(timeout=10.0)

        client.stop.assert_called_once()
        client.close.assert_called_once()

    @pytest.mark.parametrize("credential", ["user:pass", b"user:pass"])
    def test_authentication_precedes_read(
        self,
        mock_kazoo: tuple,
        credential: Any,
    ) -> None:
        _, client = mock_kazoo
        client.get.return_value = result(b"value")
        reader = ZkReader(
            "localhost:2181",
            auth_data=[("digest", credential)],
        )

        reader.read("/config")

        assert client.method_calls[:3] == [
            call.start(timeout=10.0),
            call.add_auth("digest", credential),
            call.get("/config"),
        ]

    def test_missing_authentication_does_not_call_add_auth(
        self,
        mock_kazoo: tuple,
    ) -> None:
        _, client = mock_kazoo

        ZkReader("localhost:2181").start()

        client.add_auth.assert_not_called()

    def test_connection_failure_cleans_up(self, mock_kazoo: tuple) -> None:
        _, client = mock_kazoo
        reader = ZkReader("localhost:2181")
        client.start.side_effect = RuntimeError("timeout")

        with pytest.raises(ZkConnectionError):
            reader.start()

        client.stop.assert_called_once()
        client.close.assert_called_once()

    def test_authentication_failure_cleans_up(self, mock_kazoo: tuple) -> None:
        _, client = mock_kazoo
        client.add_auth.side_effect = AuthFailedError()
        reader = ZkReader(
            "localhost:2181",
            auth_data=[("digest", b"user:pass")],
        )

        with pytest.raises(ZkAuthenticationError):
            reader.start()

        client.stop.assert_called_once()
        client.close.assert_called_once()

    @pytest.mark.parametrize(
        "auth_data",
        [
            [("", b"credential")],
            [("digest", 123)],
            [("digest", None)],
            [("digest",)],
        ],
    )
    def test_malformed_authentication_is_rejected(self, auth_data: Any) -> None:
        with pytest.raises(ValueError):
            ZkReader("localhost:2181", auth_data=auth_data)


class TestZkReaderReads:
    def test_read_returns_raw_data_and_metadata(self, mock_kazoo: tuple) -> None:
        _, client = mock_kazoo
        reader = ZkReader("localhost:2181")
        client.get.return_value = result(b"payload", version=3, cversion=4)

        node = reader.read("/config/device")

        assert node == ZkNode(
            path="/config/device",
            data=b"payload",
            version=3,
            cversion=4,
        )
        client.ensure_path.assert_not_called()

    def test_read_many_preserves_order(self, mock_kazoo: tuple) -> None:
        _, client = mock_kazoo
        reader = ZkReader("localhost:2181")
        client.get.side_effect = [result(b"a"), result(b"b")]

        nodes = reader.read_many(["/a", "/b"])

        assert [node.path for node in nodes] == ["/a", "/b"]
        assert [node.data for node in nodes] == [b"a", b"b"]
        assert client.get.call_args_list == [call("/a"), call("/b")]

    def test_read_many_stops_on_first_failure(self, mock_kazoo: tuple) -> None:
        _, client = mock_kazoo
        reader = ZkReader("localhost:2181")
        client.get.side_effect = [result(b"a"), NoNodeError(), result(b"c")]

        with pytest.raises(ZkNodeNotFoundError):
            reader.read_many(["/a", "/missing", "/c"])

        assert client.get.call_count == 2

    def test_stable_read_performs_exactly_two_complete_passes(
        self,
        mock_kazoo: tuple,
    ) -> None:
        _, client = mock_kazoo
        reader = ZkReader("localhost:2181")
        client.get.side_effect = [
            result(b"a"),
            result(b"b"),
            result(b"a"),
            result(b"b"),
        ]

        nodes = reader.read_stable(["/a", "/b"])

        assert [node.data for node in nodes] == [b"a", b"b"]
        assert client.get.call_args_list == [
            call("/a"),
            call("/b"),
            call("/a"),
            call("/b"),
        ]

    def test_stable_read_detects_snapshot_change(self, mock_kazoo: tuple) -> None:
        _, client = mock_kazoo
        reader = ZkReader("localhost:2181")
        client.get.side_effect = [
            result(b"before", version=1),
            result(b"after", version=2),
        ]

        with pytest.raises(ZkSnapshotChangedError):
            reader.read_stable(["/config"])

        assert client.get.call_count == 2

    @pytest.mark.parametrize(
        ("kazoo_error", "expected_error"),
        [
            (NoNodeError(), ZkNodeNotFoundError),
            (AuthFailedError(), ZkAuthenticationError),
            (ConnectionLoss(), ZkConnectionError),
            (OperationTimeoutError(), ZkConnectionError),
            (SessionExpiredError(), ZkConnectionError),
            (KazooException(), ZkOperationError),
        ],
    )
    def test_read_exception_mapping(
        self,
        mock_kazoo: tuple,
        kazoo_error: KazooException,
        expected_error: Any,
    ) -> None:
        _, client = mock_kazoo
        reader = ZkReader("localhost:2181")
        client.get.side_effect = kazoo_error

        with pytest.raises(expected_error):
            reader.read("/config")

