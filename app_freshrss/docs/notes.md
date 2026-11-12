FreshRSS runs in the container image of [linuxserver.io](https://docs.linuxserver.io/images/docker-freshrss/) as podman quadlet.
The role installs FreshRSS, keeps its configuration up to date and manages its users, the setup wizard of the web interface is not needed.
`freshrss_home` is mounted to `/config`, the data of FreshRSS is in `<freshrss_home>/www/freshrss/data`, the configuration in its `config.php`.
The image runs FreshRSS as the user `abc` with the uid and gid of `freshrss_uid` and `freshrss_gid` (defaults to `freshrss_uid`),
it refreshes the feeds every 15 minutes with cron.

### Configuration

`freshrss_config` contains the options of `data/config.php`, see `config.default.php` of FreshRSS.
It is merged recursively over the default of the role, the role merges it into the existing `config.php` after every start.

- a dictionary is a section, e.g. `db` or `limits`
- a string, a number, a boolean or a list is written as value of the option, lists replace the former value
- `null` removes the option, FreshRSS uses its default then

`config.php` is PHP, booleans are values of the options (e.g. `api_enabled: false`), so `false` does not remove an option like in the roles writing `key=value` files.

```yaml
freshrss_config:
  title: 'News'
  base_url: 'https://rss.example.org'
  api_enabled: true
  db:
    type: 'pgsql'
    host: 'postgres'
    user: 'freshrss'
    base: 'freshrss'
```

The role sets `disable_update: true` like the image, FreshRSS is updated with the image.
`salt` is created by the installation, `db.password` and `smtp.password` are set with `freshrss_secrets`,
these options must not be set in `freshrss_config`.
`default_user` has to be one of `freshrss_users`, without it the first user of `freshrss_users` is the default user.

### Installation and users

FreshRSS is installed if `data/applied_migrations.txt` does not exist: the role writes `freshrss_config` and the secrets to `data/config.custom.php`,
runs `cli/do-install.php`, which creates `config.php` with a new `salt` and the database, and removes `config.custom.php` afterwards.
Instances installed with the setup wizard are not installed again, their `config.php` is updated with `freshrss_config`.

```yaml
freshrss_users:
  - name: 'alice'
    admin: true
    email: 'alice@example.org'
  - name: 'bob'
    language: 'de'
freshrss_passwords:
  alice: "{{ vault_freshrss_alice_password }}"
  bob: "{{ vault_freshrss_bob_password }}"
freshrss_api_passwords:
  bob: "{{ vault_freshrss_bob_api_password }}"
```

Every user needs a password with at least 7 characters in `freshrss_passwords`, the API password for the Google Reader and Fever API is optional.
The role creates missing users without default feeds, it checks the passwords with `password_verify` and only sets passwords that differ,
the API password also updates the key of the Fever API. `language`, `email` and `admin` are kept up to date.
Users that are not listed are not changed. At least one user is needed.

The role uses its modules `app_freshrss_config` and `app_freshrss_user` (`library/`), they run PHP in the container with `podman exec` as `abc`
and pass the data on stdin, the passwords are options with `no_log` and never part of the arguments or the log.

### Secrets

`freshrss_secrets` is a list with `name`, `data` and `target`, the targets are `DB_PASSWORD` (`db.password`) and `SMTP_PASSWORD` (`smtp.password`).

```yaml
freshrss_secrets:
  - name: 'freshrss_db_password'
    data: "{{ vault_freshrss_db_password }}"
    target: 'DB_PASSWORD'
```

FreshRSS reads these passwords only from `config.php`, the image cannot read them from files or the environment.
So they are no podman secrets, the role writes them to `config.php`, `<freshrss_home>` is readable by PUID only (0700),
the image rewrites `config.php` on every start. They are neither part of the quadlet unit nor of the environment of the container.

### Allowed variables

The role only allows the options of `app_freshrss__config_allowed` in `freshrss_config`, the variables of the image in `app_freshrss__environment_allowed`
and the secrets `DB_PASSWORD` and `SMTP_PASSWORD`, it stops before any change if unknown options, variables or secrets are set.
This prevents unexpected behavior by accident, e.g. by a typo or an option FreshRSS does not know.

The options are generated from `config.default.php` of FreshRSS 1.30.4, the sections `db`, `limits`, `smtp` and `auto_sqlite_export` are paths
like `db.type`, `curl_options` and `db.pdo_options` are not allowed, their keys are PHP constants.
`environment`, `auth_type`, `mailer` and `db.type` only allow the values of FreshRSS. New versions of FreshRSS may add options, the list is generated again.

The environment allows `PUID`, `PGID`, `TZ` and `UMASK` of the image, the role sets `PUID`, `PGID` and `TZ`.
The check uses the container after merging `freshrss_container`, so variables set with `freshrss_container.environment` are checked as well.

### Container

Ports, volumes, additional hosts (`etc_hosts`) and dependencies (`requires`) are changed with `freshrss_container`, it is merged over the default of the container.
The merge is not recursive, `freshrss_container.volumes` replaces `/config`, `freshrss_container.environment` replaces the environment including `freshrss_environment`.
The role waits until FreshRSS answers on port 80, shows the log of the service otherwise, and installs and configures FreshRSS afterwards.

### Validation

The role checks before any change:

- `freshrss_secrets` is a list of entries with `name`, `data` and `target` with unique names and targets, the secrets have no line breaks
  and are not set in `freshrss_environment`
- `freshrss_config` is a dictionary, its options are known, not set by the role, have no line breaks and the allowed values
- `freshrss_users` has at least one user with valid and unique names, `admin` is a boolean, `default_user` is one of the users
- every user has a password with at least 7 characters, `freshrss_passwords` and `freshrss_api_passwords` have no passwords of unknown users
- only allowed environment variables and secrets are set in the container

If `freshrss_container` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Restart and updates

FreshRSS is restarted if it was running and the quadlet unit changed, otherwise it is started and enabled.
Changes of `config.php` and of the users need no restart, FreshRSS reads them with every request.
Updates of the image are done by `container_update` with `freshrss_autoupdate_enabled: true` and `freshrss_autoupdate_schedule`,
without `freshrss_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

- FreshRSS was installed with the setup wizard, the role installs it now. Existing installations keep their data and `salt`,
  set `freshrss_users` and `freshrss_passwords` for the existing users, their passwords are set from `freshrss_passwords`.
  Options set in the web interface are kept unless they are set in `freshrss_config`.
- `freshrss_uid`, `freshrss_gid`, `freshrss_version` and `freshrss_labels` stay, `freshrss_environment`, `freshrss_config`, `freshrss_secrets`,
  `freshrss_users`, `freshrss_passwords`, `freshrss_api_passwords` and `freshrss_autoupdate_schedule` are new.
- The volumes `/etc/localtime` and `/etc/timezone` are removed, the timezone is set by podman and `TZ`.
- The service is not stopped on every run anymore, `podman___update_mode` is removed.
- The tag `app_freshrss` stays, the tag `app` is added.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-freshrss-default` | Only the mandatory variables and one user, sqlite |
| `molecule-freshrss` | IPv6, labels, PostgreSQL with the secret `DB_PASSWORD`, title, base URL and API, two users, an administrator and an API password |

`prepare` creates the podman network, pulls the image and starts PostgreSQL on `molecule-freshrss`.
`side_effect` runs the role with `freshrss_container` not a dictionary, a secret without `target`, an unknown option, `salt` and `db.password` in `freshrss_config`,
a line break in a value, an invalid `auth_type`, a user without password, a short password, the password of an unknown user, an unknown default user
and an unknown environment variable in `freshrss_container.environment`
and checks that it fails with the expected message and the quadlet unit and `config.php` are unchanged (tasks marked `expect ERROR`),
then it sets `UMASK` and changes the title on `molecule-freshrss`, FreshRSS has to restart and `config.php` changes without a second installation.
`verify` checks the quadlet unit without secrets, the service, the addresses and the environment of the container, owner and options of `config.php`, the mode of `freshrss_home`,
the users and the administrators, the title of the page and the login to the Google Reader API with the API password and a wrong password.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd app_freshrss
MOLECULE_TART_IMAGE='debian' molecule test
```
