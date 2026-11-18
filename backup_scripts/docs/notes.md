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

### Validation

All checks run before any change. The role fails if

- `backup_scripts` is no list or contains an unknown script, or `backup_scripts_prune` is no boolean,
- `backup_borg` has unknown keys, no `repository` or an empty `archive`,
- `backup_restic` has unknown keys or no `repository`, `backend` is unknown, `sftp` misses `host` or `user`,
- more than one of `password`, `password_file` and `password_command` is set, or `password_file` is no absolute path,
- `include` is no list with at least one path, `exclude` is no list,
- a value contains a line break, or a value of `/etc/backup/borg` or `/etc/backup/restic` contains a double quote,
- `pass_enable` is no boolean.

### Check mode

The role runs with `--check`, also on a host where it never ran, and compares the scripts and their configuration files.

### Pruning

With `backup_scripts_prune: true` (default) the role removes the scripts and configuration files of all scripts of the catalog
that are not in `backup_scripts`. Packages are never removed.
Files of other roles in `/usr/local/lib/backup` and `/etc/backup` are not touched.

### Migration

The role replaces the roles `backup`, `backup_borg` and `backup_restic`, the other roles `backup_*` follow one by one.
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

Changed behavior:

- there is no daily run on the host anymore, the external system runs the scripts, the main script `900.backup` is gone,
- the role does not remove the files of the former roles, e.g. `/etc/cron.daily/backup`, `/etc/backup/backup`, `/usr/local/lib/backup/900.backup`,
  `/etc/backup/restic-directories`, `/etc/backup/restic-ssh` and `/etc/backup/restic_password`,
- the files of restic are named `restic-includes`, `restic-sftp` and `restic-password`, the passphrase of borg is `borg-password` instead of `borg_passphrase`,
- the name of the archive of borg is configurable with `backup_borg.archive`, the default keeps the former name,
- only Debian 13 is supported.

Fixed errors of the old roles:

- the password file was written but never read by the script, restic only got a password with `backup_restic_password_command`,
- `backup_restic_password` was not mapped to a variable of the role,
- the entries of `backup_restic_exclude` and `backup_borg_exclude` were appended to the options and became additional paths of the backup, now they are excluded,
- the passphrase file of borg was written but never read by the script.

### Tests

The molecule scenario `default` uses tart with two VMs with Debian 13:

| Platform | Test case |
|---|---|
| `molecule-backup-scripts-default` | No scripts, `prepare` creates files of borg and restic and a script of another role, the role prunes the files of borg and restic and keeps the other script |
| `molecule-backup-scripts` | borg over ssh and restic with the backend `sftp` to a user on localhost, `prepare` creates the key, the user and both repositories |

`check` runs `converge` with `--check`, on `molecule-backup-scripts` the packages and the directories are missing.
`side_effect` runs invalid configurations, they have to fail before the configurations of borg and restic change.
It runs both scripts with the password on STDIN, then adds an excluded directory and `password` to both.
`verify` checks the files of the directories and the modes of the password files,
runs both scripts with the password files and checks the snapshots and archives: the first one contains the excluded directory, the latest one not.

```
cd backup_scripts
MOLECULE_TART_IMAGE='debian' molecule test
```
