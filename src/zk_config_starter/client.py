"""Main public facade for zk-config-starter."""
import logging
from typing import Callable, Dict, Optional

from kazoo.client import KazooClient
from kazoo.exceptions import KazooException

from .connection import AuthData, _ZkSession, _operation_exception
from .exceptions import ZkConfigError
from .modes import StorageMode
from .store import ConfigStore
from .watchers.base import Watcher
from .watchers.children import ChildrenWatcher
from .watchers.properties import PropertiesWatcher

logger = logging.getLogger(__name__)


class ZkConfigClient:
    """Connects to Zookeeper, watches a config path, and exposes a live
    :class:`~zk_config_starter.store.ConfigStore` that updates automatically.

    The client supports two usage styles:

    **Context manager (recommended)**::

        with ZkConfigClient(hosts="localhost:2181", path="/config") as client:
            value = client.config.get("db.host", "localhost")

    **Explicit lifecycle**::

        client = ZkConfigClient(hosts="localhost:2181", path="/config")
        client.start()
        try:
            value = client.config.get("db.host")
        finally:
            client.close()

    Args:
        hosts: Comma-separated ``host:port`` pairs for Zookeeper
            (e.g. ``"zk1:2181,zk2:2181"``).
        path: The Zookeeper znode path to watch (e.g. ``"/config/myapp"``).
        mode: How properties are stored under *path*.
            Defaults to :attr:`~StorageMode.CHILDREN_AS_KEYS`.
        timeout: Connection timeout in seconds.
        auth_data: Optional sequence of ``(scheme, credential)`` pairs. String
            and byte credentials are passed unchanged to
            :meth:`kazoo.client.KazooClient.add_auth`.
    """

    def __init__(
        self,
        hosts: str,
        path: str,
        mode: StorageMode = StorageMode.CHILDREN_AS_KEYS,
        timeout: float = 10.0,
        auth_data: Optional[AuthData] = None,
    ) -> None:
        self._hosts = hosts
        self._path = path.rstrip("/")
        self._mode = mode
        self._timeout = timeout
        self._auth_data = auth_data or []

        self._store: ConfigStore = ConfigStore()
        self._watcher: Watcher = self._make_watcher()
        self._session = _ZkSession(
            hosts,
            timeout=timeout,
            auth_data=self._auth_data,
        )
        self._zk: Optional[KazooClient] = None
        self._started: bool = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Connect to Zookeeper and start watching *path*.

        Raises:
            ZkConnectionError: If the connection cannot be established within
                *timeout* seconds.
        """
        if self._started:
            return

        logger.info(
            "Connecting to Zookeeper at %r (path=%r, mode=%s)",
            self._hosts,
            self._path,
            self._mode.value,
        )

        try:
            self._session.start()
            self._zk = self._session.client
            self._watcher.start(self._zk, self._path, self._store)
        except ZkConfigError:
            self._session.close()
            self._zk = None
            raise
        except KazooException as exc:
            self._session.close()
            self._zk = None
            raise _operation_exception(
                exc, f"starting watcher for {self._path!r}"
            ) from exc
        except Exception:
            self._session.close()
            self._zk = None
            raise
        self._started = True
        logger.info("ZkConfigClient started (mode=%s, path=%r)", self._mode.value, self._path)

    def close(self) -> None:
        """Stop watching and disconnect from Zookeeper."""
        if not self._started:
            return

        logger.info("Stopping ZkConfigClient")
        try:
            self._watcher.stop()
        finally:
            self._session.close()
            self._zk = None
            self._started = False

    def __enter__(self) -> "ZkConfigClient":
        self.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def config(self) -> ConfigStore:
        """The live :class:`~zk_config_starter.store.ConfigStore`."""
        return self._store

    def subscribe(
        self, callback: Callable[[Dict[str, str]], None]
    ) -> Callable[[], None]:
        """Register a change callback on the underlying store.

        Equivalent to ``client.config.subscribe(callback)``.

        Args:
            callback: Called with a snapshot ``Dict[str, str]`` on every change.

        Returns:
            An unsubscribe callable.
        """
        return self._store.subscribe(callback)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _make_watcher(self) -> Watcher:
        if self._mode is StorageMode.CHILDREN_AS_KEYS:
            return ChildrenWatcher()
        return PropertiesWatcher()
