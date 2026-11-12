MariaDB runs in the container image [linuxserver/mariadb](https://docs.linuxserver.io/images/docker-mariadb/) (`latest` by default, `mariadb_version` sets the tag) as podman quadlet,
the role manages its databases and accounts.
The image runs MariaDB as the user `abc` with the uid and gid of `mariadb_uid` and `mariadb_gid`, it changes the owner of `/config` to them on every start.
`mariadb_home` is mounted to `/config`, the databases are in `<mariadb_home>/databases`, the logs in `<mariadb_home>/log/mysql`.
MariaDB listens on port 3306, the role `backup_mysql` dumps the databases with `podman exec mariadb mariadb-dump`.

### Configuration

The role writes `<mariadb_home>/custom.cnf`, the image starts `mariadbd-safe --defaults-extra-file=/config/custom.cnf`.
`mariadb_config` is a dictionary of the sections `client`, `mysql`, `mysqldump`, `mysqld_safe` and `mysqld`,
every section is merged over the section of the default of the role, the default is the `custom.cnf` of the image.

- a string or a number writes `option = value`
- `true` writes the option without value, e.g. `skip-name-resolve`
- a list writes one line per element
- `false` or `null` removes the option, e.g. an option of the default

```yaml
mariadb_config:
  mysqld:
    max_connections: 200
    innodb_buffer_pool_size: '1G'
    skip-name-resolve: true
    query_cache_type: false
  mysqldump:
    max_allowed_packet: '64M'
```

The names of the options are written as given, MariaDB treats `-` and `_` the same.
The options may have the prefixes `loose-`, `skip-`, `enable-`, `disable-` and `maximum-` of MariaDB.

The role sets the options the image, the role and `backup_mysql` depend on, they must not be set in `mariadb_config`:
`port` and `socket` in `client`, `socket` in `mysqld_safe`, `user`, `pid-file`, `socket`, `port`, `basedir` and `datadir` in `mysqld`.
Passwords (`password`, `wsrep_sst_auth`) must not be written to `custom.cnf`.

### Databases and accounts

The role manages databases and accounts with `ansible.mariadb` as `root` over the address of the container after every start,
it removes the anonymous accounts. Databases and accounts that are not listed are not changed.

```yaml
mariadb_databases:
  - name: 'nextcloud'
  - name: 'wiki'
    encoding: 'utf8mb4'
    collation: 'utf8mb4_unicode_ci'
mariadb_accounts:
  - name: 'nextcloud'
    host: '%'
    privileges: 'nextcloud.*:ALL'
  - name: '_backup_'
    privileges: '*.*:SELECT,LOCK TABLES,SHOW VIEW,EVENT,TRIGGER'
mariadb_passwords:
  nextcloud: "{{ vault_mariadb_nextcloud_password }}"
  _backup_: "{{ vault_mariadb_backup_password }}"
```

`host` is `localhost` by default, accounts of applications in other containers need `%` or their address.
`privileges` is a string like `nextcloud.*:ALL` or a dictionary as `priv` of `ansible.mariadb.mariadb_user`.
Every account needs a password in `mariadb_passwords`. The host of the role needs `python3-pymysql`, the role installs it.
The controller needs the collection `ansible.mariadb` (`ansible-galaxy collection install ansible.mariadb`).

### Secrets

`mariadb_secrets` is a list of podman secrets with `name`, `data` and `target`, the target is the name of the variable of the image.
The base image of linuxserver reads `FILE__<VARIABLE>` as file, the role mounts the secrets to `/run/secrets/<name>` and sets the file variable.

| Target | File variable | |
|---|---|---|
| `MYSQL_ROOT_PASSWORD` | `FILE__MYSQL_ROOT_PASSWORD` | mandatory, used by the role to manage databases and accounts |

```yaml
mariadb_secrets:
  - name: 'mariadb_root_password'
    data: "{{ vault_mariadb_root_password }}"
    target: 'MYSQL_ROOT_PASSWORD'
```

The image sets the root password only on the first start, the role uses it as `root@%` afterwards, so it has to stay the password of the first start.
The image sets no password with less than 4 characters and writes the password into SQL in single quotes without escaping,
the role rejects shorter passwords and passwords with single quotes, backslashes or line breaks.

### Allowed variables

The role only allows the options of `database_mariadb__config_allowed` in the sections of `mariadb_config`, the variables of the image in `database_mariadb__environment_allowed`
and the secret `MYSQL_ROOT_PASSWORD`, it stops before any change if unknown options, variables or secrets are set.
This prevents unexpected behavior by accident, e.g. by a typo or an option MariaDB does not know, MariaDB does not start with unknown options.

The options are generated from the sources of MariaDB 11.8.9, the version of the image:

- `mysqld`: the variables of `sql/sys_vars.cc` that can be set on the command line, the options of `sql/mysqld.cc`
  and the variables of the plugins InnoDB, Aria and MyISAM with their prefixes
- `mysql` and `mysqldump`: the options of `client/mysql.cc` and `client/mysqldump.cc`
- `client`: the options known by `mysql`, `mysqldump` and `mysqladmin`
- `mysqld_safe`: the options of `scripts/mysqld_safe.sh`

New versions of MariaDB may add options, the lists are generated again.

The environment allows `PUID`, `PGID`, `TZ`, `UMASK`, `CLI_OPTS` and `REMOTE_SQL`, the role sets `PUID`, `PGID`, `TZ` and `FILE__MYSQL_ROOT_PASSWORD`.
`MYSQL_DATABASE`, `MYSQL_USER` and `MYSQL_PASSWORD` of the image are rejected, databases and accounts are managed by the role.
The check uses the container after merging `mariadb_container`, so variables set with `mariadb_container.environment` are checked as well.

### Container

Ports, volumes, additional hosts (`etc_hosts`) and dependencies (`requires`) are changed with `mariadb_container`, it is merged over the default of the container.
The merge is not recursive, `mariadb_container.volumes` replaces `/config`, `mariadb_container.environment` replaces the environment including `mariadb_environment`.
The role waits until MariaDB answers as root, shows the log of the service otherwise, and manages the databases and accounts afterwards.

### Validation

The role checks before any change:

- `mariadb_secrets` is a list of entries with `name`, `data` and `target` and unique names, the secret `MYSQL_ROOT_PASSWORD` exists
- the root password has at least 4 characters and no single quotes, backslashes or line breaks
- neither a secret nor its file variable nor a user of the image is set in `mariadb_environment`
- the sections of `mariadb_config` are known dictionaries, their options are known, not set by the role and no passwords,
  the values are strings, numbers, booleans or lists of them without line breaks
- `mariadb_databases` and `mariadb_accounts` are lists of entries with valid names, databases are unique, accounts are unique by name and host,
  `root` is not an account, `privileges` is a string or a dictionary
- every account has a password in `mariadb_passwords`, `mariadb_passwords` has no passwords of unknown accounts and no empty passwords
- only allowed environment variables and secrets are set in the container

If `mariadb_container` or `mariadb_config` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Restart and updates

MariaDB is restarted if it was running and a secret, the quadlet unit or `custom.cnf` changed, otherwise it is started and enabled.
Updates of the image are done by `container_update` with `mariadb_autoupdate_enabled: true` and `mariadb_autoupdate_schedule`,
without `mariadb_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

- The single variables of `custom.cnf` are replaced by `mariadb_config`, e.g. `mariadb_max_connections` by `mariadb_config.mysqld.max_connections`
  and `mariadb_character_set` by `mariadb_config.client.default-character-set`; booleans like `mariadb_skip_external_locking` are `true` or `false` of the option.
  The default of the role is the `custom.cnf` of the image, the former role wrote `table_cache` and `thread_concurrency`, MariaDB 11 does not know them anymore.
- `mariadb_root_password` is replaced by the secret `MYSQL_ROOT_PASSWORD`, it is mounted as file instead of the environment, keep the former value.
- `/root/.my.cnf` with the root password in plain text is not written anymore, remove it from the host.
- `mariadb_databases` is a list of entries with `name` instead of a list of names, `mariadb_accounts` and `mariadb_passwords` stay.
- `mariadb_podman_tag` is replaced by `mariadb_version`.
- `mariadb_use_podman`, `mariadb_port`, `mariadb_socket`, `mariadb_user`, `mariadb_pid_file` and `mariadb_bind_address` are removed,
  the installation without podman, which failed with "Currently not supported", is removed, the host does not get `mariadb-client` anymore.
- The service is not stopped on every run anymore, the handler `Restart MariaDB` and `podman___update_mode` are removed.
- The tag `database_mariadb` stays, the tag `database` is added.
- The databases and accounts are managed with the collection `ansible.mariadb` instead of `community.mysql`, `community.mysql` drops the support of MariaDB with version 6.0.0.
  The controller needs `ansible.mariadb`, `community.mysql` is not needed by the role anymore.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-mariadb-default` | Only the mandatory variables and the root password |
| `molecule-mariadb` | IPv6, labels, options of `mysqld` and `mysqldump` with a removed option, an option without value and a prefix, databases and accounts with privileges |

`prepare` creates the podman network and pulls the image.
`side_effect` runs the role with `mariadb_container` not a dictionary, a secret without `target`, without the root password, a short root password,
a single quote in the root password, the root password and a user of the image in the environment, an unknown section and option,
the option `datadir` set by the role, a password in `custom.cnf`, a line break in a value, an account without password, the password of an unknown account
and an unknown environment variable in `mariadb_container.environment`
and checks that it fails with the expected message and the quadlet unit and `custom.cnf` are unchanged (tasks marked `expect ERROR`),
then it changes `max_connections` on `molecule-mariadb`, `custom.cnf` changes and MariaDB has to restart.
`verify` checks the quadlet unit with the secret as file, the service, the addresses and the environment of the container, `custom.cnf` without passwords,
the variables, the databases and the accounts as root, that `app` may write, `reader` may only read and that a wrong password is rejected,
it connects like the role with `ansible.mariadb` from the VM to the address of the container.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd database_mariadb
MOLECULE_TART_IMAGE='debian' molecule test
```
