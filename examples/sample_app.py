#!/usr/bin/env python3
"""Sample application demonstrating zk-config-starter.

Usage::

    # Start Zookeeper first (see docs/zookeeper-docker.md)
    cd docs && docker compose up -d

    # Seed some properties
    docker compose exec zookeeper zkCli.sh -server localhost:2181 \\
        create /config "" && \\
        create /config/db.host localhost && \\
        create /config/db.port 5432 && \\
        create /config/app.env production

    # Run this script
    ZK_HOSTS=localhost:2181 ZK_PATH=/config python examples/sample_app.py

Press Ctrl+C to stop.
"""
import logging
import os
import sys
import time
from typing import Dict

# Add src/ to path when running from the project root without installing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from zk_config_starter import StorageMode, ZkConfigClient

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("sample_app")


# ---------------------------------------------------------------------------
# Change subscriber
# ---------------------------------------------------------------------------
def on_config_change(snapshot: Dict[str, str]) -> None:
    logger.info("*** Config changed! New snapshot (%d keys): %s", len(snapshot), snapshot)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    hosts = os.environ.get("ZK_HOSTS", "localhost:2181")
    path = os.environ.get("ZK_PATH", "/config")
    mode_str = os.environ.get("ZK_MODE", "children").lower()

    if mode_str == "properties":
        mode = StorageMode.PROPERTIES_FILE
    else:
        mode = StorageMode.CHILDREN_AS_KEYS

    logger.info("Connecting to Zookeeper at %s  path=%s  mode=%s", hosts, path, mode.value)

    with ZkConfigClient(hosts=hosts, path=path, mode=mode) as client:
        # Register a change subscriber — called whenever any property changes
        unsub = client.subscribe(on_config_change)

        logger.info(
            "Connected. Watching for changes. Modify a znode in ZooNavigator "
            "(http://localhost:9000) or via zkCli.sh to see live updates."
        )

        try:
            while True:
                config = client.config.get_all()
                print(f"\n[{time.strftime('%H:%M:%S')}] Current config ({len(config)} keys):")
                if config:
                    for k, v in sorted(config.items()):
                        print(f"  {k} = {v}")
                else:
                    print("  (empty — no properties found yet)")
                time.sleep(5)

        except KeyboardInterrupt:
            logger.info("Shutting down…")
            unsub()


if __name__ == "__main__":
    main()
