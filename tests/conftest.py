"""Pytest configuration and shared fixtures."""
import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests that require a live Zookeeper instance.",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "integration: requires a running Zookeeper instance (set ZK_HOSTS env var)",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list  # type: ignore[type-arg]
) -> None:
    if config.getoption("--run-integration"):
        return
    skip_integration = pytest.mark.skip(
        reason="Pass --run-integration (and set ZK_HOSTS) to run integration tests"
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)
