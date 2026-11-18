The role installs backup scripts to `/usr/local/lib/backup` and their configuration to `/etc/backup`.
There is no timer on the host, an external system runs the scripts, e.g. over SSH, and passes the passwords on STDIN.

### Scripts

`backup_scripts` is a list of the scripts to install, every script has its own configuration:

```yaml
backup_scripts:
  - 'restic'
```

| Script | Installs | Configuration | Packages |
|---|---|---|---|
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

### Validation

All checks run before any change. The role fails if

- `backup_scripts` is no list or contains an unknown script, or `backup_scripts_prune` is no boolean,
- `backup_restic` has unknown keys or no `repository`, `backend` is unknown, `sftp` misses `host` or `user`,
- more than one of `password`, `password_file` and `password_command` is set, or `password_file` is no absolute path,
- `include` is no list with at least one path, `exclude` is no list,
- a value contains a line break, or a value of `/etc/backup/restic` contains a double quote,
- `pass_enable` is no boolean.

### Check mode

The role runs with `--check`, also on a host where it never ran.
Without `/etc/backup` and `/usr/local/lib/backup` the role stops after the installation of the packages, there are no files to compare.

### Pruning

With `backup_scripts_prune: true` (default) the role removes the scripts and configuration files of all scripts of the catalog
that are not in `backup_scripts`. Packages are never removed.
Files of other roles in `/usr/local/lib/backup` and `/etc/backup` are not touched.

### Migration

The role replaces the roles `backup` and `backup_restic`, the other roles `backup_*` follow one by one.
`backup_ssh` stays a role of its own for now.

| Before | Now |
|---|---|
| `backup_enable`, `backup_95x_enable` | removed, every script in `backup_scripts` is installed |
| `backup_logfile`, `backup_error_logfile` | removed, the output goes to the external system |
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
- the files of restic are named `restic-includes`, `restic-sftp` and `restic-password`,
- only Debian 13 is supported.

Fixed errors of the old roles:

- the password file was written but never read by the script, restic only got a password with `backup_restic_password_command`,
- `backup_restic_password` was not mapped to a variable of the role,
- the entries of `backup_restic_exclude` were appended to the options and became additional paths of the backup, now they are excluded.

### Tests

The molecule scenario `default` uses tart with two VMs with Debian 13:

| Platform | Test case |
|---|---|
| `molecule-backup-scripts-default` | No scripts, `prepare` creates files of restic and a script of another role, the role prunes the files of restic and keeps the other script |
| `molecule-backup-scripts` | restic with the backend `sftp` to a user on localhost, `prepare` creates the key, the user and the repository |

`check` runs `converge` with `--check`, on `molecule-backup-scripts` the directories are missing and the role stops after the installation.
`side_effect` runs invalid configurations, they have to fail before `/etc/backup/restic` changes.
It runs the restic script with the password on STDIN, then adds an excluded directory and `password`.
`verify` checks the files of the directories and the mode of the password file,
runs the restic script with the password file and checks the snapshots: the first one contains the excluded directory, the latest one not.

```
cd backup_scripts
MOLECULE_TART_IMAGE='debian' molecule test
```
