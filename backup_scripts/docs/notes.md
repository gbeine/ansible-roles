The role installs backup scripts to `/usr/local/lib/backup` and their configuration to `/etc/backup`.
There is no timer on the host, an external system runs the scripts, e.g. over SSH, and passes the passwords on STDIN.

### Scripts

`backup_scripts` is a list of the scripts to install, every script has its own configuration:

```yaml
backup_scripts:
  - 'borg'
  - 'restic'
```

| Script | Installs | Configuration | Packages |
|---|---|---|---|
| `borg` | `950.backup.borgbackup` | `backup_borg` | `bash`, `borgbackup` |
| `restic` | `950.backup.restic` | `backup_restic` | `bash`, `restic` |
| `mariadb` | `910.backup.mariadb` | `backup_mariadb` | `bash`, `xz-utils` |
| `mysql` | `910.backup.mysql` | `backup_mysql` | `bash`, `xz-utils` |

The scripts are listed in `vars/main.yml`, the packages in `vars/Debian-13.yml`.
The external system runs every script on its own, e.g. `/usr/local/lib/backup/950.backup.restic`.

### restic

`backup_restic` is merged into the default, `repository` is mandatory:

```yaml
backup_restic:
  repository: 'sftp:backup:restic'
  backend: 'sftp'
  host: 'storage.example.org'
  user: 'u1234'
  include:
    - '/etc'
    - '/home'
  exclude:
    - '/home/*/.cache'
```

