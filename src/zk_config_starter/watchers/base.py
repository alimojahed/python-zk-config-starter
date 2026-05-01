"""Abstract base class for Zookeeper watchers."""
import abc

from kazoo.client import KazooClient

from ..store import ConfigStore


class Watcher(abc.ABC):
    """Abstract watcher that monitors a Zookeeper path and updates a ConfigStore.

    Concrete subclasses implement the two storage modes:
    - :class:`~zk_config_starter.watchers.children.ChildrenWatcher`
    - :class:`~zk_config_starter.watchers.properties.PropertiesWatcher`
    """

    @abc.abstractmethod
    def start(self, zk: KazooClient, path: str, store: ConfigStore) -> None:
        """Begin watching *path* on *zk* and writing updates to *store*.

        Args:
            zk: An already-started Kazoo client.
            path: The Zookeeper znode path to watch.
            store: The :class:`~zk_config_starter.store.ConfigStore` to update.
        """

    @abc.abstractmethod
    def stop(self) -> None:
        """Stop all active watches and release internal state."""
