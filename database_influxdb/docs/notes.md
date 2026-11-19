InfluxDB runs in the official container image [influxdb](https://hub.docker.com/_/influxdb) as podman quadlet,
the role supports InfluxDB 1.x and 2.x and manages their databases, buckets and users.
InfluxDB 3 Core is installed with the role `database_influxdb_core`.

### Releases

The release is selected with `influxdb_release`, the default is `2.9`. `influxdb_version` is the tag of the image,
the default is `<release>-alpine`, a tag has to start with the release, e.g. `2.9.1-alpine`.

| `influxdb_release` | Version of the image | User of the image | Data in the container |
|---|---|---|---|
| `1.11`, `1.12`, `1.13` | 1.11.8, 1.12.4, 1.13.2 | `influxdb` (1500), runs as this user | `/var/lib/influxdb` |
| `2.7`, `2.8`, `2.9` | 2.7.12, 2.8.0, 2.9.1 | `influxdb` (1000), the entrypoint starts as root and changes to this user | `/etc/influxdb2`, `/var/lib/influxdb2` |

The values of the major version (user of the image, volumes, configuration file, defaults of the environment and secrets) are in `vars/influxdb1.yml` and `vars/influxdb2.yml`,
the allowed options of the configuration of every release in `vars/config-<release>.yml`, the role includes both before it checks anything.
The major version also selects the management of databases and users in `tasks/influxdb1.yml` or `tasks/influxdb2.yml`. Data of InfluxDB 1.x cannot be used by 2.x, the upgrade of the image
(`DOCKER_INFLUXDB_INIT_MODE: upgrade`) is not supported by the role.

### Configuration

InfluxDB is configured with the configuration file, `influxdb_config` is its content:

- InfluxDB 1.x reads `/etc/influxdb/influxdb.conf` (TOML), the role writes `<influxdb_home>/influxdb.conf` (root, group 1500, 0640) and mounts it read-only.
  The sections are dictionaries, `graphite`, `collectd`, `opentsdb` and `udp` are lists of tables (`[[graphite]]`).
  The default sets `http.auth-enabled: true`, the role needs the admin to manage databases and users.
- InfluxDB 2.x reads `/etc/influxdb2/config.yml`, the role writes `<influxdb_home>/etc/config.yml` (1000:1000, 0640) without a comment,
  `dasel` of the entrypoint loses the first option after a leading comment.
  The options are the flags of `influxd`, e.g. `log-level` or `http-bind-address`.

```yaml
# InfluxDB 1.x
influxdb_config:
  logging:
    level: 'warn'
  http:
    log-enabled: false
  graphite:
    - enabled: true
      database: 'graphite'
```

```yaml
# InfluxDB 2.x
influxdb_config:
  log-level: 'warn'
  storage-cache-max-memory-size: 1073741824
```

The values are TOML or YAML values, e.g. booleans, numbers and lists. `null` removes an option, also in a section or a table.
The paths of the data are set by the role and must not be set: `meta.dir`, `data.dir` and `data.wal-dir` (1.x), `bolt-path` and `engine-path` (2.x).
`influxdb_config` is merged recursively over the default, a section of 1.x keeps the options of the default that are not set.
The TOML of 1.x is written with `community.general.to_toml`, it needs the Python library `tomlkit` on the controller.

`influxdb_environment` only takes the variables of the initialization (see Initialization) and `TZ`.
The time zone is set by podman with `influxdb_timezone` (`/etc/localtime` of the container), `TZ` is not needed.

### Initialization

The image initializes InfluxDB only on the first start. The role runs the initialization once in the container `influxdb-init`
without network, with the volumes and the configuration of the quadlet unit, and removes it afterwards, also if the initialization failed.
The role detects an initialized InfluxDB by `<influxdb_home>/data/meta` (1.x) or `<influxdb_home>/data/influxd.bolt` (2.x).

- InfluxDB 1.x: `init-influxdb.sh` creates the admin `INFLUXDB_ADMIN_USER` (default `admin`) with the secret `INFLUXDB_ADMIN_PASSWORD`,
  the role sets `INFLUXDB_HTTP_AUTH_ENABLED=true` for it.
- InfluxDB 2.x: the setup creates the admin `DOCKER_INFLUXDB_INIT_USERNAME` (default `admin`), the organization `DOCKER_INFLUXDB_INIT_ORG` (mandatory),
  the bucket `DOCKER_INFLUXDB_INIT_BUCKET` (default `default`) with `DOCKER_INFLUXDB_INIT_RETENTION` and the admin token,
  the role sets `DOCKER_INFLUXDB_INIT_MODE=setup`.

```yaml
influxdb_environment:
  DOCKER_INFLUXDB_INIT_ORG: 'example'
  DOCKER_INFLUXDB_INIT_RETENTION: '52w'
```

Neither the variables nor the secrets of the initialization are part of the quadlet unit.
A failed initialization names the data directory, remove its content before the next run.

### Databases, buckets and users

The role manages databases (1.x) or buckets (2.x) and users over the HTTP API of InfluxDB after every start,
authenticated as the admin of the image. Databases, buckets, users and privileges that are not listed are not changed.
The passwords of the users are set in `influxdb_passwords`, a user whose password does not work gets the password of `influxdb_passwords`.
The admin of the image is not part of `influxdb_users`, its password is the secret of the admin.
The retention is a duration like `30d`, `12h` or `1w2d`, `INF` or `0` keeps the data infinitely.

InfluxDB 1.x:

```yaml
influxdb_release: '1.13'
influxdb_databases:
  - name: 'telegraf'
    retention: '30d'
  - name: 'app'
influxdb_users:
  - name: 'telegraf'
    grants:
      - { database: 'telegraf', privilege: 'WRITE' }
  - name: 'grafana'
    grants:
      - { database: 'telegraf', privilege: 'READ' }
      - { database: 'app', privilege: 'READ' }
  - name: 'operator'
    admin: true
influxdb_passwords:
  telegraf: "{{ vault_influxdb_telegraf_password }}"
  grafana: "{{ vault_influxdb_grafana_password }}"
  operator: "{{ vault_influxdb_operator_password }}"
```

The retention changes the default retention policy of the database, the shard duration follows the rules of InfluxDB for new policies.
`privilege` is `READ`, `WRITE` or `ALL`, the role grants the privileges of `grants` and revokes the privileges on other databases.
`admin: true` grants all privileges, `admin: false` (the default) revokes them.

InfluxDB 2.x:

```yaml
influxdb_buckets:
  - name: 'telegraf'
    retention: '30d'
  - name: 'logs'
    org: 'operations'
influxdb_users:
  - name: 'grafana'
  - name: 'operator'
    role: 'owner'
influxdb_passwords:
  grafana: "{{ vault_influxdb_grafana_password }}"
  operator: "{{ vault_influxdb_operator_password }}"
```

`org` is the organization of a bucket or user, the default is the organization of the setup, missing organizations are created.
`role` is `member` (the default) or `owner` of the organization of the user. InfluxDB knows only one role per user and organization,
the role changes it if needed, memberships in other organizations are kept.
Applications usually write and read with tokens, InfluxDB 2.x creates tokens with generated values, they are not managed by the role.

### Secrets

`influxdb_secrets` is a list of podman secrets with `name`, `data` and `target`, the name of the environment variable.
Neither a target nor its file variable may be set in `influxdb_environment`.

The secrets of the initialization are only passed to `influxdb-init`:

| Target | Passed as | |
|---|---|---|
| `DOCKER_INFLUXDB_INIT_PASSWORD` (2.x) | file, `DOCKER_INFLUXDB_INIT_PASSWORD_FILE` | mandatory |
| `DOCKER_INFLUXDB_INIT_ADMIN_TOKEN` (2.x) | file, `DOCKER_INFLUXDB_INIT_ADMIN_TOKEN_FILE` | mandatory, used by the role and by `backup_influxdb` |
| `INFLUXDB_ADMIN_PASSWORD` (1.x) | environment, `init-influxdb.sh` reads it only from there | mandatory, used by the role |

The secrets of the configuration are passed in the environment of the quadlet unit with `type=env`,
they are not part of the unit file:

| Target | Option | |
|---|---|---|
| `INFLUXDB_HTTP_SHARED_SECRET` (1.x) | `http.shared-secret` | the secret of JWT tokens |
| `INFLUXD_VAULT_TOKEN` (2.x) | `vault-token` | the token of Vault |

Neither TOML nor YAML can read a file and the images have no file variables for these options,
the environment variable of the option takes precedence over the configuration file in both images.
The options must not be set in `influxdb_config`.

```yaml
influxdb_secrets:
  - name: 'influxdb_password'
    data: "{{ vault_influxdb_password }}"
    target: 'DOCKER_INFLUXDB_INIT_PASSWORD'
  - name: 'influxdb_admin_token'
    data: "{{ vault_influxdb_admin_token }}"
    target: 'DOCKER_INFLUXDB_INIT_ADMIN_TOKEN'
```

The password and the token of the initialization only have an effect on the first start, the role uses them to manage the buckets and users,
so they have to stay the values of the initialization.

### Allowed variables

The role only allows the options of the release in `vars/config-<release>.yml`, the environment variables in `database_influxdb__environment_allowed`
and the secrets of the major version, it stops before any change if unknown options, variables or secrets are set.
This prevents unexpected behavior by accident, e.g. by a typo, an option of the other major version or a variable that has to be passed as secret.
The check of the environment uses `influxdb_environment` and the environment of the container after merging `influxdb_container`,
so variables set with `influxdb_container.environment` are checked as well.

The options are generated from `etc/config.sample.toml` of InfluxDB 1.x and from the flags in `cmd/influxd/launcher/cmd.go` of InfluxDB 2.x
of the version of the image, without the testing flags of 2.x and without the secret options.
The variables of InfluxDB (`INFLUXDB_<SECTION>_<KEY>`, `INFLUXD_<FLAG>`) and the users of `init-influxdb.sh` of 1.x (`INFLUXDB_DB`, `INFLUXDB_USER`, …) are unknown variables,
databases and users are managed with `influxdb_databases`, `influxdb_users` and `influxdb_passwords`.

### Container

The container `influxdb` mounts `<influxdb_home>/data` and `<influxdb_home>/backup` to `/backup`, 1.x also the configuration file,
2.x also `<influxdb_home>/etc` to `/etc/influxdb2` with the configuration file.
`backup_influxdb` uses the container `influxdb`, the admin token and the backup directory.
Ports, volumes and additional hosts (`etc_hosts`) are changed with `influxdb_container`, it is merged over the default of the container.
The merge is not recursive, `influxdb_container.environment` replaces the environment, use `influxdb_environment` instead.
The dependencies of the quadlet unit are lists in `influxdb_container`: `requires`, `wants`, `after`, `part_of` and `binds_to` are units,
`requires_mounts_for` are paths. They are written to `[Unit]` as `Requires=`, `Wants=`, `After=`, `PartOf=`, `BindsTo=` and `RequiresMountsFor=`.

```yaml
influxdb_container:
  requires_mounts_for: [ '/srv/influxdb' ]
```

InfluxDB listens on port 8086, the port and HTTPS follow `http.bind-address` and `http.https-enabled` (1.x)
or `http-bind-address` and `tls-cert` (2.x) of `influxdb_config`, the role uses them to reach the API on the address of the container.

### Validation

The role checks before any change:

- `influxdb_release` is supported and `influxdb_version` starts with the release
- `influxdb_secrets` is a list of entries with `name`, `data` and `target` and unique names, the mandatory secrets exist
- the mandatory variables of the initialization are set, neither a secret nor its file variable is set in `influxdb_environment`
- `influxdb_config` is a dictionary of known options, the sections of tables of 1.x are lists, the paths of the data and the secret options are not set,
  `http.auth-enabled` is `true` (1.x), the values contain no line breaks
- `influxdb_databases`, `influxdb_buckets` and `influxdb_users` are lists of entries with unique and valid names and valid retentions,
  databases only with 1.x, buckets only with 2.x, `admin` and `grants` only with 1.x, `org` and `role` only with 2.x,
  privileges and roles are known, grants only on databases of `influxdb_databases`, the admin is not in `influxdb_users`
- every user has a password in `influxdb_passwords`, `influxdb_passwords` has no passwords of unknown users and no empty passwords
- only allowed environment variables and secrets are set, the values contain no line breaks

If `influxdb_container` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Check mode

The role runs with `--check` without failing, also on a host where it never ran before.
It reports the changes of the configuration file, the secrets and the quadlet unit,
the initialization, the start and the management of the databases, buckets and users are skipped.

### Restart and updates

InfluxDB is restarted if it was running and the configuration file, a secret or the quadlet unit changed, e.g. after changing `influxdb_config`,
otherwise it is started and enabled. If the start fails, the role stops with the last lines of the journal of the service.
The role waits until `/ping` answers, shows the log of the service otherwise, and manages the databases, buckets and users afterwards.
Updates of the image are done by `container_update` with `influxdb_autoupdate_enabled: true` and `influxdb_autoupdate_schedule`,
without `influxdb_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

The former role installed InfluxDB 2 or InfluxDB 3 Core with `influxdb_version` (2 or 3):

- InfluxDB 3 Core is installed with the role `database_influxdb_core`.
- `influxdb_version: 2` is replaced by `influxdb_release`, e.g. `2.9`, `influxdb_version` is the tag of the image now, `influxdb_tag` is removed.
- `influxdb_username`, `influxdb_org`, `influxdb_bucket` and `influxdb_retention` are replaced by `DOCKER_INFLUXDB_INIT_USERNAME`, `DOCKER_INFLUXDB_INIT_ORG`,
  `DOCKER_INFLUXDB_INIT_BUCKET` and `DOCKER_INFLUXDB_INIT_RETENTION` in `influxdb_environment`.
- `influxdb_password` and `influxdb_admin_token` are replaced by the secrets `DOCKER_INFLUXDB_INIT_PASSWORD` and `DOCKER_INFLUXDB_INIT_ADMIN_TOKEN`,
  keep the former values, the role uses the token.
- `influxdb_expose` and `influxdb_publish` are removed, the port 8086 is not published by default anymore, set `influxdb_container.publish` if needed.
- `influxdb_use_podman` is removed, the handler `Restart InfluxDB container` is removed.
- The directories `etc`, `data` and `backup` of `influxdb_home` stay.
- `/etc/localtime` and `/etc/timezone` are not mounted anymore, the time zone is set by podman with `influxdb_timezone`.
- `podman___update_mode` is not evaluated anymore, the role neither stops the container nor pulls the image or recreates the container.
- Buckets and users are new with `influxdb_buckets`, `influxdb_users` and `influxdb_passwords`, InfluxDB 1.x is new.
- The tag `database_influxdb` stays, the tag `database` is added.

Changes of the configuration since the first version of this role:

- The options are set in `influxdb_config` instead of the environment:
  `INFLUXDB_<SECTION>_<KEY>` of 1.x is `<section>.<key>` with `-` instead of `_` in the key, e.g. `INFLUXDB_LOGGING_LEVEL` is `logging: { level: … }`,
  `INFLUXDB_GRAPHITE_0_ENABLED` is the first entry of the list `graphite`, `INFLUXDB_HTTP_AUTH_ENABLED` is `http.auth-enabled`.
  `INFLUXD_<FLAG>` of 2.x is the flag with `-` instead of `_` in lower case, e.g. `INFLUXD_LOG_LEVEL` is `log-level`.
- `DOCKER_INFLUXDB_INIT_MODE` is set by the role, `TZ` is not set anymore.
- The initialization runs in `influxdb-init`, its variables and secrets are not part of the quadlet unit anymore.
- `wants`, `after`, `part_of`, `binds_to` and `requires_mounts_for` of `influxdb_container` are new.

### Tests

The molecule scenario `default` runs the role in three [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
Three platforms instead of two test both major versions. The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-influxdb-default` | InfluxDB 2.9 with the mandatory variables, the organization of the setup and the secrets of the setup |
| `molecule-influxdb` | InfluxDB 2.9 with IPv6, labels, dependencies, `log-level`, an option removed with `null`, buckets with retention, a second organization, a member and an owner |
| `molecule-influxdb-1` | InfluxDB 1.13 with the shared secret in the environment, databases with retention, users with `WRITE`, `READ` and `ALL`, an admin and a password with a single quote |

`prepare` creates the podman network and pulls the images, `check` runs `converge` with `--check` on the new VMs.
`side_effect` runs the role with invalid values of the release, the secrets, the environment, the configuration of both major versions,
the databases, buckets and users and checks that it fails with the expected message and that the quadlet unit and the configuration file are unchanged
(tasks marked `expect ERROR`).
On `molecule-influxdb` and `molecule-influxdb-1` it changes the log level, adds a bucket or database and changes a password,
only the configuration file changes, the service has to restart and the role has to create the bucket or database and change the password.
`molecule-influxdb-default` runs again without a change and must not restart. The initialization must not run again.
`verify` checks the quadlet unit with the volumes and the secrets without the variables and secrets of the initialization,
the configuration file, the log level as InfluxDB reads it, that `influxdb-init` was removed,
the service, the addresses and the environment of the container, the owner of the data directory and `/ping`.
For 2.x it checks the buckets and their retention, the sign in of the users with their passwords and with a wrong password,
the owners of the organization and writes and queries a point with the admin token.
For 1.x it checks the databases and their retention, the admins and that `writer` may only write, `reader` only read from `telegraf`
and write to `app`, and that a wrong password is rejected.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd database_influxdb
MOLECULE_TART_IMAGE='debian' molecule test
```
