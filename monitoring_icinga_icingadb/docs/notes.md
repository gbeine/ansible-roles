Icinga DB runs in the official container image [icinga/icingadb](https://hub.docker.com/r/icinga/icingadb) as podman quadlet.
Icinga DB keeps no data of its own, the state and the history are in the database, the objects and events come from Redis,
so the container needs no volume. The image starts Icinga DB with `--database-auto-import`, it imports the schema into an empty database.

### Configuration

Icinga DB is configured with `icingadb_environment`, the variables `ICINGADB_<SECTION>_<OPTION>` of the
[configuration](https://icinga.com/docs/icinga-db/latest/doc/03-Configuration/), e.g. `ICINGADB_DATABASE_HOST` is `host` of `database`.
Without `/etc/icingadb/config.yml` Icinga DB reads the configuration from the environment only.
`icingadb_environment` is merged over the default of the role, `null` removes a variable of the default.
`ICINGADB_DATABASE_HOST` and `ICINGADB_REDIS_HOST` are mandatory.

```yaml
icingadb_environment:
  ICINGADB_DATABASE_TYPE: 'pgsql'
  ICINGADB_DATABASE_HOST: 'postgresql.example.org'
  ICINGADB_DATABASE_PORT: 5432
  ICINGADB_REDIS_HOST: 'redis-icingadb'
  ICINGADB_LOGGING_LEVEL: 'info'
  ICINGADB_LOGGING_OPTIONS: 'database:warn,redis:warn'
  ICINGADB_RETENTION_HISTORY_DAYS: 365
  ICINGADB_RETENTION_OPTIONS: 'state:90'
```

The default of the role, Icinga DB itself uses the port 6380 of Redis:

```yaml
ICINGADB_DATABASE_PORT: 3306
ICINGADB_DATABASE_DATABASE: 'icinga'
ICINGADB_DATABASE_USER: 'icinga'
ICINGADB_REDIS_PORT: 6379
```

Maps like `ICINGADB_LOGGING_OPTIONS` and `ICINGADB_RETENTION_OPTIONS` are `key:value` pairs separated by commas,
lists like `ICINGADB_NOTIFICATIONS_DEFAULT_RELATIONS` are values separated by commas.

### Secrets

`icingadb_secrets` is a list of podman secrets with `name`, `data` and `target`, the target is the variable of the password:
`ICINGADB_DATABASE_PASSWORD` (mandatory), `ICINGADB_REDIS_PASSWORD` and `ICINGADB_NOTIFICATIONS_PASSWORD`.
The role creates the secret, mounts it to `/run/secrets/<name>` and sets the file variable of the target,
e.g. `ICINGADB_DATABASE_PASSWORD_FILE=/run/secrets/<name>` (`PASSWORD_FILE` of icinga-go-library), Icinga DB reads the file at the start.
Passwords are neither part of the quadlet unit nor of the environment of the container.

```yaml
icingadb_secrets:
  - name: 'icingadb_database_password'
    data: "{{ vault_icingadb_database_password }}"
    target: 'ICINGADB_DATABASE_PASSWORD'
  - name: 'icingadb_redis_password'
    data: "{{ vault_icingadb_redis_password }}"
    target: 'ICINGADB_REDIS_PASSWORD'
```

Icinga DB reads the file as it is, a line break at the end would be part of the password, so the role rejects line breaks in secrets.
Icinga DB stops if a password and its file are set, neither a target nor its file variable may be set in `icingadb_environment`.

### Allowed variables

The role only allows the variables of `monitoring_icinga_icingadb__environment_allowed` and the secrets of `monitoring_icinga_icingadb__secret_variables`,
it stops before any change if unknown variables or secrets are set.
This prevents unexpected behavior by accident, e.g. by a typo or a password that has to be passed as secret.
The list is generated from the `env` tags of `internal/config/config.go` of Icinga DB v1.6.0 and the configuration of icinga-go-library v0.10.0,
it contains the options without the passwords and the file variables of the secrets.
The image has no variables of its own. The check uses the environment of the container after merging `icingadb_container`.

### Container

Ports, volumes, additional hosts (`etc_hosts`) and dependencies are changed with `icingadb_container`, it is merged over the default of the container.
The merge is not recursive, `icingadb_container.environment` replaces the environment including `icingadb_environment` and the file variables of the secrets.
Volumes are only needed for files of the TLS options (`*_CERT`, `*_KEY`, `*_CA`).
The dependencies of the quadlet unit are lists of units in `icingadb_container`: `requires`, `wants`, `after`, `part_of` and `binds_to`
are written as `Requires=`, `Wants=`, `After=`, `PartOf=` and `BindsTo=` to `[Unit]`.

```yaml
icingadb_container:
  wants: [ 'mariadb.service', 'redis-icingadb.service' ]
  after: [ 'mariadb.service', 'redis-icingadb.service' ]
```

### Validation

The role checks before any change:

- `icingadb_secrets` is a list of entries with `name`, `data` and `target` and unique names, every target is a known secret and set once,
  `ICINGADB_DATABASE_PASSWORD` is set, the names start with a letter or digit, the data are strings without line breaks
- `icingadb_environment` contains `ICINGADB_DATABASE_HOST` and `ICINGADB_REDIS_HOST`, no secret and no file variable of a secret,
  booleans (`*_TLS`, `*_INSECURE`, `ICINGADB_NOTIFICATIONS_SYNCHRONIZE_WITH_DATABASE`) are `true` or `false`, no value contains a line break
- the former single variables of the role are not set, the message names their replacement
- only allowed environment variables and secrets are set in the container

If `icingadb_container` or `icingadb_environment` is no dictionary, merging it with the default fails before anything changes.
Icinga DB checks the values at the start.

### Restart and updates

Icinga DB is restarted if it was running and a secret or the quadlet unit changed, otherwise it is started and enabled.
If the start fails, the role shows the journal of the service.
Icinga DB exits if the configuration, the database or Redis fail, the role waits until Icinga DB logged in to the database and to Redis
(it waits for Icinga 2 or syncs) and shows the journal otherwise.
Updates of the image are done by `container_update` with `icingadb_autoupdate_enabled: true` and `icingadb_autoupdate_schedule`,
without `icingadb_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

The former version of the role configured Icinga DB with single variables, they are variables of `icingadb_environment` now.
The role rejects the former variables and names their replacement.

| Former variable | Replacement |
|---|---|
| `icingadb_redis_host`, `icingadb_redis_port` | `ICINGADB_REDIS_HOST`, `ICINGADB_REDIS_PORT` |
| `icingadb_db_host`, `icingadb_db_port` | `ICINGADB_DATABASE_HOST`, `ICINGADB_DATABASE_PORT` |
| `icingadb_db_user`, `icingadb_db_name` | `ICINGADB_DATABASE_USER`, `ICINGADB_DATABASE_DATABASE` |
| `icingadb_db_pass` | secret with target `ICINGADB_DATABASE_PASSWORD` |
| `podman___update_mode` | `icingadb_autoupdate_enabled` |

Changed behavior:

- the password of the database was the podman secret `icingadb_database_password` in the environment (`type=env`),
  it is a secret of `icingadb_secrets` mounted as file now, the name is chosen freely
- the password of Redis can be set with the secret `ICINGADB_REDIS_PASSWORD`
- all options of Icinga DB can be set with `icingadb_environment`
- `/etc/localtime` and `/etc/timezone` are not mounted anymore, the time zone is set with `icingadb_timezone`
- Icinga DB is restarted if the environment or a secret changed, the role waits until Icinga DB is connected and shows the journal if it fails
- the tags are `monitoring` and `monitoring_icinga_icingadb`

### Tests

The molecule scenario `default` uses tart with the VMs `molecule-icingadb-default` with the mandatory variables and MariaDB
and `molecule-icingadb` with the options, PostgreSQL and Redis with a password.
`prepare` starts the database and Redis as containers.
`side_effect` runs the role with `icingadb_container` and `icingadb_environment` not a dictionary, an unknown variable, a boolean that is no boolean,
the password of Redis and the file variable of the password of the database in `icingadb_environment`, without `ICINGADB_REDIS_HOST`,
a secret without target, an unknown secret, without the password of the database, a former variable
and an unknown variable in `icingadb_container.environment`
and checks that it fails with the expected message and the quadlet unit is unchanged (tasks marked `expect ERROR`),
then it changes `ICINGADB_RETENTION_HISTORY_DAYS` on `molecule-icingadb`, the quadlet unit changes and Icinga DB has to restart.
`verify` checks the quadlet unit with the mounted secrets and without volume and passwords, the environment of the container with the file variables
and without passwords, the service, the schema imported into the database and that Icinga DB is connected to Redis and waits for Icinga 2.

```shell
cd monitoring_icinga_icingadb
MOLECULE_TART_IMAGE='debian' molecule test
```
