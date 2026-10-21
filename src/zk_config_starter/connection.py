"""Internal Kazoo connection and lifecycle management."""
import logging
from typing import Callable, List, Optional, Sequence, Tuple, Union

from kazoo.client import KazooClient
from kazoo.exceptions import (
    AuthFailedError,
    ConnectionLoss,
    KazooException,
    NoNodeError,
    OperationTimeoutError,
    SessionExpiredError,
)

from .exceptions import (
    ZkAuthenticationError,
    ZkConnectionError,
    ZkNodeNotFoundError,
    ZkOperationError,
)

logger = logging.getLogger(__name__)

AuthCredential = Union[str, bytes]
AuthData = Sequence[Tuple[str, AuthCredential]]
ClientFactory = Callable[..., KazooClient]


def _validate_auth_data(auth_data: AuthData) -> Tuple[Tuple[str, AuthCredential], ...]:
    """Validate and freeze authentication entries without logging credentials."""
    validated: List[Tuple[str, AuthCredential]] = []
    for entry in auth_data:
        if not isinstance(entry, (tuple, list)) or len(entry) != 2:
            raise ValueError("auth_data entries must be (scheme, credential) pairs")
        scheme, credential = entry
        if not isinstance(scheme, str) or not scheme:
            raise ValueError("authentication scheme must be a non-empty string")
        if not isinstance(credential, (str, bytes)):
            raise ValueError("authentication credentials must be strings or bytes")
        validated.append((scheme, credential))
    return tuple(validated)


def _operation_exception(exc: KazooException, action: str) -> Exception:
    """Translate a Kazoo operation exception into the public exception hierarchy."""
    if isinstance(exc, AuthFailedError):
        return ZkAuthenticationError(f"Zookeeper authentication failed while {action}")
    if isinstance(exc, NoNodeError):
        return ZkNodeNotFoundError(f"Zookeeper node not found while {action}")
    if isinstance(exc, (ConnectionLoss, OperationTimeoutError, SessionExpiredError)):
        return ZkConnectionError(f"Zookeeper connection failed while {action}")
    return ZkOperationError(f"Zookeeper operation failed while {action}")


class _ZkSession:
    """Own one Kazoo client and centralize connection, auth, and cleanup."""

    def __init__(
        self,
        hosts: str,
        *,
        timeout: float = 10.0,
        auth_data: Optional[AuthData] = None,
        client_factory: Optional[ClientFactory] = None,
    ) -> None:
        if not isinstance(hosts, str) or not hosts.strip():
            raise ValueError("hosts must be a non-empty string")
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")

        self._hosts = hosts
        self._timeout = timeout
        self._auth_data = _validate_auth_data(auth_data or ())
        self._client_factory = client_factory
        self._client: Optional[KazooClient] = None
        self._started = False

    @property
    def client(self) -> KazooClient:
        """Return the started client for internal consumers."""
        if not self._started or self._client is None:
            raise RuntimeError("Zookeeper session has not been started")
        return self._client

    @property
    def started(self) -> bool:
        return self._started

    def start(self) -> None:
        """Connect and authenticate, rolling back after any partial failure."""
        if self._started:
            return

        factory = self._client_factory or KazooClient
        zk = factory(hosts=self._hosts, timeout=self._timeout)
        try:
            zk.start(timeout=self._timeout)
        except AuthFailedError as exc:
            self._cleanup_partial(zk)
            raise ZkAuthenticationError(
                f"Zookeeper authentication failed at {self._hosts!r}"
            ) from exc
        except Exception as exc:
            self._cleanup_partial(zk)
            raise ZkConnectionError(
                f"Failed to connect to Zookeeper at {self._hosts!r}: {exc}"
            ) from exc

        try:
            for scheme, credential in self._auth_data:
                zk.add_auth(scheme, credential)
        except AuthFailedError as exc:
            self._cleanup_partial(zk)
            raise ZkAuthenticationError(
                "Zookeeper rejected the configured authentication credentials"
            ) from exc
        except KazooException as exc:
            self._cleanup_partial(zk)
            raise _operation_exception(exc, "applying authentication") from exc
        except Exception:
            self._cleanup_partial(zk)
            raise

        self._client = zk
        self._started = True

    def close(self) -> None:
        """Stop and close the owned Kazoo client. Safe to call repeatedly."""
        zk = self._client
        self._client = None
        was_started = self._started
        self._started = False
        if zk is None:
            return

        if was_started:
            try:
                zk.stop()
            except Exception:
                logger.exception("Error while stopping Kazoo client")
        try:
            zk.close()
        except Exception:
            logger.exception("Error while closing Kazoo client")

    @staticmethod
    def _cleanup_partial(zk: KazooClient) -> None:
        """Best-effort cleanup for a client that failed during startup."""
        try:
            zk.stop()
        except Exception:
            logger.debug("Error while stopping partially initialized Kazoo client", exc_info=True)
        try:
            zk.close()
        except Exception:
            logger.debug("Error while closing partially initialized Kazoo client", exc_info=True)

