"""Custom exceptions for zk-config-starter."""


class ZkConfigError(Exception):
    """Base exception for all zk-config-starter errors."""


class ZkConnectionError(ZkConfigError):
    """Raised when the client cannot connect to or loses connection with Zookeeper."""


class ZkConfigParseError(ZkConfigError):
    """Raised when a properties-file znode contains data that cannot be parsed."""
