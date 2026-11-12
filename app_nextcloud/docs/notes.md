Nextcloud runs in the container image of [linuxserver.io](https://docs.linuxserver.io/images/docker-nextcloud/) as podman quadlet.
The role installs Nextcloud, keeps its configuration up to date and manages its users, the web-based installer is not needed.
`<nextcloud_home>/config` is mounted to `/config`, the configuration is in `<nextcloud_home>/config/www/nextcloud/config/config.php`,
`<nextcloud_home>/data` is mounted to `/data`, the data directory of Nextcloud.
The image runs Nextcloud as the user `abc` with the uid and gid of `nextcloud_uid` and `nextcloud_gid` (defaults to `nextcloud_uid`),
nginx listens on port 80 and 443, cron runs the background jobs every 5 minutes.

### Configuration

`nextcloud_config` contains the system values of `config.php`, see `config/config.sample.php` of Nextcloud.
It is merged over the default of the role, the merge is not recursive, a value replaces the value of the default.
The role sets the values in the existing `config.php` after every start.

- a string, a number, a boolean, a list or a dictionary is written as value, e.g. `trusted_domains` or `redis`
- `null` removes the value, Nextcloud uses its default then

`config.php` is PHP, booleans are values (e.g. `mail_smtpauth: true`), so `false` does not remove a value like in the roles writing `key=value` files.
The default of the role sets `dbtype: mysql`, `trusted_domains` with `nextcloud_hostname`, `overwrite.cli.url` with `https://<nextcloud_hostname>`
and `upgrade.disable-web: true`, Nextcloud is updated with the image.

```yaml
nextcloud_config:
  dbhost: 'mariadb'
  dbname: 'nextcloud'
  dbuser: 'nextcloud'
  trusted_domains: [ 'cloud.example.org' ]
  overwrite.cli.url: 'https://cloud.example.org'
  trusted_proxies: [ '10.89.0.2' ]
  default_phone_region: 'DE'
```

The database is MariaDB or MySQL (`dbtype: mysql`, the default) or PostgreSQL (`dbtype: pgsql`), sqlite is not supported.
`dbhost`, `dbname`, `dbuser` and the secret `dbpassword` are mandatory, a port is set with `dbhost: 'mariadb:3307'` or `dbport`.
The image sets `memcache.local`, `memcache.locking`, `filelocking.enabled` and `upgrade.disable-web` on start if they are missing.

### Installation and users

Nextcloud is installed if `installed` is not set in `config.php`: the role runs `occ maintenance:install` with the database, the secret `dbpassword`,
the first administrator of `nextcloud_users` and the data directory `/data`, then it sets `nextcloud_config`.
Instances installed with the web-based installer are not installed again, their `config.php` is updated with `nextcloud_config`.

```yaml
nextcloud_users:
  - name: 'admin'
    admin: true
    email: 'admin@example.org'
  - name: 'alice'
    display_name: 'Alice'
    email: 'alice@example.org'
    groups: [ 'family' ]
nextcloud_passwords:
  admin: "{{ vault_nextcloud_admin_password }}"
  alice: "{{ vault_nextcloud_alice_password }}"
```

Every user needs a password with at least 10 characters in `nextcloud_passwords`, at least one user needs `admin: true`.
The names may contain letters, digits and `_ . @ -`, Nextcloud allows spaces and quotes as well, the role does not.
The role creates missing users, it checks the passwords with the user manager of Nextcloud and only sets passwords that differ.
`display_name` and `email` are kept up to date if they are set. With `groups` the user is a member of exactly these groups, missing groups are created,
without `groups` the groups of the user are not changed. `admin` sets the membership of the group `admin`, it must not be part of `groups`.
Users that are not listed are not changed.

The role uses its modules `app_nextcloud_install`, `app_nextcloud_config` and `app_nextcloud_user` (`library/`), they run PHP in the container
with `podman exec` as `abc` and pass the data on stdin. The passwords are options with `no_log` and never part of the arguments of a process or the log,
the installation passes them to `occ` inside PHP.

### Secrets

`nextcloud_secrets` is a list with `name`, `data` and `target`, the targets are `dbpassword` (mandatory) and `mail_smtppassword`.

```yaml
nextcloud_secrets:
  - name: 'nextcloud_db_password'
    data: "{{ vault_nextcloud_db_password }}"
    target: 'dbpassword'
  - name: 'nextcloud_smtp_password'
    data: "{{ vault_nextcloud_smtp_password }}"
    target: 'mail_smtppassword'
```

Nextcloud reads these passwords from `config.php`, it reads no files for them. Nextcloud reads values from variables `NC_<key>` of the environment,
but the image runs `occ` with `sudo` and the background jobs with cron, both do not get the environment of the container.
So they are no podman secrets, the role writes them to `config.php`, Nextcloud writes it with mode 0640, `<nextcloud_home>` is 0750.
They are neither part of the quadlet unit nor of the environment of the container.

### Allowed variables

The role only allows the values of `app_nextcloud__config_allowed` in `nextcloud_config`, the variables of the image in `app_nextcloud__environment_allowed`
and the secrets `dbpassword` and `mail_smtppassword`, it stops before any change if unknown values, variables or secrets are set.
This prevents unexpected behavior by accident, e.g. by a typo or a value Nextcloud does not know.

The values are generated from the keys of the first level of `config/config.sample.php` of Nextcloud 35.0.2 plus `dbport` and `filelocking.enabled`,
without the values set by Nextcloud, the installation or the role (`installed`, `version`, `instanceid`, `passwordsalt`, `secret`, `datadirectory`,
`data-fingerprint`, `copied_sample_config`) and the passwords. `dbtype` only allows `mysql` and `pgsql`.
Values of apps that are not part of `config.sample.php` are not allowed. New versions of Nextcloud may add values, the list is generated again.

The environment allows `PUID`, `PGID`, `TZ` and `UMASK` of the image, the role sets `PUID`, `PGID` and `TZ`.
The check uses the container after merging `nextcloud_container`, so variables set with `nextcloud_container.environment` are checked as well.

### Container

Ports, volumes, additional hosts (`etc_hosts`) and dependencies (`requires`) are changed with `nextcloud_container`, it is merged over the default of the container.
The merge is not recursive, `nextcloud_container.volumes` replaces `/config`, `/data` and the certificates of the host,
`nextcloud_container.environment` replaces the environment including `nextcloud_environment`.
`/usr/local/share/ca-certificates` of the host is mounted read-only, the image adds these certificates to its trust store.
The role waits until `/status.php` answers with `nextcloud_hostname` as host, the image copies Nextcloud and runs `occ upgrade` before nginx starts,
an installed Nextcloud answers 400 if `nextcloud_hostname` is no trusted domain, the role shows the log of the service if Nextcloud does not answer.

### Validation

The role checks before any change:

- `nextcloud_secrets` is a list of entries with `name`, `data` and `target` with unique names and targets, `dbpassword` is set,
  the secrets have no line breaks and are not set in `nextcloud_environment`
- `nextcloud_config` is a dictionary, its values are known, not set by the role, have no line breaks, `dbtype` is `mysql` or `pgsql`
  and `dbhost`, `dbname` and `dbuser` are set
- `nextcloud_users` has at least one administrator, valid and unique names, `admin` is a boolean, `groups` is a list without `admin`,
  `display_name` and `email` have no line breaks
- every user has a password with at least 10 characters, `nextcloud_passwords` has no passwords of unknown users
- only allowed environment variables and secrets are set in the container

If `nextcloud_container` or `nextcloud_config` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Restart and updates

Nextcloud is restarted if it was running and the quadlet unit changed, otherwise it is started and enabled.
Changes of `config.php` and of the users need no restart, Nextcloud reads them with every request.
Updates of the image are done by `container_update` with `nextcloud_autoupdate_enabled: true` and `nextcloud_autoupdate_schedule`,
without `nextcloud_autoupdate_schedule` the schedule of `container_update` is used. The image runs `occ upgrade` after an update.

### Migration

- `nextcloud_config` was the content of `config.php` as string, it was only written if `config.php` did not exist.
  It is a dictionary of the system values now, move the values of `config.php` to `nextcloud_config` and the passwords to `nextcloud_secrets`.
- Nextcloud was installed with the web-based installer, the role installs it now. Existing installations are not installed again,
  set `nextcloud_users` and `nextcloud_passwords` for the existing users, their passwords are set from `nextcloud_passwords`.
  Values set in the web interface are kept unless they are set in `nextcloud_config`.
- sqlite is not supported anymore, migrate an existing installation before with `occ db:convert-type`.
- `nextcloud_publish` was not used, ports are published with `nextcloud_container.publish`.
- `nextcloud_container.hosts` was passed as `etc_hosts`, it is `nextcloud_container.etc_hosts` now like in the other roles.
- `/usr/local/share/ca-certificates` is mounted read-only.
- The former default of `nextcloud_autoupdate_schedule` (`*-*-* 00/4:00:00`) is removed, the schedule of `container_update` is used.
- `nextcloud_uid`, `nextcloud_gid`, `nextcloud_version`, `nextcloud_labels` and `nextcloud_container` stay,
  `nextcloud_environment`, `nextcloud_secrets`, `nextcloud_users` and `nextcloud_passwords` are new.
- The service is not stopped on every run anymore, `podman___update_mode` is removed.
- The tag `app_nextcloud` stays, the tag `app` is added.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-nextcloud-default` | Only the mandatory variables, MariaDB and one administrator |
| `molecule-nextcloud` | IPv6, labels, PostgreSQL, values of `config.php`, the secret `mail_smtppassword`, an administrator and a user with a group |

`prepare` creates the podman network, pulls the images and starts MariaDB on `molecule-nextcloud-default` and PostgreSQL on `molecule-nextcloud`.
`side_effect` runs the role with `nextcloud_container` not a dictionary, a secret without `target`, no database password, an unknown secret,
an unknown value, `dbpassword` and `passwordsalt` in `nextcloud_config`, sqlite, no database host, a line break in a value, no administrator,
a user without password, a short password and an unknown environment variable
and checks that it fails with the expected message and the quadlet unit and `config.php` are unchanged (tasks marked `expect ERROR`),
then it sets `UMASK`, changes `default_language` and the password of a user on `molecule-nextcloud`,
Nextcloud has to restart, `config.php` and the password change without a second installation.
`verify` checks the quadlet unit without secrets, the service, the addresses and the environment of the container, mode, owner and values of `config.php`,
`/status.php`, the login to the OCS API with the passwords and the refused former password, the groups of the users and the tables of Nextcloud in the database.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd app_nextcloud
MOLECULE_TART_IMAGE='debian' molecule test
```
