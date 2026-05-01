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
from .exceptions import ZkConfigError, ZkConfigParseError, ZkConnectionError
from .modes import StorageMode
from .store import ConfigStore

__all__ = [
    "ZkConfigClient",
    "ConfigStore",
    "StorageMode",
    "ZkConfigError",
    "ZkConnectionError",
    "ZkConfigParseError",
]

__version__ = "1.0.0"
