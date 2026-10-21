"""zk-config-starter — Zookeeper-backed live config dictionary for Python.

Quickstart::

    from zk_config_starter import ZkConfigClient, StorageMode

    with ZkConfigClient(hosts="localhost:2181", path="/config") as client:
        db_host = client.config.get("db.host", "localhost")
        all_props = client.config.get_all()

Public API
----------
- :class:`ZkConfigClient` — main facade; connects, watches, exposes the store
- :class:`ConfigStore` — thread-safe property dictionary
- :class:`StorageMode` — ``CHILDREN_AS_KEYS`` or ``PROPERTIES_FILE``
- :exc:`ZkConfigError` — base exception
- :exc:`ZkConnectionError` — raised when ZK connection fails
- :exc:`ZkConfigParseError` — raised when properties-file data is malformed
"""
from .client import ZkConfigClient
from .exceptions import (
    ZkAuthenticationError,
    ZkConfigError,
    ZkConfigParseError,
    ZkConnectionError,
    ZkNodeNotFoundError,
    ZkOperationError,
    ZkSnapshotChangedError,
)
from .modes import StorageMode
from .parser import parse_properties
from .reader import ZkNode, ZkReader
from .store import ConfigStore

__all__ = [
    "ZkConfigClient",
    "ZkReader",
    "ZkNode",
    "ConfigStore",
    "StorageMode",
    "parse_properties",
    "ZkConfigError",
    "ZkConnectionError",
    "ZkAuthenticationError",
    "ZkOperationError",
    "ZkNodeNotFoundError",
    "ZkSnapshotChangedError",
    "ZkConfigParseError",
]

__version__ = "1.1.0"
