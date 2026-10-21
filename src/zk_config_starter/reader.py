"""Read-only ZooKeeper facade."""
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from kazoo.exceptions import KazooException

from .connection import AuthData, _operation_exception, _ZkSession
from .exceptions import ZkSnapshotChangedError


@dataclass(frozen=True)
class ZkNode:
    """Immutable raw znode data and metadata used for change detection."""

    path: str
    data: bytes
    version: int
    cversion: int


class ZkReader:
    """Own a ZooKeeper session and expose non-creating, read-only operations."""

    def __init__(
        self,
        hosts: str,
        *,
        timeout: float = 10.0,
        auth_data: Optional[AuthData] = None,
    ) -> None:
        self._session = _ZkSession(
            hosts,
            timeout=timeout,
            auth_data=auth_data,
        )

    def start(self) -> None:
        """Start the owned ZooKeeper session. Safe to call repeatedly."""
        self._session.start()

    def close(self) -> None:
        """Close the owned ZooKeeper session. Safe to call repeatedly."""
        self._session.close()

    def __enter__(self) -> "ZkReader":
        self.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def read(self, path: str) -> ZkNode:
        """Read one existing znode without creating or watching it."""
        self._validate_path(path)
        self.start()
        try:
            data, stat = self._session.client.get(path)
        except KazooException as exc:
            raise _operation_exception(exc, f"reading {path!r}") from exc
        return ZkNode(
            path=path,
            data=data,
            version=stat.version,
            cversion=stat.cversion,
        )

    def read_many(self, paths: Sequence[str]) -> Tuple[ZkNode, ...]:
        """Read paths sequentially in input order; the result is not atomic."""
        normalized = self._normalize_paths(paths)
        return tuple(self.read(path) for path in normalized)

    def read_stable(self, paths: Sequence[str]) -> Tuple[ZkNode, ...]:
        """Return two identical ordered reads or report a changed snapshot.

        This performs exactly two complete passes and is not an atomic
        ZooKeeper snapshot.
        """
        normalized = self._normalize_paths(paths)
        first = self.read_many(normalized)
        second = self.read_many(normalized)
        if first != second:
            raise ZkSnapshotChangedError(
                "Zookeeper snapshot changed between the two verification reads"
            )
        return second

    @staticmethod
    def _validate_path(path: str) -> None:
        if not isinstance(path, str) or not path.startswith("/"):
            raise ValueError("Zookeeper path must be an absolute string path")

    @classmethod
    def _normalize_paths(cls, paths: Sequence[str]) -> Tuple[str, ...]:
        if isinstance(paths, (str, bytes)):
            raise ValueError("paths must be a sequence of absolute string paths")
        normalized: List[str] = []
        for path in paths:
            cls._validate_path(path)
            normalized.append(path)
        return tuple(normalized)

