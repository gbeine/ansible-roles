Paperless-ngx runs in the container image [paperless-ngx/paperless-ngx](https://github.com/paperless-ngx/paperless-ngx/pkgs/container/paperless-ngx) (`latest` by default) as podman quadlet.
`<paperless_ngx_home>/data`, `media`, `export` and `consume` are mounted to `/usr/src/paperless/data`, `media`, `export` and `consume`,
`data` contains the sqlite database and the search index, `media` the documents, new documents are put into `consume`.
The image runs Paperless-ngx as the user `paperless` with the uid and gid of `paperless_ngx_uid` (default 1000) and `paperless_ngx_gid` (defaults to `paperless_ngx_uid`),
the webserver listens on port 8000. Paperless-ngx needs Redis as broker.

### Configuration

Paperless-ngx is configured with `paperless_ngx_environment`, which is merged over the defaults of the role (`USERMAP_UID`, `USERMAP_GID` and `PAPERLESS_TIME_ZONE`),
see the [configuration of Paperless-ngx](https://docs.paperless-ngx.com/configuration/).
Booleans may be written as YAML booleans, the role passes them as `true` and `false`.

```yaml
paperless_ngx_environment:
  PAPERLESS_URL: 'https://paperless.example.org'
  PAPERLESS_DBENGINE: 'postgresql'
  PAPERLESS_DBHOST: 'postgres'
  PAPERLESS_DBUSER: 'paperless'
  PAPERLESS_DBNAME: 'paperless'
  PAPERLESS_OCR_LANGUAGE: 'deu+eng'
  PAPERLESS_OCR_LANGUAGES: 'deu'
```

The database is sqlite in `<paperless_ngx_home>/data` (the default), PostgreSQL (`postgresql`) or MariaDB (`mariadb`).
`postgresql` and `mariadb` need `PAPERLESS_DBHOST` and the secret `PAPERLESS_DBPASS`, without `PAPERLESS_DBENGINE` Paperless-ngx uses `postgresql` if `PAPERLESS_DBHOST` is set.
`PAPERLESS_OCR_LANGUAGES` installs additional languages of Tesseract on start, `PAPERLESS_OCR_LANGUAGE` selects the languages of the OCR.
`PAPERLESS_ENABLE_FLOWER` and `PAPERLESS_CONSUMER_DISABLE` of the image are enabled by any value, they are no booleans, leave them out to disable them.

### Administrator

`paperless_ngx_admin` is the administrator of Paperless-ngx with `name`, `email` and `password`, the password needs at least 8 characters.

```yaml
paperless_ngx_admin:
  name: 'admin'
  email: 'admin@example.org'
  password: "{{ vault_paperless_admin_password }}"
```

The image only creates an administrator from `PAPERLESS_ADMIN_USER` and `PAPERLESS_ADMIN_PASSWORD` if no superuser exists and never changes its password,
so these variables are not allowed. The role uses its module `app_paperless_ngx_admin` (`library/`), it runs the Django shell of Paperless-ngx in the container
like the script `createsuperuser` of the image and passes the name, the email and the password on stdin.
It creates the user, checks the password with `check_password` and only sets it if it differs, and keeps the email and the superuser flags up to date.

### Secrets

Variables carrying secrets are passed as podman secrets with `paperless_ngx_secrets` and must not be set in `paperless_ngx_environment`.
Every secret has a `name`, the `data` and the `target`, the name of the variable, e.g. `PAPERLESS_SECRET_KEY`.
The role creates the secret with `podman secret create`, mounts it to `/run/secrets/<name>` and sets `<target>_FILE`,
the image reads every variable `PAPERLESS_*_FILE` from the file, so the secret is neither part of the quadlet unit nor of the environment of the container.
The file must not end with a line break, the image warns about it.

```yaml
paperless_ngx_secrets:
  - name: 'paperless_secret_key'
    data: "{{ vault_paperless_secret_key }}"
    target: 'PAPERLESS_SECRET_KEY'
  - name: 'paperless_redis'
    data: "redis://:{{ vault_redis_password }}@redis:6379"
    target: 'PAPERLESS_REDIS'
  - name: 'paperless_dbpass'
    data: "{{ vault_paperless_db_password }}"
    target: 'PAPERLESS_DBPASS'
```

`PAPERLESS_SECRET_KEY` is mandatory, Paperless-ngx does not start without it. `PAPERLESS_REDIS` is mandatory, it is the URL of Redis and may contain its password.
`PAPERLESS_DBPASS` is mandatory for `postgresql` and `mariadb`.
The allowed targets are listed in `app_paperless_ngx__secret_files`: the URLs of Redis (`PAPERLESS_REDIS`, `PAPERLESS_READ_CACHE_REDIS_URL`),
the passwords of the database and the mail server, the API keys of the AI and the remote OCR, the client secrets of Gmail and Outlook
and `PAPERLESS_SOCIALACCOUNT_PROVIDERS`, which contains the client secrets of the social accounts.

### Allowed variables

The role only allows the environment variables in `app_paperless_ngx__environment_allowed` and the secrets in `app_paperless_ngx__secret_files`,
it stops before any change if unknown variables or secrets are set.
This prevents unexpected behavior by accident, e.g. by a typo, a deprecated variable or a variable that has to be passed as secret.
The variables are generated from all `PAPERLESS_*` variables in `src` of Paperless-ngx v3.4.2 without the tests and the variables of the s6 scripts of the image
(`USERMAP_UID`, `USERMAP_GID`, `PAPERLESS_OCR_LANGUAGES`, `PAPERLESS_PORT`, `PAPERLESS_BIND_ADDR`, `PAPERLESS_WEBSERVER_WORKERS`, `PAPERLESS_ENABLE_FLOWER`, `PAPERLESS_CONSUMER_DISABLE`),
without the secrets and `PAPERLESS_ADMIN_*`, plus the file variables of the secrets.
The booleans (`app_paperless_ngx__environment_booleans`) are the variables read with `get_bool_from_env`.
New versions of Paperless-ngx may add variables, the lists are generated again.
The check uses the environment of the container after merging `paperless_ngx_container`, so variables set with `paperless_ngx_container.environment` are checked as well.

### Container

Ports, volumes, additional hosts (`etc_hosts`) and dependencies (`requires`) are changed with `paperless_ngx_container`, it is merged over the default of the container.
The merge is not recursive, `paperless_ngx_container.volumes` replaces the four directories,
`paperless_ngx_container.environment` replaces the environment including `paperless_ngx_environment`.
The role waits until the login page of Paperless-ngx answers, the image migrates the database before the webserver starts, it shows the log of the service otherwise.

### Validation

The role checks before any change:

- `paperless_ngx_secrets` is a list of entries with `name`, `data` and `target` with unique names, `PAPERLESS_SECRET_KEY` and `PAPERLESS_REDIS` are set
- `PAPERLESS_DBENGINE` is `sqlite`, `postgresql` or `mariadb`, `postgresql` and `mariadb` have `PAPERLESS_DBHOST` and the secret `PAPERLESS_DBPASS`
- neither a secret nor its file variable is set in `paperless_ngx_environment`, the booleans are `true` or `false`, values and secrets have no line breaks
- `paperless_ngx_admin` has a valid name, a valid email and a password with at least 8 characters
- only allowed environment variables and secrets are set in the container

If `paperless_ngx_container` is no dictionary, merging it with the default fails before anything changes.

### Restart and updates

Paperless-ngx is restarted if it was running and a secret or the quadlet unit changed, otherwise it is started and enabled.
A changed password of the administrator needs no restart.
Updates of the image are done by `container_update` with `paperless_ngx_autoupdate_enabled: true` and `paperless_ngx_autoupdate_schedule`,
without `paperless_ngx_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

- `paperless_ngx_secrets` were passed with `type=env`, they are passed as files with `<target>_FILE` now, the names of the secrets stay.
- `PAPERLESS_SECRET_KEY` and `PAPERLESS_REDIS` are mandatory secrets, use the values of the existing installation.
  A changed `PAPERLESS_SECRET_KEY` logs out all users.
- `paperless_ngx_admin` is new and mandatory, an existing user with the same name gets the password and the email of `paperless_ngx_admin` and becomes a superuser.
- `paperless_ngx_environment`, `paperless_ngx_uid`, `paperless_ngx_gid` and `paperless_ngx_autoupdate_schedule` are new, the uid was fixed to 1000 before.
- The volumes `/etc/localtime` and `/etc/timezone` are removed, the timezone is set by podman and `PAPERLESS_TIME_ZONE`.
- The service is not stopped on every run anymore, `podman___update_mode` is removed.
- The tag `app_paperless_ngx` stays, the tag `app` is added.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-paperless-default` | Only the mandatory variables, sqlite, Redis and the administrator |
| `molecule-paperless` | IPv6, labels, PostgreSQL with the secret `PAPERLESS_DBPASS`, options, a boolean and the administrator |

`prepare` creates the podman network, pulls the images and starts Redis on both platforms and PostgreSQL on `molecule-paperless`.
`side_effect` runs the role with `paperless_ngx_container` not a dictionary, a secret without `target`, no `PAPERLESS_SECRET_KEY`, an unknown secret,
the database password in the environment, `postgresql` without the host, an invalid database engine, an invalid boolean, a line break in a value,
`PAPERLESS_ADMIN_PASSWORD` in the environment, an administrator without password and a short password
and checks that it fails with the expected message and the quadlet unit is unchanged (tasks marked `expect ERROR`),
then it changes the title and the password of the administrator on `molecule-paperless`, Paperless-ngx has to restart and the password changes without a new user.
`verify` checks the quadlet unit with the secrets as files and without their values, the service, the addresses and the environment of the container,
the login to the API with the password and the refused former password, the superuser, the title and the database.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd app_paperless_ngx
MOLECULE_TART_IMAGE='debian' molecule test
```
