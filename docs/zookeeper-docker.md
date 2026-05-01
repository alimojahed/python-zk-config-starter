# Running Zookeeper + ZooNavigator with Docker Compose

This guide spins up a local Zookeeper instance and the ZooNavigator web UI
so you can develop and test `zk-config-starter` without installing anything
beyond Docker.

---

## Prerequisites

| Tool | Minimum version |
|------|----------------|
| Docker | 24.x |
| Docker Compose plugin | v2.x (`docker compose`) |

---

## 1. Start the stack

The `docker-compose.yml` file lives in the `docs/` folder of this repository.

```bash
cd docs
docker compose up -d
```

Expected output:
```
 ✔ Network docs_default      Created
 ✔ Container zookeeper        Started
 ✔ Container zoonavigator     Started
```

Verify Zookeeper is healthy:

```bash
docker compose ps
# STATUS column for "zookeeper" should show "healthy"
```

---

## 2. Open ZooNavigator

Browse to **http://localhost:9000**

A connection named **"local"** is pre-configured pointing at `zookeeper:2181`.
Click **Connect** to open the znode browser.

---

## 3. Seed sample config data

### Option A — Using `zkCli.sh` inside the container (recommended)

```bash
docker compose exec zookeeper zkCli.sh -server localhost:2181
```

Inside the CLI prompt create a config folder and some key znodes:

```
# Create the root config folder (empty data)
create /config ""

# CHILDREN_AS_KEYS mode: each child = one property
create /config/db.host localhost
create /config/db.port 5432
create /config/app.env production
create /config/app.debug false
```

Verify:
```
ls /config
# [app.debug, app.env, db.host, db.port]

get /config/db.host
# localhost
```

Type `quit` to exit the CLI.

### Option B — PROPERTIES_FILE mode

If you plan to use `StorageMode.PROPERTIES_FILE`, store all properties in a
single znode's data:

```bash
docker compose exec zookeeper zkCli.sh -server localhost:2181
```

```
create /config ""
set /config "db.host=localhost
db.port=5432
app.env=production
app.debug=false
"
```

---

## 4. Connect with the SDK

```python
import os
from zk_config_starter import ZkConfigClient, StorageMode

with ZkConfigClient(
    hosts=os.environ.get("ZK_HOSTS", "localhost:2181"),
    path="/config",
    mode=StorageMode.CHILDREN_AS_KEYS,
) as client:
    print(client.config.get_all())
```

---

## 5. Modify properties live

Change a value via ZooNavigator (click a znode → Edit) or the CLI:

```bash
docker compose exec zookeeper zkCli.sh -server localhost:2181 set /config/db.host 127.0.0.1
```

Any running `ZkConfigClient` will receive the change within milliseconds via
Kazoo's watcher mechanism — no restart required.

---

## 6. Run the integration tests

```bash
# from the project root
ZK_HOSTS=localhost:2181 pytest --run-integration
```

---

## 7. Stop and clean up

```bash
# Stop containers but keep data volumes
docker compose stop

# Stop and remove containers + volumes (full reset)
docker compose down -v
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Connection refused` on port 2181 | Run `docker compose ps` — check the `zookeeper` container is healthy. Wait ~10 s for the health check to pass. |
| ZooNavigator shows "Connection error" | The ZK container may still be starting. Refresh after ~5 s. |
| `zkCli.sh: command not found` | Use the full path: `/apache-zookeeper-*/bin/zkCli.sh` |
| `NoNodeError` in SDK | Ensure `/config` (or your custom path) was created before starting the client. |
