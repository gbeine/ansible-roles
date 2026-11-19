PostgreSQL runs in the official container image [postgres](https://hub.docker.com/_/postgres) (Alpine variant) as podman quadlet.
The role creates accounts, databases, privileges and replication slots with the modules of [community.postgresql](https://docs.ansible.com/ansible/latest/collections/community/postgresql/),
which need `libpq5` and `python3-psycopg2` on the host, the role installs both packages.

### Versions

| `postgresql_version` | Image tag | Status |
|---|---|---|
| `18` (default) | `18-alpine` | release |
| `19` | `19rc1-alpine` | release candidate, the role shows a warning |

`postgresql_tag` overrides the tag of the image, e.g. to pin a minor release (`18.1-alpine`).
Versions before 18 are not supported: since PostgreSQL 18 the image keeps the data in `/var/lib/postgresql/<major>/docker`,
older images use `/var/lib/postgresql/data`.

The data of the cluster is in `<postgresql_home>/data/<major>/docker` on the host.
The script `postgresql` of `backup_scripts` dumps the databases with `podman exec postgresql pg_dump` to the host.

### Upgrade to a new major version

A new major version uses a new, empty data directory.
The role fails before it changes anything if `<postgresql_home>/data` contains the data of another version but not of `postgresql_version`.
To upgrade, e.g. from 18 to 19:

1. Stop the service: `systemctl stop postgresql`.
2. Upgrade the data, e.g. with the image [pgautoupgrade](https://github.com/pgautoupgrade/docker-pgautoupgrade) or `pg_upgrade` in a container that contains both versions,
   from `<postgresql_home>/data/18/docker` to `<postgresql_home>/data/19/docker`,
   or create a dump with `pg_dumpall` before and restore it into the new cluster after the role created it.
3. Set `postgresql_version: 19` and run the role.
4. Remove `<postgresql_home>/data/18` once the new cluster works.

### Configuration

`postgresql.conf` contains all parameters of the version with their description and default, generated from `postgresql.conf.sample` of the PostgreSQL sources
into `vars/settings-<major>.yml`.
Parameters set with `postgresql_config` are active, all others stay commented out with their default.
`true` and `false` are written as `on` and `off`, numbers as numbers and strings as quoted strings, `null` removes a parameter, it stays commented out with its default.

```yaml
postgresql_config:
  max_connections: 200
  shared_buffers: '1GB'
  ssl: true
  ssl_cert_file: '/var/lib/postgresql/server.crt'
  ssl_key_file: '/var/lib/postgresql/server.key'
  wal_level: 'logical'
  max_wal_senders: 10
  shared_preload_libraries: 'pg_stat_statements'
  pg_stat_statements.track: 'all'
```

Parameters with a dot in the name are parameters of extensions, they are written to the section `CUSTOMIZED OPTIONS`.
The parameters have no types in the sample, values of the wrong type are rejected by PostgreSQL at the start.

Without `postgresql_config` the role writes the same active parameters as `initdb` of the image into a new cluster:
`listen_addresses = '*'`, `max_connections = 100`, `shared_buffers = 128MB`, `dynamic_shared_memory_type = posix`, `max_wal_size = 1GB`, `min_wal_size = 80MB`,
`log_timezone` and `timezone` set to `postgresql_timezone`, `datestyle = 'iso, mdy'`, the locales `en_US.utf8` and `default_text_search_config = 'pg_catalog.english'`.
`postgresql_config` is merged over these defaults.

`postgresql.conf`, `pg_hba.conf` and `pg_ident.conf` are written after the initialization and before the start of the service.

### Standby

With `postgresql_configure_from_primary: true` the role does not initialize the cluster, does not write the configuration and does not create accounts, databases, privileges and slots,
they are replicated from the primary, e.g. with `pg_basebackup` in `postgresql_container.exec_start_pre`.
The standby parameters, e.g. `primary_conninfo`, are part of the replicated configuration of the primary or are set with `ALTER SYSTEM` on the standby.
A standby needs no secret `POSTGRES_PASSWORD`.

### Access

`pg_hba.conf` is generated from `postgresql_hba`, a list of entries with `type`, `database`, `user`, optional `address` and `method`.
The default allows local connections without password and connections from everywhere with `scram-sha-256`.

### Secrets

`postgresql_secrets` is a list of podman secrets with `name`, `data` and `target`, the only target is `POSTGRES_PASSWORD`, the password of the user `postgres`, it is required.
The image reads it from the file of `POSTGRES_PASSWORD_FILE` when it creates the cluster, the role manages the accounts with it.
initdb reads the password as one line, it must not be empty and must not contain line breaks.

```yaml
postgresql_secrets:
  - name: 'postgresql_password'
    data: "{{ vault_postgresql_password }}"
    target: 'POSTGRES_PASSWORD'
```

The secret is only mounted in the container of the initialization (`/run/secrets/<name>`, owned by `postgres`), it is never part of the quadlet unit.
Changing the password later does not change the password of an existing cluster.

### Initialization

The image creates the cluster only if the data directory of the version contains no `PG_VERSION`.
The role runs the initialization once in the container `postgresql-init` without network, with the secret and `postgresql_environment`,
waits for `PostgreSQL init process complete; ready for start up.` in its log and removes the container, also if the initialization failed.
A failed initialization names the data directory whose content has to be removed before the next run.
The quadlet unit contains neither the secret nor the variables of the initialization.

### Accounts, databases, privileges and replication slots

- `postgresql_accounts` supports the options `name`, `comment` and `attributes` (`role_attr_flags`), see the [postgresql_user module](https://docs.ansible.com/ansible/latest/collections/community/postgresql/postgresql_user_module.html).
  The password of every account is taken from `postgresql_passwords`, a mapping of account names to passwords.
- `postgresql_databases` supports `name`, `owner`, `comment`, `encoding`, `lc_collate`, `lc_ctype`, `locale_provider`, `icu_locale` and `template`,
  see the [postgresql_db module](https://docs.ansible.com/ansible/latest/collections/community/postgresql/postgresql_db_module.html).
- `postgresql_privileges` supports `database`, `type` (default `table`), `objects`, `privs`, `roles` and `schema`,
  see the [postgresql_privs module](https://docs.ansible.com/ansible/latest/collections/community/postgresql/postgresql_privs_module.html).
- `postgresql_slots` supports `name` and `type` (`physical` or `logical`), see the [postgresql_slot module](https://docs.ansible.com/ansible/latest/collections/community/postgresql/postgresql_slot_module.html).

```yaml
postgresql_accounts:
  - name: 'nextcloud'
    comment: 'Nextcloud'
postgresql_passwords:
  nextcloud: "{{ vault_postgresql_nextcloud_password }}"
postgresql_databases:
  - name: 'nextcloud'
    owner: 'nextcloud'
postgresql_privileges:
  - database: 'nextcloud'
    type: 'database'
    privs: 'ALL'
    roles: 'nextcloud'
```

The role waits until PostgreSQL answers before it manages the accounts, so roles depending on PostgreSQL can use it.

### Container

Ports, volumes, additional hosts (`etc_hosts`), commands before the start (`exec_start_pre`) and dependencies are changed with `postgresql_container`,
it is merged over the default of the container. The merge is not recursive, `publish` and `volumes` replace the values of the default completely.
The container only mounts the data, the time zone is set by podman with `postgresql_timezone` (`/etc/localtime`).

The dependencies of the quadlet unit are set with `requires`, `wants`, `after`, `part_of`, `binds_to` and `requires_mounts_for`
in `postgresql_container`, the role writes them to `[Unit]` as `Requires=`, `Wants=`, `After=`, `PartOf=`, `BindsTo=` and `RequiresMountsFor=`:

```yaml
postgresql_container:
  wants: [ 'network-online.target' ]
  after: [ 'network-online.target' ]
  requires_mounts_for: [ '/opt/postgresql' ]
```

### Allowed variables

`postgresql_environment` takes the variables of the initialization of the image, `POSTGRES_INITDB_ARGS` and `POSTGRES_INITDB_WALDIR`,
they are only passed to `postgresql-init`, there is no default. The image reads no variable after the initialization,
so the quadlet unit has no environment and no secrets, `postgresql_container.environment` and `postgresql_container.secrets` are rejected.
The role stops before any change if other variables are set, e.g. `POSTGRES_PASSWORD` in plain text, `PGDATA` or `POSTGRES_USER`,
which would break the data directory or the management of the accounts by the role.
This prevents unexpected behavior by accident.

### Validation

The role checks before any change:

- `postgresql_version` is a supported version
- `postgresql_secrets` is a list of entries with `name`, `data` and `target` and unique names, the secret `POSTGRES_PASSWORD` exists (except on a standby),
  the password is not empty and contains no line breaks
- neither a secret nor `POSTGRES_PASSWORD_FILE` is set in `postgresql_environment`, only the variables of the initialization are set, without line breaks
- `postgresql_container` sets neither `environment` nor `secrets`
- every key of `postgresql_config` is a parameter of the version or contains a dot, the values are strings without line breaks, numbers, booleans or `null`
- the entries of `postgresql_accounts`, `postgresql_databases` and `postgresql_slots` have `name`, the names contain only letters, digits and `_ . $ -`
- every account has a password in `postgresql_passwords`
- every entry of `postgresql_hba` has `type`, `database`, `user` and `method`
- the data directory contains no data of another major version (see Upgrade to a new major version)

The message only names the failing checks.
If `postgresql_container` is no dictionary, merging it with the default fails before anything changes.

### Check mode

The role runs with `--check` also on a host where it never ran before and compares the configuration files, the secrets and the quadlet unit.
On an initialized host with `python3-psycopg2` it also compares the accounts, databases, privileges and slots.
The initialization and the start do not run in check mode.

### Restart and updates

PostgreSQL is restarted if it was running and `postgresql.conf`, `pg_hba.conf`, `pg_ident.conf` or the quadlet unit changed, otherwise it is started and enabled.
A failed start reports the journal of the service.
Updates of the image within the major version are done by `container_update` with `postgresql_autoupdate_enabled: true` and `postgresql_autoupdate_schedule`, without `postgresql_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

| `postgresql_use_podman` | removed, only podman |
| `postgresql_podman_tag` | `postgresql_tag` |
| `postgresql_port`, `postgresql_max_connections`, `postgresql_shared_buffers`, `postgresql_dynamic_shared_memory_type`, `postgresql_unix_socket_directories` | `postgresql_config` |
| `postgresql_enable_ssl`, `postgresql_ssl_ca_file`, `postgresql_ssl_cert_file`, `postgresql_ssl_key_file` | `postgresql_config` with `ssl`, `ssl_ca_file`, `ssl_cert_file`, `ssl_key_file` |
| `postgresql_enable_wal` and `postgresql_wal_*`, `postgresql_fsync`, `postgresql_synchronous_commit`, `postgresql_checkpoint_*`, `postgresql_*_wal_size`, `postgresql_archive_*`, `postgresql_commit_*` | `postgresql_config` with the parameter names |
| `postgresql_enable_replication_sending` and `postgresql_max_wal_senders`, `postgresql_max_replication_slots`, `postgresql_wal_keep_size`, `postgresql_max_slot_wal_keep_size`, `postgresql_idle_replication_slot_timeout`, `postgresql_wal_sender_timeout`, `postgresql_track_commit_timestamp` | `postgresql_config` with the parameter names |
| `postgresql_enable_replication_standby` and `postgresql_primary_conninfo`, `postgresql_primary_slot_name`, `postgresql_hot_standby` | `postgresql_config` with the parameter names |
| `postgresql_log_timezone`, `postgresql_datestyle`, `postgresql_lc_*`, `postgresql_default_text_search_config` | `postgresql_config` with the parameter names |
| `podman___update_mode` | `postgresql_autoupdate_enabled` |
| `postgresql_publish` | `postgresql_container.publish` |
| the secret as environment variable `POSTGRES_PASSWORD` | the secret mounted as file in `postgresql-init` with `POSTGRES_PASSWORD_FILE` |
| tag `database_postgresql` | tags `database` and `database_postgresql` |
| versions before 18 | not supported |
| `postgresql_password` | `postgresql_secrets` with the target `POSTGRES_PASSWORD` |
| `postgresql_settings` | `postgresql_config` |

Changed behavior and fixed bugs:

- The cluster is created in the container `postgresql-init`, the quadlet unit contains neither the secret nor `POSTGRES_PASSWORD_FILE` anymore.
  The secret `postgres_password` of former versions is not created and not removed, remove it with `podman secret rm postgres_password`.
- `postgresql.conf`, `pg_hba.conf` and `pg_ident.conf` are written before the first start, a new cluster is no longer restarted after the first start.
- `/etc/localtime` and `/etc/timezone` are not mounted anymore, the time zone is set by podman with `postgresql_timezone`.
- `<postgresql_home>/backup` is neither created nor mounted anymore, `backup_scripts` streams the dumps to the host, the role does not remove the directory.
- `null` in the configuration wrote `'None'`, now it removes the parameter.
- The role has no own filter `fill_up_to` anymore, it uses `whitespaces_fill_up_to` of `common_filters`.

### Tests

The molecule scenario `default` runs the role in three [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.

| Platform | Test case |
|---|---|
| `molecule-postgresql-default` | PostgreSQL 18 with the mandatory variables and the secret only |
| `molecule-postgresql` | PostgreSQL 18 with `POSTGRES_INITDB_ARGS`, `postgresql_config` with `null`, accounts, databases, privileges, slots and dependencies |
| `molecule-postgresql-19` | The release candidate of PostgreSQL 19 with the same options |

`prepare` creates the podman network and pulls the image, `check` runs `converge` with `--check` on the fresh VMs.
`side_effect` runs the role with invalid variables and checks that it fails with the expected message and the quadlet unit and `postgresql.conf` are unchanged
(tasks marked `expect ERROR`): `postgresql_container` not a dictionary, a secret without `target`,
without the secret `POSTGRES_PASSWORD`, a line break in the password, `POSTGRES_PASSWORD_FILE` and `POSTGRES_USER` in `postgresql_environment`,
a line break in `postgresql_environment`, a variable and a secret in `postgresql_container`, an unknown parameter, a line break in a value of `postgresql_config`,
an account without password, an invalid name of an account and an entry of `postgresql_hba` without method.
Then it runs the role with `side_effect.role_vars` of the test case: `molecule-postgresql` changes `max_connections` and has to restart,
the other platforms run again without a change and must not restart, the initialization must not run again.
On `molecule-postgresql` it runs the role with `postgresql_version: 19` and checks that it fails because of the data of PostgreSQL 18 without changing the container.

`verify` checks the quadlet unit with the dependencies and without secret, environment, time zone and backup volumes, that `postgresql-init` was removed,
`PG_VERSION` and `postgresql.conf` of the version, the parameters of the running server including the WAL segment size of `POSTGRES_INITDB_ARGS`,
the login of `postgres` with the password of the secret and, with the options, of the account with the right and a wrong password over TCP,
the owner of the database, the privileges and the replication slot.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd database_postgresql
MOLECULE_TART_IMAGE='debian' molecule test
```
