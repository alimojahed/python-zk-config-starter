"""Watcher for the CHILDREN_AS_KEYS storage mode.

Each child znode of the watched path represents one config property:
  - child name  -> property key
  - child data  -> property value (UTF-8 decoded)

A ChildrenWatch on the folder detects znodes being created or deleted.
A DataWatch per child detects value changes.
"""
import logging
import threading
from typing import Dict, List, Optional

from kazoo.client import KazooClient
from kazoo.exceptions import NoNodeError

from ..store import ConfigStore
from .base import Watcher

logger = logging.getLogger(__name__)


class ChildrenWatcher(Watcher):
    """Watches a Zookeeper folder whose *children* represent config properties."""

    def __init__(self) -> None:
        self._zk: Optional[KazooClient] = None
        self._path: str = ""
        self._store: Optional[ConfigStore] = None
        # Strong references to DataWatch callables, keyed by child name.
        # Kazoo holds a weak ref internally; without strong refs here they get GC'd.
        self._data_watches: Dict[str, object] = {}
        self._lock: threading.Lock = threading.Lock()
        self._stopped: bool = False

    def start(self, zk: KazooClient, path: str, store: ConfigStore) -> None:
        self._zk = zk
        self._path = path
        self._store = store
        self._stopped = False

        # Ensure the root path exists (created with empty data if missing)
        zk.ensure_path(path)

        @zk.ChildrenWatch(path)
        def _on_children(children: List[str]) -> Optional[bool]:
            if self._stopped:
                return False  # cancel the watch
            self._sync_children(children)
            return None  # keep watching

        # Keep a strong reference so the callback isn't GC'd
        self._children_watch = _on_children  # type: ignore[assignment]

    def stop(self) -> None:
        self._stopped = True
        with self._lock:
            self._data_watches.clear()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _sync_children(self, children: List[str]) -> None:
        """Called by ChildrenWatch when the child list changes."""
        assert self._store is not None
        assert self._zk is not None

        with self._lock:
            current_watched = set(self._data_watches.keys())
            new_children = set(children)

            # Remove keys for znodes that were deleted
            deleted = current_watched - new_children
            for child in deleted:
                self._data_watches.pop(child, None)
                self._store.update_one(child, None)
                logger.debug("child deleted, removed key %r", child)

            # Start a DataWatch for newly appeared children
            added = new_children - current_watched
            for child in added:
                self._start_data_watch(child)

    def _start_data_watch(self, child: str) -> None:
        """Register a DataWatch for a single child znode."""
        assert self._zk is not None
        assert self._store is not None

        child_path = f"{self._path}/{child}"

        # Capture child name in closure default arg to avoid late-binding
        @self._zk.DataWatch(child_path)
        def _on_data(data: Optional[bytes], stat: object, event: object = None,
                     _child: str = child) -> Optional[bool]:
            if self._stopped:
                return False  # cancel watch

            if data is None:
                # Znode deleted — self-cancel and clean up
                with self._lock:
                    self._data_watches.pop(_child, None)
                assert self._store is not None
                self._store.update_one(_child, None)
                logger.debug("DataWatch: node deleted, removed key %r", _child)
                return False

            try:
                value = data.decode("utf-8")
            except UnicodeDecodeError:
                logger.warning(
                    "DataWatch: could not decode data for key %r as UTF-8; skipping",
                    _child,
                )
                return None

            assert self._store is not None
            self._store.update_one(_child, value)
            return None  # keep watching

        with self._lock:
            self._data_watches[child] = _on_data
