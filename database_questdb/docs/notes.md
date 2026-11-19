QuestDB runs in the container image [questdb/questdb](https://hub.docker.com/r/questdb/questdb) (`latest` by default, `questdb_version` sets the tag) as podman quadlet.
The entrypoint of the image starts as root, fixes the owner of the data and runs QuestDB as the user `questdb` (uid 10001).
QuestDB listens on port 9000 (HTTP API and web console), 8812 (PostgreSQL wire protocol) and 9009 (InfluxDB line protocol over TCP).
`questdb_home` is the data directory of QuestDB, owned by the user `questdb` and mounted to `/var/lib/questdb`,
the role `backup_questdb` creates a checkpoint in the container `questdb` and backs up this directory.

### Configuration

QuestDB reads `conf/server.conf` below `questdb_home`, a file of Java properties. The image copies its own `server.conf` only if the file is missing,
so the file written by the role stays. `questdb_config` is a flat dictionary of the keys of `server.conf`,
see the [configuration of QuestDB](https://questdb.com/docs/configuration/), it is merged over the default of the role:

- a string or a number writes `key=value`, backslashes are escaped
- `true` and `false` write `true` and `false`
- a list writes the elements separated by commas, e.g. the CPUs of `shared.network.worker.affinity`
- `null` removes the key, QuestDB uses its default then

The default writes the active keys of the `server.conf` of the image, `query.timeout=1m` and `cairo.sql.copy.root=import`.
The role sets `config.validation.strict=false` and the files of the secrets (see Secrets), these keys must not be set in `questdb_config`.

```yaml
questdb_config:
  http.user: 'admin'
  pg.user: 'admin'
  telemetry.enabled: false
  shared.worker.count: 2
```

Without `http.user` the HTTP API and the web console need no authentication.
With `http.user` the role `backup_questdb` cannot create the checkpoint anymore, it calls `/exec` without authentication.
The environment takes precedence over `server.conf` in QuestDB (`QDB_<KEY>`), the keys of QuestDB are therefore not allowed in `questdb_environment`.

### Secrets

`questdb_secrets` is a list of podman secrets with `name`, `data` and `target`, the target is the key of `server.conf`.
The role creates the secret, mounts it to `/run/secrets/<name>` for the user of the image and writes `<key>.file=/run/secrets/<name>` to `server.conf`,
QuestDB reads the sensitive keys from this file (`getSecretFilePath` in `PropServerConfiguration.java` of QuestDB 10.2.0).
The passwords are neither part of `server.conf`, the quadlet unit nor of the environment of the container.

The targets are:

- `pg.password`, the password of `pg.user` (`admin`) for the PostgreSQL wire protocol, required, without it QuestDB uses the well known password `quest`
- `pg.readonly.password`, the password of the read only user, needed with `pg.readonly.user.enabled: true`
- `http.password`, the password of `http.user` for the HTTP API and the web console, `http.user` and `http.password` are only set together

```yaml
questdb_secrets:
  - name: 'questdb_pg_password'
    data: "{{ vault_questdb_pg_password }}"
    target: 'pg.password'
  - name: 'questdb_http_password'
    data: "{{ vault_questdb_http_password }}"
    target: 'http.password'
```

The strict validation of QuestDB (`config.validation.strict=true`) does not know the keys `<key>.file` and stops QuestDB,
so the role sets `config.validation.strict=false`, unknown keys are rejected by the role before any change.

### Allowed variables

The role only allows the keys of `database_questdb__config_allowed` in `questdb_config`, generated from `PropertyKey.java` of [QuestDB](https://github.com/questdb/questdb) 10.2.0
without the debug keys and the sensitive keys, the variables of `database_questdb__environment_allowed` in the environment
and the secrets with a target in `database_questdb__secrets_allowed`, it stops before any change if unknown keys, variables or secrets are set.
This prevents unexpected behavior by accident, e.g. by a typo or a password in plain text.
The check of the environment uses the environment of the container after merging `questdb_container`,
so variables set with `questdb_container.environment` are checked as well.

`questdb_environment` takes the variables of `docker-entrypoint.sh` of the image: `JVM_PREPEND`, `DO_CHOWN`, `RUN_AS_ROOT`, `QUESTDB_UID`, `QUESTDB_GID`,
`IGNORE_DATA_ROOT_MOUNT_CHECK`, `DEFAULT_LOCAL_DIRS`, the variables of the profiler `PROFILER_*` and `PROFILE_NAME`, and `TZ`,
there is no default, without `questdb_environment` the quadlet unit has no environment.

New versions of QuestDB may add keys, the list is generated again from `PropertyKey.java`.

### Container

Ports, volumes, additional hosts (`etc_hosts`) and dependencies are changed with `questdb_container`, it is merged over the default of the container.
The merge is not recursive, `questdb_container.volumes` replaces the data directory,
`questdb_container.environment` replaces the environment including `questdb_environment`, use `questdb_environment` instead.
Options of the JVM, e.g. the heap, are set with `JVM_PREPEND` in `questdb_environment`.
The time zone of the container is set by podman with `questdb_timezone`.
For a reverse proxy, e.g. Traefik, the labels are set with `questdb_labels`, the web console listens on port 9000.
After the start the role waits until port 9000 is open, so roles depending on QuestDB can use it.

The dependencies of the quadlet unit are set with `requires`, `wants`, `after`, `part_of`, `binds_to` and `requires_mounts_for`
in `questdb_container`, the role writes them to `[Unit]` as `Requires=`, `Wants=`, `After=`, `PartOf=`, `BindsTo=` and `RequiresMountsFor=`:

```yaml
questdb_container:
  wants: [ 'network-online.target' ]
  after: [ 'network-online.target' ]
  requires_mounts_for: [ '/opt/questdb' ]
```

### Validation

The role checks before any change:

- `questdb_secrets` is a list of entries with `name`, `data` and `target` and unique names, the secret `pg.password` exists
- `questdb_config` is a dictionary of known keys, it contains neither a secret nor a key set by the role,
  the values are strings without line breaks, numbers, booleans, lists of them or `null`
- `http.user` and the secret `http.password` are set together, `pg.readonly.user.enabled: true` has the secret `pg.readonly.password`
- only allowed environment variables without line breaks and secrets are set in the container

If `questdb_container` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Check mode

The role runs with `--check` also on a host where it never ran before and compares `server.conf`, the secrets and the quadlet unit.
QuestDB is not started or restarted and the role does not wait for the port in check mode.

### Restart and updates

QuestDB is restarted if it was running and `server.conf`, a secret or the quadlet unit changed, otherwise it is started and enabled.
A failed start reports the journal of the service.
Updates of the image are done by `container_update` with `questdb_autoupdate_enabled: true` and `questdb_autoupdate_schedule`,
without `questdb_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

The keys of QuestDB are set in `server.conf` with `questdb_config` instead of `QDB_<KEY>` in `questdb_environment`,
the key is the variable without `QDB_`, lower case, with dots instead of underscores, e.g.:

- `QDB_HTTP_USER` is `http.user`
- `QDB_PG_USER` is `pg.user`
- `QDB_PG_READONLY_USER_ENABLED` is `pg.readonly.user.enabled`
- `QDB_TELEMETRY_ENABLED` is `telemetry.enabled`
- `QDB_SHARED_WORKER_COUNT` is `shared.worker.count`

Values are no strings anymore, e.g. `'false'` is `false`. Keys with a hyphen, e.g. `http.keep-alive.timeout`, can be set now.
The targets of the secrets are the keys: `QDB_PG_PASSWORD` is `pg.password`, `QDB_PG_READONLY_PASSWORD` is `pg.readonly.password`, `QDB_HTTP_PASSWORD` is `http.password`,
the role writes `<key>.file` to `server.conf` instead of setting `QDB_<KEY>_FILE`.
`TZ` is not set by default anymore, the time zone is set by podman with `questdb_timezone`.
The `server.conf` of the image is replaced by the file of the role, changes made in the file by hand are lost.

Changes of former versions:
The former role had no configuration and no secrets, QuestDB ran with the well known password `quest` of the PostgreSQL user `admin`.
Now the secret `pg.password` is required, set it before running the role, clients of the PostgreSQL wire protocol need the new password.
`/etc/localtime` and `/etc/timezone` are not mounted anymore.
The data directory and the name of the container `questdb` stay for `backup_questdb`.
`podman___update_mode` is not evaluated anymore, the role neither stops the container nor pulls the image or recreates the container.
The tag `database_questdb` stays, the tag `database` is added.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-questdb-default` | Only the mandatory variables and the secret `pg.password`, no environment |
| `molecule-questdb` | IPv6, labels, dependencies, `JVM_PREPEND`, `questdb_config` with `http.user`, `telemetry.enabled` and `null`, the secrets `pg.password` and `http.password` |

`prepare` creates the podman network and pulls the images, `check` runs `converge` with `--check` on the fresh VMs.
`side_effect` runs the role with invalid variables and checks that it fails with the expected message and the quadlet unit and `server.conf` are unchanged
(tasks marked `expect ERROR`): `questdb_container` and `questdb_config` not a dictionary, a secret without `target`, without `pg.password`,
`pg.password`, `http.password.file` and `config.validation.strict` in `questdb_config`, `QDB_PG_PASSWORD` and a line break in the environment,
`http.user` without password, the read only user without password, an unknown key, a line break in a value, an unknown variable in `questdb_container.environment` and an unknown secret.
Then it waits until QuestDB answers and runs the role with `side_effect.role_vars` of the test case: `molecule-questdb` sets `shared.worker.count`,
only `server.conf` changes and QuestDB has to restart, `molecule-questdb-default` runs again without a change and must not restart.
`verify` checks the quadlet unit with the volume, the mounted secrets and the dependencies, without `TZ`, `QDB_*` and on `molecule-questdb-default` without environment,
the service, the addresses, `server.conf` with its owner, its mode and its lines, the data directory, the HTTP authentication,
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