- `backend` is `local` (default), `sftp` or `rest`.
  - `sftp` needs `host` and `user`. The role writes `/etc/backup/restic-sftp` with the host `backup`,
    the repository is `sftp:backup:<path>`. The key is `id_file` (default `/root/.ssh/backup`), it is created by `backup_ssh`.
    The host key of the server has to be in `/root/.ssh/known_hosts`.
  - `rest` reads the user and password of the REST server with `pass_command` (default `pass`)
    from `restic/rest_username` and `restic/rest_password` if `pass_enable` is `true`.
  - `local` is any other repository of restic, e.g. a directory, see
    [Preparing a new repository](https://restic.readthedocs.io/en/stable/030_preparing_a_new_repo.html).
- `include` is the list of backed-up paths, written to `/etc/backup/restic-includes` (`--files-from-verbatim`),
  the default is `/etc`, `/home`, `/root`, `/usr/local/etc`, `/var/backups` and `/var/log`.
- `exclude` is the list of excluded patterns, written to `/etc/backup/restic-excludes` (`--exclude-file`).
- `options` are the options of `restic backup` (default `--compression max --one-file-system -v`).
- `cache_dir` is the cache of restic (default `/var/cache/restic`).

The role does not initialize the repository, `restic init` runs once before the first backup.

#### Password

By default the password of the repository is not stored on the host.
The external system passes it on STDIN, restic reads it from there if no password file or command is set:

```
ssh root@host /usr/local/lib/backup/950.backup.restic < password
```

Instead, one of these keys keeps the password on the host. The role prints a warning then:

- `password` is written to `/etc/backup/restic-password` with mode `0400` and used with `RESTIC_PASSWORD_FILE`
- `password_file` is an existing file on the host, used with `RESTIC_PASSWORD_FILE`
- `password_command` is used with `RESTIC_PASSWORD_COMMAND`

### borg

`backup_borg` is merged into the default, `repository` is mandatory:

```yaml
backup_borg:
  repository: 'ssh://u1234@storage.example.org:23/./borg'
  include:
    - '/etc'
    - '/home'
  exclude:
    - '/home/*/.cache'
```

- `repository` is any repository of borg, e.g. a directory or `ssh://…`, see
  [Repository URLs](https://borgbackup.readthedocs.io/en/stable/usage/general.html#repository-urls).
  borg has to be installed on the server of an `ssh://` repository.
- `rsh` is the command of ssh (`BORG_RSH`, default `ssh -i /root/.ssh/backup`), the key is created by `backup_ssh`.
  The host key of the server has to be in `/root/.ssh/known_hosts`.
- `archive` is the name of the archive with the placeholders of borg (default `{hostname}-{now:%Y-%m-%d}`, one archive per day),
  e.g. `{hostname}-{now}` for more than one backup per day.
- `include` is the list of backed-up paths, written to `/etc/backup/borg-includes`, the default is the one of restic.
- `exclude` is the list of excluded patterns, written to `/etc/backup/borg-excludes` (`--exclude-from`).
- `options` are the options of `borg create` (default `-s -v -p`), `cache_dir` is the cache of borg (default `/var/cache/borg`).

The role does not initialize the repository, `borg init` runs once before the first backup.

By default the passphrase of the repository is not stored on the host, the script sets `BORG_PASSPHRASE_FD=0`
and borg reads the passphrase from STDIN.
`password`, `password_file` and `password_command` keep the passphrase on the host like for restic and the role prints a warning:
`password` is written to `/etc/backup/borg-password` with mode `0400`, the script reads the file or runs the command with `BORG_PASSCOMMAND`.

### MariaDB and MySQL

The scripts `mariadb` and `mysql` dump every database of MariaDB or MySQL running in a podman container into its own file
`<backup_dir>/<database>-<YYYYMMDD>.sql`, the clients run in the container with `podman exec`.
`backup_mariadb` and `backup_mysql` are merged into the default:

```yaml
backup_mariadb:
  container: 'mariadb'
  user: '_backup_'
  ignore_databases:
    - 'information_schema'
    - 'performance_schema'
    - 'sys'
    - 'test'
```

- `container` is the name of the container (default `mariadb` and `mysql`), e.g. the container of `database_mariadb`,
  `host` is the host the client connects to in the container (default `localhost`, the socket).
- `user` is the database user of the backup (default `_backup_`), it needs `SELECT`, `SHOW VIEW`, `TRIGGER`, `EVENT`,
  `LOCK TABLES` and `RELOAD` for `--flush-logs`, with `replication` also `REPLICATION SLAVE ADMIN` (MariaDB) or `REPLICATION_SLAVE_ADMIN` (MySQL).
- `backup_dir` is the directory of the dumps (default `/var/backups/mariadb` and `/var/backups/mysql`), it is created with mode `0750`.
- `options` are the options of `mariadb-dump` or `mysqldump` (default `--flush-logs --add-locks --lock-tables --triggers --routines --events`).
- `ignore_databases` are the databases that are not dumped (default `information_schema`, `performance_schema` and `sys`).
- `compress` compresses the dumps with `xz` (default `true`).
- `keep_days` removes dumps older than the number of days (default `14`).
- `replication` stops the replica with `STOP REPLICA` before the dumps and starts it with `START REPLICA` afterwards (default `false`).

By default the password of the database user is not stored on the host.
The external system passes it on STDIN, the script reads it once and passes it to every client in the container on STDIN:
the clients run with `--password` without value and `podman exec -i` without a terminal, so they read the password from STDIN.
The password never appears on a command line or in the environment.

```
ssh root@host /usr/local/lib/backup/910.backup.mariadb < password
```

`password`, `password_file` and `password_command` keep the password on the host like for restic and the role prints a warning,
`password` is written to `/etc/backup/mariadb-password` or `/etc/backup/mysql-password` with mode `0400`.

### Validation

All checks run before any change. The role fails if

- `backup_scripts` is no list or contains an unknown script, or `backup_scripts_prune` is no boolean,
- `backup_borg` has unknown keys, no `repository` or an empty `archive`,
- `backup_restic` has unknown keys or no `repository`, `backend` is unknown, `sftp` misses `host` or `user`,
- more than one of `password`, `password_file` and `password_command` is set, or `password_file` is no absolute path,
- `include` is no list with at least one path, `exclude` is no list,
- a value contains a line break, or a value of `/etc/backup/borg` or `/etc/backup/restic` contains a double quote,
- `pass_enable` is no boolean,
- `backup_mariadb` or `backup_mysql` has unknown keys, an empty `container`, `host` or `user`, a `backup_dir` that is no absolute path,
  `ignore_databases` is no list or contains spaces, `keep_days` is no positive integer, `compress` or `replication` is no boolean,
  a value contains a line break or a value of `/etc/backup/mariadb` or `/etc/backup/mysql` contains a double quote.

### Check mode

The role runs with `--check`, also on a host where it never ran, and compares the scripts and their configuration files.

### Pruning

With `backup_scripts_prune: true` (default) the role removes the scripts and configuration files of all scripts of the catalog
that are not in `backup_scripts`. Packages are never removed.
Files of other roles in `/usr/local/lib/backup` and `/etc/backup` are not touched.

### Migration

The role replaces the roles `backup`, `backup_borg`, `backup_restic` and `backup_mysql`, the other roles `backup_*` follow one by one.
`backup_ssh` stays a role of its own for now.

| Before | Now |
|---|---|
| `backup_enable`, `backup_95x_enable` | removed, every script in `backup_scripts` is installed |
| `backup_logfile`, `backup_error_logfile` | removed, the output goes to the external system |
| `backup_borg_enable` | `borg` in `backup_scripts` |
| `backup_borg_repository`, `backup_borg_rsh` | `backup_borg.repository`, `.rsh`, the default of `rsh` uses `/root/.ssh/backup` instead of `backup_ssh_key_name` |
| `backup_borg_passphrase` | `backup_borg.password`, by default the passphrase comes on STDIN |
| `backup_borg_password_command` | `backup_borg.password_command` |
| `backup_borg_options`, `backup_borg_cache_dir`, `backup_borg_include`, `backup_borg_exclude` | `backup_borg.options`, `.cache_dir`, `.include`, `.exclude` |
| `backup_restic_enable` | `restic` in `backup_scripts` |
| `backup_restic_repository`, `backup_restic_host`, `backup_restic_user`, `backup_restic_id_file` | `backup_restic.repository`, `.host`, `.user`, `.id_file` |
| `backup_restic_ssh: true`, `backup_restic_rest: true` | `backup_restic.backend: 'sftp'`, `backup_restic.backend: 'rest'` |
| `backup_restic_password` | `backup_restic.password`, by default the password comes on STDIN |
| `backup_restic_password_command` | `backup_restic.password_command` |
| `backup_restic_pass_enable`, `backup_restic_pass_command` | `backup_restic.pass_enable`, `backup_restic.pass_command` |
| `backup_restic_options`, `backup_restic_cache_dir`, `backup_restic_include`, `backup_restic_exclude` | `backup_restic.options`, `.cache_dir`, `.include`, `.exclude` |
| `backup_mysql_use_podman` | removed, `mariadb` or `mysql` in `backup_scripts`, both scripts run the clients in the container `backup_mariadb.container` or `backup_mysql.container` |
| `backup_mysql_user`, `backup_mysql_host`, `backup_mysql_backup_dir` | `backup_mariadb.user`, `.host`, `.backup_dir` and the same keys of `backup_mysql` |
| `backup_mysql_password` | `backup_mariadb.password` or `backup_mysql.password`, by default the password comes on STDIN |
| `backup_mysql_pass` | `backup_mariadb.password_command` or `backup_mysql.password_command` |
| `backup_mysql_dump_options` | `backup_mariadb.options` or `backup_mysql.options`, the options replace the default instead of being appended |
| `backup_mysql_ignore_databases`, `backup_mysql_keep_days`, `backup_mysql_compress`, `backup_mysql_replication` | `.ignore_databases`, `.keep_days`, `.compress`, `.replication` of `backup_mariadb` or `backup_mysql` |

Changed behavior:

- there is no daily run on the host anymore, the external system runs the scripts, the main script `900.backup` is gone,
- the role does not remove the files of the former roles, e.g. `/etc/cron.daily/backup`, `/etc/backup/backup`, `/usr/local/lib/backup/900.backup`,
  `/etc/backup/restic-directories`, `/etc/backup/restic-ssh`, `/etc/backup/restic_password`,
  `/usr/local/lib/backup/910.backup.mariadb-podman` and `/etc/backup/mysql_password`,
- the scripts of MariaDB and MySQL are split, both run the clients in a podman container, MySQL no longer runs natively,
- the dumps of MariaDB are written to `/var/backups/mariadb` instead of `/var/backups/mysql`,
- the files of restic are named `restic-includes`, `restic-sftp` and `restic-password`, the passphrase of borg is `borg-password` instead of `borg_passphrase`,
- the name of the archive of borg is configurable with `backup_borg.archive`, the default keeps the former name,
- only Debian 13 is supported.

Fixed errors of the old roles:

- the password file was written but never read by the script, restic only got a password with `backup_restic_password_command`,
- `backup_restic_password` was not mapped to a variable of the role,
- the entries of `backup_restic_exclude` and `backup_borg_exclude` were appended to the options and became additional paths of the backup, now they are excluded,
- the passphrase file of borg was written but never read by the script,
- the password of MySQL and MariaDB was passed with `--password=…` and visible in the process list,
- `backup_mysql_compress` was ignored, the dumps were always compressed,
- `backup_mysql_replication` ran `mysqladmin stop` and `start`, which are no commands of `mysqladmin`,
- the databases were read from the table output of `mysqlshow`, a failed dump left a broken file and did not fail the script.

### Tests

The molecule scenario `default` uses tart with two VMs with Debian 13:

| Platform | Test case |
|---|---|
| `molecule-backup-scripts-default` | No scripts, `prepare` creates files of borg, restic, mariadb and mysql and a script of another role, the role prunes the files of the catalog and keeps the other script |
| `molecule-backup-scripts` | borg over ssh and restic with the backend `sftp` to a user on localhost, `prepare` creates the key, the user and both repositories; mariadb and mysql as `root`, mysql without compression, `prepare` starts the containers `mariadb` (`mariadb:lts`) and `mysql` (`mysql:8.4`) with the database `molecule` and an old dump |

`check` runs `converge` with `--check`, on `molecule-backup-scripts` the packages and the directories are missing.
`side_effect` runs invalid configurations, they have to fail before the configurations of borg, restic, mariadb and mysql change.
It runs all scripts with the password on STDIN, then adds an excluded directory to borg and restic and `password` to all scripts.
`verify` checks the files of the directories and the modes of the password files,
runs borg and restic with the password files and checks the snapshots and archives: the first one contains the excluded directory, the latest one not.
It runs mariadb and mysql with the password files and checks that the dump of `molecule` contains its row,
the ignored databases are not dumped and the old dump is removed.

```
cd backup_scripts
MOLECULE_TART_IMAGE='debian' molecule test
```
