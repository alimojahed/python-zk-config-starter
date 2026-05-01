"""Thread-safe configuration store backed by an RLock-protected dict."""
import logging
import threading
from typing import Callable, Dict, Iterator, List, Mapping, Optional

logger = logging.getLogger(__name__)


class ConfigStore:
    """A thread-safe, mutable dictionary of configuration properties.

    All mutation methods (``update_one``, ``replace_all``) are called from
    Kazoo's internal event thread.  All read methods are safe to call from
    any thread at any time.

    Change subscribers receive a *snapshot* (shallow copy) of the store
    after each mutation, invoked **outside** the internal lock to prevent
    deadlocks from callbacks that themselves read the store.

    Example::

        store = ConfigStore()
        unsubscribe = store.subscribe(lambda snap: print("changed:", snap))

        value = store.get("db.host", default="localhost")
        all_props = store.get_all()   # returns a safe-to-iterate copy

        unsubscribe()  # stop receiving change notifications
    """

    def __init__(self) -> None:
        self._lock: threading.RLock = threading.RLock()
        self._data: Dict[str, str] = {}
        self._subs: List[Callable[[Dict[str, str]], None]] = []

    # ------------------------------------------------------------------
    # Read API
    # ------------------------------------------------------------------

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Return the value for *key*, or *default* if not present."""
        with self._lock:
            return self._data.get(key, default)

    def get_all(self) -> Dict[str, str]:
        """Return a shallow copy of all properties.

        The returned dict is safe to iterate even if the store is
        concurrently mutated.
        """
        with self._lock:
            return dict(self._data)

    def __getitem__(self, key: str) -> str:
        with self._lock:
            return self._data[key]

    def __contains__(self, key: object) -> bool:
        with self._lock:
            return key in self._data

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)

    def keys(self) -> List[str]:
        """Return a list of all current keys (snapshot)."""
        with self._lock:
            return list(self._data.keys())

    def __iter__(self) -> Iterator[str]:
        """Iterate over a snapshot of keys."""
        return iter(self.keys())

    def __repr__(self) -> str:
        with self._lock:
            return f"{self.__class__.__name__}({self._data!r})"

    # ------------------------------------------------------------------
    # Mutation API  (called from Kazoo event thread)
    # ------------------------------------------------------------------

    def update_one(self, key: str, value: Optional[str]) -> None:
        """Set or delete a single key.

        Args:
            key: The property key.
            value: The new value, or ``None`` to delete the key.
        """
        with self._lock:
            if value is None:
                self._data.pop(key, None)
                logger.debug("config key deleted: %r", key)
            else:
                self._data[key] = value
                logger.debug("config key updated: %r = %r", key, value)
            snapshot = dict(self._data)
            subs = list(self._subs)

        self._notify(subs, snapshot)

    def replace_all(self, new_data: Mapping[str, str]) -> None:
        """Atomically replace the entire store with *new_data*.

        Args:
            new_data: The new set of properties.
        """
        with self._lock:
            self._data = dict(new_data)
            logger.debug("config store replaced with %d keys", len(self._data))
            snapshot = dict(self._data)
            subs = list(self._subs)

        self._notify(subs, snapshot)

    # ------------------------------------------------------------------
    # Subscriptions
    # ------------------------------------------------------------------

    def subscribe(
        self, callback: Callable[[Dict[str, str]], None]
    ) -> Callable[[], None]:
        """Register *callback* to be invoked on every store mutation.

        The callback receives a snapshot (shallow copy) of the full store
        at the time of the change.  It is called from Kazoo's event thread,
        so it must not block for long.

        Args:
            callback: A callable that accepts a ``Dict[str, str]`` snapshot.

        Returns:
            An unsubscribe callable.  Call it to stop receiving notifications.
        """
        with self._lock:
            self._subs.append(callback)

        def unsubscribe() -> None:
            with self._lock:
                try:
                    self._subs.remove(callback)
                except ValueError:
                    pass

        return unsubscribe

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _notify(
        subs: List[Callable[[Dict[str, str]], None]],
        snapshot: Dict[str, str],
    ) -> None:
        for cb in subs:
            try:
                cb(snapshot)
            except Exception:
                logger.exception("exception in config store subscriber")
