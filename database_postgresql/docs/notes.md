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

The data of the cluster is in `<postgresql_home>/data/<major>/docker` on the host, the backups in `<postgresql_home>/backup` (`/backup` in the container).

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

### Settings

`postgresql.conf` contains all parameters of the version with their description and default, generated from `postgresql.conf.sample` of the PostgreSQL sources
into `vars/settings-<major>.yml`.
Parameters set with `postgresql_settings` are active, all others stay commented out with their default.
`true` and `false` are written as `on` and `off`, numbers as numbers and everything else as quoted string.

```yaml
postgresql_settings:
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

The role fails before it changes anything if `postgresql_settings` contains a parameter unknown to the version.
Parameters with a dot in the name are settings of extensions, they are written to the section `CUSTOMIZED OPTIONS`.

Without `postgresql_settings` the role writes the same active settings as `initdb` of the image into a new cluster:
`listen_addresses = '*'`, `max_connections = 100`, `shared_buffers = 128MB`, `dynamic_shared_memory_type = posix`, `max_wal_size = 1GB`, `min_wal_size = 80MB`,
`log_timezone` and `timezone` set to `postgresql_timezone`, `datestyle = 'iso, mdy'`, the locales `en_US.utf8` and `default_text_search_config = 'pg_catalog.english'`.
`postgresql_settings` is merged over these defaults.

### Standby

With `postgresql_configure_from_primary: true` the role does not write the configuration and does not create accounts, databases, privileges and slots,
they are replicated from the primary. The standby parameters, e.g. `primary_conninfo`, are part of the replicated configuration of the primary
or are set with `ALTER SYSTEM` on the standby.

### Access

`pg_hba.conf` is generated from `postgresql_hba`, a list of entries with `type`, `database`, `user`, optional `address` and `method`.
The default allows local connections without password and connections from everywhere with `scram-sha-256`.

### Accounts, databases, privileges and replication slots

The password of the user `postgres` is set with `postgresql_password`, it is passed as podman secret and used by `initdb` when the cluster is created.
Changing the password later does not change the password of an existing cluster.

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

The role fails before it changes anything if an account has no password in `postgresql_passwords`.

### Restart and updates

PostgreSQL is restarted if the configuration or the access configuration changed, or if it was running and the secret or the quadlet unit changed.
Updates of the image within the major version are done by `container_update` with `postgresql_autoupdate_enabled: true` and `postgresql_autoupdate_schedule`, without `postgresql_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

| Before | Now |
|---|---|
| `postgresql_use_podman` | removed, only podman |
| `postgresql_podman_tag` | `postgresql_tag` |
| `postgresql_port`, `postgresql_max_connections`, `postgresql_shared_buffers`, `postgresql_dynamic_shared_memory_type`, `postgresql_unix_socket_directories` | `postgresql_settings` |
| `postgresql_enable_ssl`, `postgresql_ssl_ca_file`, `postgresql_ssl_cert_file`, `postgresql_ssl_key_file` | `postgresql_settings` with `ssl`, `ssl_ca_file`, `ssl_cert_file`, `ssl_key_file` |
| `postgresql_enable_wal` and `postgresql_wal_*`, `postgresql_fsync`, `postgresql_synchronous_commit`, `postgresql_checkpoint_*`, `postgresql_*_wal_size`, `postgresql_archive_*`, `postgresql_commit_*` | `postgresql_settings` with the parameter names |
| `postgresql_enable_replication_sending` and `postgresql_max_wal_senders`, `postgresql_max_replication_slots`, `postgresql_wal_keep_size`, `postgresql_max_slot_wal_keep_size`, `postgresql_idle_replication_slot_timeout`, `postgresql_wal_sender_timeout`, `postgresql_track_commit_timestamp` | `postgresql_settings` with the parameter names |
| `postgresql_enable_replication_standby` and `postgresql_primary_conninfo`, `postgresql_primary_slot_name`, `postgresql_hot_standby` | `postgresql_settings` with the parameter names |
| `postgresql_log_timezone`, `postgresql_datestyle`, `postgresql_lc_*`, `postgresql_default_text_search_config` | `postgresql_settings` with the parameter names |
| `podman___update_mode` | `postgresql_autoupdate_enabled` |
| versions before 18 | not supported |

### Tests

The molecule scenario `default` uses tart with two VMs:

- `molecule-postgresql` runs PostgreSQL 18, `side_effect` changes `max_connections` and checks the restart,
  then runs the role with `postgresql_version: 19` and checks that it fails because of the data of PostgreSQL 18 without changing the container,
- `molecule-postgresql-19` runs the release candidate of PostgreSQL 19.

`verify` checks the quadlet unit, `PG_VERSION` and `postgresql.conf` of the version, the settings of the running server,
the login of the account with the right and a wrong password over TCP, the owner of the database, the privileges and the replication slot.

```
cd database_postgresql
MOLECULE_TART_IMAGE='debian' molecule test
```
