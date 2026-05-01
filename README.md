# zk-config-starter

[![CI](https://github.com/alimojahed/python-zk-config-starter/actions/workflows/ci.yml/badge.svg)](https://github.com/alimojahed/python-zk-config-starter/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/zk-config-starter.svg)](https://pypi.org/project/zk-config-starter/)
[![Python versions](https://img.shields.io/pypi/pyversions/zk-config-starter.svg)](https://pypi.org/project/zk-config-starter/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A Python SDK that connects to a Zookeeper instance, watches a specific znode
folder, and exposes the properties as a **live, thread-safe, mutable
dictionary** — updated automatically via Zookeeper watchers whenever a
property changes.

---

## Features

- **Live updates** — uses Kazoo watchers (`ChildrenWatch` + `DataWatch`) to
  reflect changes within milliseconds, with no polling.
- **Two storage modes**:
  - `CHILDREN_AS_KEYS` — each child znode = one property (name → value).
  - `PROPERTIES_FILE` — one znode whose data is a `key=value` text blob.
- **Thread-safe** — an `RLock`-guarded store; all reads return snapshots.
- **Change subscriptions** — register callbacks to react to config changes.
- **Python 3.7+** — typed throughout; compatible with `typing` module generics.
- **Context manager** support for clean lifecycle management.

---

## Installation

```bash
pip install zk-config-starter
```

---

## Quickstart

### CHILDREN_AS_KEYS mode (default)

```
/config
  ├── db.host   → "localhost"
  ├── db.port   → "5432"
  └── app.env   → "production"
```

```python
from zk_config_starter import ZkConfigClient, StorageMode

with ZkConfigClient(hosts="localhost:2181", path="/config") as client:
    print(client.config.get("db.host", "localhost"))
    print(client.config.get_all())
    # {'db.host': 'localhost', 'db.port': '5432', 'app.env': 'production'}
```

### PROPERTIES_FILE mode

```
/config  (data: "db.host=localhost\ndb.port=5432\n")
```

```python
from zk_config_starter import ZkConfigClient, StorageMode

with ZkConfigClient(
    hosts="localhost:2181",
    path="/config",
    mode=StorageMode.PROPERTIES_FILE,
) as client:
    print(client.config.get_all())
```

### Change subscriptions

```python
def on_change(snapshot: dict) -> None:
    print("Config changed:", snapshot)

with ZkConfigClient(hosts="localhost:2181", path="/config") as client:
    unsub = client.subscribe(on_change)
    # … your application code …
    unsub()
```

---

## Local Development Setup

### 1. Clone & install

```bash
git clone https://github.com/alimojahed/python-zk-config-starter.git
cd python-zk-config-starter
pip install -e ".[dev]"
```

### 2. Start Zookeeper + ZooNavigator

```bash
cd docs
docker compose up -d
```

Browse ZooNavigator at **http://localhost:9000** (connection "local" is
pre-configured). See [docs/zookeeper-docker.md](docs/zookeeper-docker.md) for
the full guide.

### 3. Run tests

```bash
# Unit tests (no ZK needed)
pytest

# Integration tests (ZK must be running)
ZK_HOSTS=localhost:2181 pytest --run-integration
```

### 4. Run the sample app

```bash
# Seed some znodes first (see docs/zookeeper-docker.md § 3)
ZK_HOSTS=localhost:2181 ZK_PATH=/config python examples/sample_app.py
```

---

## Documentation

- [Usage guide](docs/usage.md) — all options, thread-safety notes, troubleshooting.
- [Zookeeper + ZooNavigator Docker guide](docs/zookeeper-docker.md) — spin up a local stack.

---

## Releasing to PyPI

Releases are automated via GitHub Actions.

### First-time setup

1. **Configure PyPI Trusted Publisher** (one-time, no API token needed):
   - Go to [pypi.org](https://pypi.org) → Account → Publishing → **Add a Pending Trusted Publisher**.
   - Fill in:
     - PyPI project name: `zk-config-starter`
     - GitHub owner: `alimojahed`
     - Repository: `python-zk-config-starter`
     - Workflow filename: `release.yml`
     - Environment name: `pypi`

2. **Create a GitHub Environment** named `pypi` in your repository settings
   (Settings → Environments → New environment).

### Cut a release

```bash
git tag v0.1.0
git push origin v0.1.0
```

The [release workflow](.github/workflows/release.yml) will:
1. Build an sdist and a wheel.
2. Publish them to PyPI using OIDC (no secret tokens needed).
3. Create a GitHub Release with the built artifacts attached and auto-generated release notes.

> **Dry run:** trigger the workflow manually from the Actions tab and set
> `dry_run = true` (default) to test the build without publishing.

---

## License

[MIT](LICENSE) © Ali Mojahed
