"""Custom exceptions for zk-config-starter."""


class ZkConfigError(Exception):
    """Base exception for all zk-config-starter errors."""


class ZkConnectionError(ZkConfigError):
    """Raised when the client cannot connect to or loses connection with Zookeeper."""


class ZkAuthenticationError(ZkConfigError):
    """Raised when Zookeeper rejects the configured authentication credentials."""


class ZkOperationError(ZkConfigError):
    """Raised when a Zookeeper operation fails for a non-connection reason."""


class ZkNodeNotFoundError(ZkOperationError):
    """Raised when a requested Zookeeper node does not exist."""


class ZkSnapshotChangedError(ZkOperationError):
    """Raised when two verification reads return different node snapshots."""


class ZkConfigParseError(ZkConfigError):
    """Raised when a properties-file znode contains data that cannot be parsed."""
