"""Watcher for the PROPERTIES_FILE storage mode.

The watched znode's data is a ``key=value`` text blob (one property per
line).  The entire store is replaced on every change event.
"""
import logging
from typing import Optional

from kazoo.client import KazooClient

from ..parser import parse_properties
from ..store import ConfigStore
from .base import Watcher

logger = logging.getLogger(__name__)


class PropertiesWatcher(Watcher):
    """Watches a single Zookeeper znode whose data is a properties text blob."""

    def __init__(self) -> None:
        self._stopped: bool = False

    def start(self, zk: KazooClient, path: str, store: ConfigStore) -> None:
        self._stopped = False

        # Ensure the node exists
        zk.ensure_path(path)

        @zk.DataWatch(path)
        def _on_data(data: Optional[bytes], stat: object, event: object = None) -> Optional[bool]:
            if self._stopped:
                return False  # cancel watch

            if data is None:
                # Node deleted — clear all properties
                store.replace_all({})
                logger.debug("PropertiesWatcher: node deleted, store cleared")
                return None  # keep watching (node may be re-created)

            text = data.decode("utf-8") if data else ""
            try:
                props = parse_properties(text)
            except Exception:
                logger.exception(
                    "PropertiesWatcher: failed to parse properties blob; store unchanged"
                )
                return None

            store.replace_all(props)
            logger.debug(
                "PropertiesWatcher: store replaced with %d properties", len(props)
            )
            return None  # keep watching

        # Strong reference so the closure isn't GC'd
        self._data_watch = _on_data  # type: ignore[assignment]

    def stop(self) -> None:
        self._stopped = True
