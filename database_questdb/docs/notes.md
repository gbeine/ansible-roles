QuestDB runs in the container image [questdb/questdb](https://hub.docker.com/r/questdb/questdb) (`latest` by default, `questdb_version` sets the tag) as podman quadlet.
The entrypoint of the image starts as root, fixes the owner of the data and runs QuestDB as the user `questdb` (uid 10001).
QuestDB listens on port 9000 (HTTP API and web console), 8812 (PostgreSQL wire protocol) and 9009 (InfluxDB line protocol over TCP).
`questdb_home` is the data directory of QuestDB, owned by the user `questdb` and mounted to `/var/lib/questdb`,
the role `backup_questdb` creates a checkpoint in the container `questdb` and backs up this directory.

### Configuration

QuestDB is configured completely with environment variables in `questdb_environment`, merged over the default of the role, which sets `TZ` to `questdb_timezone`.
Every key of `server.conf` is set with `QDB_<KEY>`, the dots of the key are replaced by underscores and the letters are upper case,
e.g. `cairo.commit.lag` is `QDB_CAIRO_COMMIT_LAG`, see the [configuration of QuestDB](https://questdb.com/docs/configuration/).
Values are strings, e.g. `'false'`. The keys `http.keep-alive.timeout` and `http.keep-alive.max` contain a hyphen and cannot be set as environment variable.

```yaml
questdb_environment:
  QDB_HTTP_USER: 'admin'
  QDB_PG_USER: 'admin'
  QDB_TELEMETRY_ENABLED: 'false'
  QDB_SHARED_WORKER_COUNT: '2'
```

Without `QDB_HTTP_USER` the HTTP API and the web console need no authentication.
With `QDB_HTTP_USER` the role `backup_questdb` cannot create the checkpoint anymore, it calls `/exec` without authentication.

### Secrets

`questdb_secrets` is a list of podman secrets with `name`, `data` and `target`, the name of the environment variable, e.g. `QDB_PG_PASSWORD`.
The role creates the secret, mounts it to `/run/secrets/<name>` for the user of the image and sets the file variable of the target,
QuestDB reads the sensitive keys from `QDB_<KEY>_FILE`, so passwords are neither part of the quadlet unit nor of the environment of the container.

| Target | File variable set by the role | Description |
|---|---|---|
| `QDB_PG_PASSWORD` | `QDB_PG_PASSWORD_FILE` | Password of `QDB_PG_USER` (`admin`) for the PostgreSQL wire protocol, required |
| `QDB_PG_READONLY_PASSWORD` | `QDB_PG_READONLY_PASSWORD_FILE` | Password of the read only user, with `QDB_PG_READONLY_USER_ENABLED: 'true'` |
| `QDB_HTTP_PASSWORD` | `QDB_HTTP_PASSWORD_FILE` | Password of `QDB_HTTP_USER` for the HTTP API and the web console |

`QDB_PG_PASSWORD` is required, without it QuestDB uses the well known password `quest`.
`QDB_HTTP_USER` and `QDB_HTTP_PASSWORD` are only set together, `QDB_PG_READONLY_USER_ENABLED: 'true'` needs `QDB_PG_READONLY_PASSWORD`.
The targets are the keys of `database_questdb__secret_files`. Neither a target nor its file variable may be set in `questdb_environment`.

```yaml
questdb_secrets:
  - name: 'questdb_pg_password'
    data: "{{ vault_questdb_pg_password }}"
    target: 'QDB_PG_PASSWORD'
  - name: 'questdb_http_password'
    data: "{{ vault_questdb_http_password }}"
    target: 'QDB_HTTP_PASSWORD'
```

### Allowed variables

The role only allows the environment variables in `database_questdb__environment_allowed` and the secrets with a target in `database_questdb__secret_files`,
it stops before any change if unknown variables or secrets are set.
This prevents unexpected behavior by accident, e.g. by a typo or a variable that has to be passed as secret.
The check uses the environment and the secrets of the container after merging `questdb_container`,
so variables set with `questdb_container.environment` are checked as well.

Allowed environment variables:

- `QDB_<KEY>` for every key of `PropertyKey.java` of [QuestDB](https://github.com/questdb/questdb) 10.2.0,
  without the debug keys, the sensitive keys and the keys with a hyphen
- the variables of `docker-entrypoint.sh` of the image: `JVM_PREPEND`, `DO_CHOWN`, `RUN_AS_ROOT`, `QUESTDB_UID`, `QUESTDB_GID`,
  `IGNORE_DATA_ROOT_MOUNT_CHECK`, `DEFAULT_LOCAL_DIRS` and the variables of the profiler `PROFILER_*` and `PROFILE_NAME`,
  without the internal `QDB_PACKAGE` and `QUESTDB_DATA_DIR`, which depends on the volume
- the file variables of the secrets, set by the role, and `TZ`

New versions of QuestDB may add keys, the list is generated again from `PropertyKey.java`.

### Container

Ports, volumes, additional hosts (`etc_hosts`) and dependencies (`requires`) are changed with `questdb_container`, it is merged over the default of the container.
The merge is not recursive, `questdb_container.volumes` replaces the data directory,
`questdb_container.environment` replaces the environment including `questdb_environment`, use `questdb_environment` instead.
Options of the JVM, e.g. the heap, are set with `JVM_PREPEND` in `questdb_environment`.
For a reverse proxy, e.g. Traefik, the labels are set with `questdb_labels`, the web console listens on port 9000.
After the start the role waits until port 9000 is open, so roles depending on QuestDB can use it.

### Validation

The role checks before any change:

- `questdb_secrets` is a list of entries with `name`, `data` and `target` and unique names, the secret `QDB_PG_PASSWORD` exists
- `QDB_HTTP_USER` and the secret `QDB_HTTP_PASSWORD` are set together, `QDB_PG_READONLY_USER_ENABLED: 'true'` has the secret `QDB_PG_READONLY_PASSWORD`
- neither a secret nor its file variable is set in `questdb_environment`
- only allowed environment variables and secrets are set in the container

If `questdb_container` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Restart and updates

QuestDB is restarted if it was running and a secret or the quadlet unit changed, e.g. after changing `questdb_environment`, otherwise it is started and enabled.
Updates of the image are done by `container_update` with `questdb_autoupdate_enabled: true` and `questdb_autoupdate_schedule`,
without `questdb_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

The former role had no configuration and no secrets, QuestDB ran with the well known password `quest` of the PostgreSQL user `admin`.
Now the secret `QDB_PG_PASSWORD` is required, set it before running the role, clients of the PostgreSQL wire protocol need the new password.
`/etc/localtime` and `/etc/timezone` are not mounted anymore, the timezone is set with `TZ` and the timezone of the container.
The data directory and the name of the container `questdb` stay for `backup_questdb`.
`podman___update_mode` is not evaluated anymore, the role neither stops the container nor pulls the image or recreates the container.
The tag `database_questdb` stays, the tag `database` is added.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-questdb-default` | Only the mandatory variables and the secret `QDB_PG_PASSWORD`, HTTP without authentication |
| `molecule-questdb` | IPv6, labels, `QDB_TELEMETRY_ENABLED`, `QDB_HTTP_USER` with the secret `QDB_HTTP_PASSWORD` and the secret `QDB_PG_PASSWORD` |

`prepare` creates the podman network and pulls the image of QuestDB and the image of PostgreSQL as client of `verify`.
`side_effect` runs the role with `questdb_container` not a dictionary, a secret without `target`, without the secret `QDB_PG_PASSWORD`,
`QDB_PG_PASSWORD` and `QDB_HTTP_PASSWORD_FILE` in the environment, `QDB_HTTP_USER` without password, the read only user without password,
an unknown key `QDB_FOO`, an unknown environment variable in `questdb_container.environment` and an unknown secret
and checks that it fails with the expected message and the quadlet unit is unchanged (tasks marked `expect ERROR`),
then it waits until QuestDB answers on `molecule-questdb`, shows the log of the service otherwise, and changes `QDB_SHARED_WORKER_COUNT`,
the quadlet unit changes and QuestDB has to restart.
`verify` checks the quadlet unit with the volume and the mounted secrets, the service, the addresses and the environment of the container
with the file variables set by the role and without passwords and the data directory owned by the user of the image.
It runs a query over HTTP, without authentication on `molecule-questdb-default`, with the user and the password of the secret on `molecule-questdb`,
where a query without authentication has to fail, and a query with `psql` over the PostgreSQL wire protocol with the password of the secret.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd database_questdb
MOLECULE_TART_IMAGE='debian' molecule test
```
