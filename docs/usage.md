# Usage Guide

## Installation

```bash
pip install zk-config-starter
```

Requires Python 3.7+ and a reachable Zookeeper instance.

---

## Quickstart

### Mode 1: CHILDREN_AS_KEYS (default)

Each child znode of the watched path represents one property.
- znode **name** → property key
- znode **data** → property value (UTF-8 string)

```
/config
  ├── db.host   (data: "localhost")
  ├── db.port   (data: "5432")
  └── app.env   (data: "production")
```

```python
from zk_config_starter import ZkConfigClient, StorageMode

with ZkConfigClient(hosts="localhost:2181", path="/config") as client:
    db_host = client.config.get("db.host", "localhost")
    db_port = client.config.get("db.port", "5432")
    print(client.config.get_all())
    # {'db.host': 'localhost', 'db.port': '5432', 'app.env': 'production'}
```

### Mode 2: PROPERTIES_FILE

The watched znode's data is a ``key=value`` text blob (one property per line).

```
/config   (data: "db.host=localhost\ndb.port=5432\napp.env=production\n")
```

```python
from zk_config_starter import ZkConfigClient, StorageMode

with ZkConfigClient(
    hosts="localhost:2181",
    path="/config",
    mode=StorageMode.PROPERTIES_FILE,
) as client:
    db_host = client.config.get("db.host")
    print(client.config.get_all())
```

---

## Thread-safe access

The `ConfigStore` is safe to read from any thread at any time.

```python
# Always read via client.config methods — never cache a reference to the
# underlying dict.

# Good: thread-safe
value = client.config.get("key", "default")
snapshot = client.config.get_all()   # returns a copy; safe to iterate

# Also available
if "key" in client.config:
    print(client.config["key"])

print(len(client.config))
print(client.config.keys())
```

---

## Read-only znode access

`ZkReader` is for callers that need raw znode bytes and metadata without a
live configuration store. Unlike `ZkConfigClient`, it never creates missing
paths and does not install watchers.

```python
from zk_config_starter import ZkReader

with ZkReader(hosts="localhost:2181") as reader:
    node = reader.read("/config/device")
    print(node.data)
    print(node.version, node.cversion)

    ordered = reader.read_many([
        "/config/device",
        "/config/device/camera-0",
    ])

    stable = reader.read_stable([
        "/config/device",
        "/config/device/camera-0",
    ])
```

`read_many()` reads sequentially in input order and makes no atomicity claim.
`read_stable()` performs exactly two complete ordered passes and returns only
when they match. It detects a change between those passes, but it is not an
atomic ZooKeeper snapshot and does not retry until stable.

Lifecycle can also be managed explicitly with `start()` and `close()`. Both
methods are idempotent. Reads start the owned session lazily if necessary.

Kazoo 2.10 expects string credentials, so strings are recommended. Byte
credentials are also accepted and passed through unchanged for compatibility
with legacy callers; support for bytes depends on the installed Kazoo version.

```python
reader = ZkReader(
    hosts="localhost:2181",
    auth_data=[("digest", "user:password")],
)
```

---

## Change subscriptions

Register a callback to be notified whenever any property changes.  The
callback receives a **snapshot** (shallow copy) of the full store.

```python
def on_change(snapshot: dict) -> None:
    print("Config updated:", snapshot)

with ZkConfigClient(hosts="localhost:2181", path="/config") as client:
    # Register — returns an unsubscribe callable
    unsubscribe = client.subscribe(on_change)

    # ... your application code ...

    # Stop receiving notifications
    unsubscribe()
```

Callbacks are invoked on Kazoo's internal event thread.
- They must **not block for long** (do not perform blocking I/O inside them).
- For heavy processing, hand off to a thread pool or queue.

---

## Explicit lifecycle (without context manager)

```python
client = ZkConfigClient(hosts="localhost:2181", path="/config")
client.start()   # connects and starts watching

try:
    run_application(client)
finally:
    client.close()   # stops watching and disconnects
```

---

## Authentication (digest scheme)

String credentials are recommended for Kazoo 2.10. Byte credentials remain
accepted for legacy pass-through compatibility, but are not supported by every
Kazoo version. Credentials are never encoded or decoded by this library.

```python
client = ZkConfigClient(
    hosts="localhost:2181",
    path="/config",
    auth_data=[("digest", "user:password")],
)
```

---

## Connection timeout

```python
client = ZkConfigClient(
    hosts="zk1:2181,zk2:2181,zk3:2181",
    path="/config",
    timeout=15.0,   # seconds; default is 10.0
)
```

---

## Exception reference

| Exception | When raised |
|-----------|-------------|
| `ZkConnectionError` | Cannot connect within *timeout* seconds |
| `ZkAuthenticationError` | ZooKeeper rejects authentication |
| `ZkNodeNotFoundError` | A requested read-only node is missing |
| `ZkSnapshotChangedError` | Two stable-read passes differ |
| `ZkOperationError` | Another ZooKeeper operation fails |
| `ZkConfigParseError` | `PROPERTIES_FILE` blob contains an unparseable line |
| `ZkConfigError` | Base class for the exceptions above |

```python
from zk_config_starter import ZkConnectionError, ZkConfigError

try:
    client.start()
except ZkConnectionError as exc:
    print(f"ZK unavailable: {exc}")
```

---

## Troubleshooting

**Connection times out**
: Check `hosts` format (`host:port`) and that Zookeeper is reachable from
  your machine.  Increase `timeout` if the network is slow.

**Watcher never fires after code change**
: Make sure the `ZkConfigClient` is not being garbage-collected.  Always
  hold a strong reference (e.g. use it as a context manager or store it in a
  module-level variable).

**ACL / permission denied**
: Pass `auth_data` with the correct scheme and credentials, or check the
  znode ACLs in ZooNavigator.

**SASL / Kerberos**
: SASL authentication is not supported in v0.1.  Use `digest` or `ip` schemes,
  or open a feature request on GitHub.

**`ZkConfigParseError` in PROPERTIES_FILE mode**
: A line in the znode data has no `=` or `:` separator.  Fix the data or
  remove the offending line.
