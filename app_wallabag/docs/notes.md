wallabag runs in the container image [wallabag/wallabag](https://hub.docker.com/r/wallabag/wallabag) (`latest` by default) as podman quadlet.
`<wallabag_home>/data`, `images` and `var` are mounted to `/var/www/wallabag/data`, `web/assets/images` and `var`,
`data` contains the sqlite database, `images` the downloaded images of the articles.
The image runs PHP and nginx as `nobody` (uid 65534), the role creates the directories with this owner, nginx listens on port 80.

### Configuration

wallabag is configured with `wallabag_environment`, which is merged over the default of the role (`SYMFONY__ENV__DATABASE_DRIVER` `pdo_sqlite`),
see the [parameters of wallabag](https://doc.wallabag.org/admin/parameters) and the [image](https://github.com/wallabag/docker).
`SYMFONY__ENV__DOMAIN_NAME` is mandatory, it is the public URL of wallabag used in links and emails.
Booleans may be written as YAML booleans, the role passes them as `true` and `false`.
The time zone of the container is `wallabag_timezone`, the image sets no `TZ` and the role sets no default for it.

wallabag stays configured with the environment, the role writes no configuration file:
`entrypoint.sh` of the image writes `app/config/parameters.yml` from its template with `envsubst` on every start,
a file of the role would be overwritten, and the entrypoint reads `SYMFONY__ENV__DATABASE_DRIVER`, `_HOST` and `_PORT` itself
to wait for the database and to install wallabag with sqlite. `parameters.yml` cannot read files.

```yaml
wallabag_environment:
  SYMFONY__ENV__DOMAIN_NAME: 'https://wallabag.example.org'
  SYMFONY__ENV__DATABASE_DRIVER: 'pdo_mysql'
  SYMFONY__ENV__DATABASE_HOST: 'mariadb'
  SYMFONY__ENV__DATABASE_PORT: 3306
  SYMFONY__ENV__DATABASE_NAME: 'wallabag'
  SYMFONY__ENV__DATABASE_USER: 'wallabag'
  SYMFONY__ENV__DATABASE_CHARSET: 'utf8mb4'
  SYMFONY__ENV__FROM_EMAIL: 'wallabag@example.org'
  SYMFONY__ENV__SERVER_NAME: 'wallabag'
  SYMFONY__ENV__FOSUSER_REGISTRATION: false
```

The database is sqlite in `<wallabag_home>/data/db` (`pdo_sqlite`, the default), MySQL or MariaDB (`pdo_mysql`) or PostgreSQL (`pdo_pgsql`).
`pdo_mysql` and `pdo_pgsql` need `SYMFONY__ENV__DATABASE_HOST`, `SYMFONY__ENV__DATABASE_PORT` and the secret `SYMFONY__ENV__DATABASE_PASSWORD`,
the image waits for the database with the host and the port.
The database and its user have to exist (e.g. created with `database_mysql`), the role does not use the root password of the database.
If the tables of wallabag are missing, the role runs `wallabag:install` once, it creates the schema and the internal settings,
with sqlite the image installs wallabag itself on the first start.

The image writes the variables with `envsubst` into the YAML file `app/config/parameters.yml`,
values with ` #` or starting with a special character of YAML (e.g. `*`, `&`, `!`, `%`, `@`, `` ` ``) break the file.

### Administrator

`wallabag_admin` is the administrator of wallabag with `name`, `email` and `password`, the password needs at least 8 characters.

```yaml
wallabag_admin:
  name: 'admin'
  email: 'admin@example.org'
  password: "{{ vault_wallabag_admin_password }}"
```

`wallabag:install` creates the super administrator `wallabag` with the password `wallabag`.
The role uses its module `app_wallabag_admin` (`library/`), it runs PHP with the kernel of wallabag in the container as `nobody`
and passes the name, the email and the password on stdin.
If no user has the name of `wallabag_admin`, the module takes over `wallabag` and changes its name, so no administrator with the default password remains,
otherwise it creates the user like `wallabag:install`.
It checks the password with the `sha512` encoder of wallabag and only sets it if it differs,
and keeps the email up to date and the user an enabled super administrator.
A changed name in `wallabag_admin` creates a new administrator, the former one stays.

### Secrets

Variables carrying secrets are passed as podman secrets with `wallabag_secrets` and must not be set in `wallabag_environment`.
Every secret has a `name`, the `data` and the `target`, the name of the variable, e.g. `SYMFONY__ENV__SECRET`.

```yaml
wallabag_secrets:
  - name: 'wallabag_symfony_env_secret'
    data: "{{ vault_wallabag_secret }}"
    target: 'SYMFONY__ENV__SECRET'
  - name: 'wallabag_symfony_env_database_password'
    data: "{{ vault_wallabag_db_password }}"
    target: 'SYMFONY__ENV__DATABASE_PASSWORD'
  - name: 'wallabag_symfony_env_mailer_dsn'
    data: "smtp://wallabag:{{ vault_wallabag_mail_password }}@mail.example.org:587"
    target: 'SYMFONY__ENV__MAILER_DSN'
```

The image writes `parameters.yml` with `envsubst` from the environment, it has no file variables, so the secrets are passed with `type=env`.
They are not part of the quadlet unit, but part of the environment of the container.
`SYMFONY__ENV__SECRET` is mandatory, without it the image uses a secret that is published in its repository.
The allowed targets are listed in `app_wallabag__secrets_allowed`: the secret, the password of the database, the DSN of the mailer with the password of the mail server,
the passwords of RabbitMQ and Redis and the DSN of Sentry with its key.

### Allowed variables

The role only allows the environment variables in `app_wallabag__environment_allowed` and the secrets in `app_wallabag__secrets_allowed`,
it stops before any change if unknown variables or secrets are set.
This prevents unexpected behavior by accident, e.g. by a typo, a deprecated variable or a variable that has to be passed as secret.
The variables are generated from `root/etc/wallabag/parameters.template.yml` and `php-wallabag.template.ini` of the image for wallabag 2.6.18,
the image ignores every other variable, without the secrets.
`POPULATE_DATABASE`, `MYSQL_ROOT_PASSWORD`, `POSTGRES_USER` and `POSTGRES_PASSWORD` of the initialization with the root password of the database are not allowed.
The booleans (`app_wallabag__environment_booleans`) are `SYMFONY__ENV__FOSUSER_REGISTRATION` and `SYMFONY__ENV__FOSUSER_CONFIRMATION`.
New versions of the image may add variables, the lists are generated again.
The check uses the environment and the secrets of the container after merging `wallabag_container`,
so variables set with `wallabag_container.environment` or `wallabag_container.secrets` are checked as well.

### Container

Ports, volumes, additional hosts (`etc_hosts`) and the dependencies are changed with `wallabag_container`, it is merged over the default of the container.
The dependencies of the quadlet unit are lists: `requires`, `wants`, `after`, `part_of` and `binds_to` are units,
`requires_mounts_for` are paths. They are written to `[Unit]` as `Requires=`, `Wants=`, `After=`, `PartOf=`, `BindsTo=` and `RequiresMountsFor=`.
The merge is not recursive, `wallabag_container.volumes` replaces the three directories,
`wallabag_container.environment` replaces the environment including `wallabag_environment`.
For a reverse proxy, e.g. Traefik, the labels are set with `wallabag_labels`.
The image runs `composer install` on every start before nginx listens, the role waits until `/api/info` answers, it shows the log of the service otherwise.

```yaml
wallabag_container:
  requires: [ 'mariadb.service' ]
  after: [ 'mariadb.service' ]
```

### Validation

The role checks before any change:

- `wallabag_secrets` is a list of entries with `name`, `data` and `target` with unique names, `SYMFONY__ENV__SECRET` is set, the secrets have no line breaks
- `SYMFONY__ENV__DOMAIN_NAME` is set, `SYMFONY__ENV__DATABASE_DRIVER` is `pdo_sqlite`, `pdo_mysql` or `pdo_pgsql`,
  `pdo_mysql` and `pdo_pgsql` have the host, the port and the secret `SYMFONY__ENV__DATABASE_PASSWORD`
- no secret is set in `wallabag_environment`, the booleans are `true` or `false`, values have no line breaks
- `wallabag_admin` has a valid name, a valid email and a password with at least 8 characters without line breaks
- only allowed environment variables without line breaks and allowed secrets are set in the container

If `wallabag_container` or `wallabag_environment` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Check mode

The role runs with `--check`, also on a host where it never ran, and reports the directories, the secrets and the quadlet unit.
The start, the wait for wallabag and the administrator do not run in check mode.

### Restart and updates

wallabag is restarted if it was running and a secret or the quadlet unit changed, otherwise it is started and enabled.
If the start fails, the role shows the error and the journal of the service.
A changed password of the administrator needs no restart.
Updates of the image are done by `container_update` with `wallabag_autoupdate_enabled: true` and `wallabag_autoupdate_schedule`,
without `wallabag_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

- The single variables are replaced by `wallabag_environment` and `wallabag_secrets`:
  - `wallabag_db_type` is `SYMFONY__ENV__DATABASE_DRIVER`, the default is `pdo_sqlite` now, existing installations with MySQL set `pdo_mysql`
  - `wallabag_db_host`, `wallabag_db_port`, `wallabag_db_user`, `wallabag_db_name` and `wallabag_db_charset` are `SYMFONY__ENV__DATABASE_HOST`, `_PORT`, `_USER`, `_NAME` and `_CHARSET`,
    the defaults of the role (port 3306, user and name `wallabag`, `utf8mb4`) are gone
  - `wallabag_db_pass` is the secret `SYMFONY__ENV__DATABASE_PASSWORD`, `wallabag_secret` the secret `SYMFONY__ENV__SECRET`
  - `wallabag_url` is `SYMFONY__ENV__DOMAIN_NAME`
  - `wallabag_locale`, `wallabag_server_name`, `wallabag_from_email`, `wallabag_user_registration` and `wallabag_user_confirmation`
    are `SYMFONY__ENV__LOCALE`, `SYMFONY__ENV__SERVER_NAME`, `SYMFONY__ENV__FROM_EMAIL`, `SYMFONY__ENV__FOSUSER_REGISTRATION` and `SYMFONY__ENV__FOSUSER_CONFIRMATION`
  - `wallabag_mail_host`, `wallabag_mail_port`, `wallabag_mail_user` and `wallabag_mail_password` are the secret `SYMFONY__ENV__MAILER_DSN`, e.g. `smtp://user:password@host:port`
- The former secret names (e.g. `wallabag_symfony_env_secret`) may stay.
- `wallabag_mysql_root_password`, `wallabag_postgres_password` and `wallabag_postgres_user` are removed, the root passwords are not part of the quadlet unit anymore,
  the database and its user have to exist, the role installs wallabag if its tables are missing.
- `wallabag_admin` is new and mandatory, it takes over `wallabag` or a user with the same name.
- `wallabag_environment`, `wallabag_secrets` and `wallabag_autoupdate_schedule` are new, `wallabag_labels` has no default anymore.
- The dependencies `wants`, `after`, `part_of`, `binds_to` and `requires_mounts_for` of `wallabag_container` are new.
- The service is not stopped on every run anymore, `podman___update_mode` is removed.
- The tag `app_wallabag` stays, the tag `app` is added.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-wallabag-default` | Only the mandatory variables, sqlite and the administrator |
| `molecule-wallabag` | IPv6, labels, MariaDB with the secret `SYMFONY__ENV__DATABASE_PASSWORD`, the DSN of the mailer, the name of the server, a boolean and the administrator |

`prepare` creates the podman network, pulls the images and starts MariaDB with the database and the user `wallabag` on `molecule-wallabag`.
`check` runs `converge` with `--check` on the new VMs.
`side_effect` runs the role with `wallabag_container` and `wallabag_environment` not a dictionary, an unknown environment variable, a secret without `target`, no `SYMFONY__ENV__SECRET`, the root password of the database as secret,
the database password in the environment, no `SYMFONY__ENV__DOMAIN_NAME`, an invalid database driver, `pdo_mysql` without the port, an invalid boolean,
a line break in a value, an administrator without password and a short password
and checks that it fails with the expected message and the quadlet unit is unchanged (tasks marked `expect ERROR`),
then it changes the name of the server and the password of the administrator on `molecule-wallabag`,
wallabag has to restart and the password changes without a new user and without a new installation,
`molecule-wallabag-default` runs again without a change and wallabag must not restart.
`verify` checks the quadlet unit with the secrets and without their values, the service without automatic restarts, the addresses, the time zone and the environment of the container, the API,
the login with the password, the refused former password and the refused default administrator, the administration of the users and the database.
The logins use the module `app_wallabag_test_login` in `molecule/default/library/`, it keeps the cookies of the session in one cookie jar,
because Symfony changes the session on the login and sets several cookies in the redirect.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd app_wallabag
MOLECULE_TART_IMAGE='debian' molecule test
```
