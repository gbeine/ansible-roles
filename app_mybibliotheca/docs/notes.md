MyBibliotheca runs in the container image [pickles4evaaaa/mybibliotheca](https://hub.docker.com/r/pickles4evaaaa/mybibliotheca)
(`latest` by default, `mybibliotheca_version` sets the tag) as podman quadlet. Gunicorn listens on port 5054,
the data (covers, uploads, backups and the state of the database) is kept in `<mybibliotheca_home>/data`, mounted as `/app/data`.
The database is PostgreSQL, it is not part of the role.

### Configuration

MyBibliotheca is configured with environment variables in `mybibliotheca_environment`, merged over the default of the role.
The default sets `TZ` and `TIMEZONE` to `mybibliotheca_timezone`, `POSTGRES_PORT` to `5432` and `KUZU_DB_PATH` to `/app/data/kuzu`.
Booleans may be given as YAML booleans, the role passes them as `true` or `false`.

A new installation uses PostgreSQL if `POSTGRES_HOST`, `POSTGRES_DB` and `POSTGRES_USER` or the secret `POSTGRES_DSN` are set,
otherwise MyBibliotheca falls back to the embedded KuzuDB, which upstream only keeps for the migration of former installations.
The role always needs PostgreSQL. The database and its user have to exist, MyBibliotheca creates the schema at the start,
e.g. with the role `database_postgresql`. MyBibliotheca records the database in `/app/data/persistence_state.json`.

```yaml
mybibliotheca_environment:
  POSTGRES_HOST: 'postgresql'
  POSTGRES_DB: 'bibliotheca'
  POSTGRES_USER: 'bibliotheca'
  SITE_NAME: 'My Library'
  WORKERS: '4'
```

`WORKERS` sets the number of Gunicorn workers on PostgreSQL, the entrypoint allows 1 to 32.
Redis is optional, `CACHE_REDIS_URL` enables the shared cache and `SESSION_TYPE: 'redis'` with `REDIS_HOST` the sessions in Redis.

### Administrator

Without users MyBibliotheca redirects every visitor to the onboarding, the first visitor becomes the administrator.
So `mybibliotheca_admin` with `name`, `email` and `password` is mandatory, the module `app_mybibliotheca_admin` creates the administrator
right after the first start with the services of MyBibliotheca in the container, before the onboarding can be used.

On every run the module checks the password and only sets it if it differs, keeps the email up to date
and makes the user an active administrator without a forced password change.
The password has to meet the password policy of MyBibliotheca: at least `PASSWORD_MIN_LENGTH` characters (default 8, at most 128),
a letter and a digit or a special character. The name, the email and the password are passed to Python on stdin.

```yaml
mybibliotheca_admin:
  name: 'admin'
  email: 'admin@example.org'
  password: "{{ vault_mybibliotheca_admin_password }}"
```

The module fails if PostgreSQL is not the active database, e.g. for an existing installation on KuzuDB.

### Secrets

`mybibliotheca_secrets` is a list of podman secrets with `name`, `data` and `target`, the usual name of the variable, e.g. `POSTGRES_PASSWORD`.
MyBibliotheca reads all its settings with `os.getenv` and has no file variables, so the secrets are passed in the environment
of the container with `type=env,target=<target>`, they are not part of the quadlet unit.

`SECRET_KEY` is mandatory, without it the entrypoint generates a new key on every start and all sessions are lost.
One of `POSTGRES_PASSWORD` or `POSTGRES_DSN` is mandatory, the password in a DSN has to be percent-encoded.
The allowed targets are `SECRET_KEY`, `POSTGRES_PASSWORD`, `POSTGRES_DSN`, `DATABASE_URL`, `REDIS_PASSWORD`, `REDIS_URL`, `CACHE_REDIS_URL`,
`MAIL_PASSWORD`, `GOOGLE_BOOKS_API_KEY`, `GOOGLE_API_KEY` and `ISBN_API_KEY`, the URLs of the databases and of Redis contain passwords.
None of them may be set in `mybibliotheca_environment`.

```yaml
mybibliotheca_secrets:
  - name: 'mybibliotheca_secret_key'
    data: "{{ vault_mybibliotheca_secret_key }}"
    target: 'SECRET_KEY'
  - name: 'mybibliotheca_postgres_password'
    data: "{{ vault_mybibliotheca_postgres_password }}"
    target: 'POSTGRES_PASSWORD'
```

### Allowed variables

The role only allows the environment variables in `app_mybibliotheca__environment_allowed` and the secrets listed above,
it stops before any change if unknown variables or secrets are set.
This prevents unexpected behavior by accident, e.g. by a typo or a variable that has to be passed as secret.
The check uses the environment and the secrets of the container after merging `mybibliotheca_container`,
so variables set with `mybibliotheca_container.environment` are checked as well.

The list is generated from the `os.getenv` and `os.environ` calls of `app/`, `config.py` and `run.py`, `docker-entrypoint.sh`
and the `Dockerfile` of MyBibliotheca v3.0.3, new versions of the image may add variables. It leaves out:

- `KUZU_FORCE_RESET`, it deletes the database at the start
- the variables for development `DEV_ADMIN_USERNAME`, `DEV_ADMIN_PASSWORD`, `API_TEST_TOKEN` and `FLASK_ENV`,
  the administrator is set with `mybibliotheca_admin`
- `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `ADMIN_EMAIL` and `SECURITY_PASSWORD_SALT`, MyBibliotheca does not use them
  (the compose file of upstream sets `SECURITY_PASSWORD_SALT`, it can be dropped)
- the variables set by MyBibliotheca or the entrypoint itself, e.g. `HOSTNAME`, `POSTGRES_WORKERS` and `APP_VERSION`

### Container

Ports, volumes, additional hosts (`etc_hosts`) and dependencies (`requires`) are changed with `mybibliotheca_container`, it is merged over the default of the container.
The merge is not recursive, `mybibliotheca_container.environment` replaces the environment including `mybibliotheca_environment`, use `mybibliotheca_environment` instead.
For a reverse proxy, e.g. Traefik, the labels are set with `mybibliotheca_labels`.
The data directory belongs to the user 1000 with the mode `0755`, like the entrypoint sets it.

### Validation

The role checks before any change:

- `mybibliotheca_secrets` is a list of entries with `name`, `data` and `target` and unique names
- PostgreSQL is configured, `SECRET_KEY` and the password or the DSN of PostgreSQL are set
- no secret is set in `mybibliotheca_environment`, secrets and values contain no line breaks
- booleans are `true` or `false`, `WORKERS` is a number from 1 to 32
- `mybibliotheca_admin` is a dictionary with a valid name, email and password
- only allowed environment variables and secrets are set in the container

If `mybibliotheca_container` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Restart and updates

MyBibliotheca is restarted if it was running and a secret or the quadlet unit changed, e.g. after changing `mybibliotheca_environment`,
otherwise it is started and enabled. Afterwards the role waits up to 300 seconds for the login page (`/auth/login`) and shows the journal if MyBibliotheca does not answer.
Updates of the image are done by `container_update` with `mybibliotheca_autoupdate_enabled: true` and `mybibliotheca_autoupdate_schedule`,
without `mybibliotheca_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

The role is new, there are no former variables.
An existing installation on KuzuDB stays on KuzuDB until an administrator completes the database migration of MyBibliotheca
(Admin, Database Migration), the role fails at the administrator until then. Do not remove `data/kuzu` before the migration is verified.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-mybibliotheca-default` | Only the mandatory variables, PostgreSQL with `POSTGRES_HOST`, `POSTGRES_DB`, `POSTGRES_USER` and the secret `POSTGRES_PASSWORD` |
| `molecule-mybibliotheca` | IPv6, labels, PostgreSQL with the secret `POSTGRES_DSN`, `SITE_NAME`, `WORKERS` and a boolean |

`prepare` installs curl, creates the podman network, pulls the images and starts PostgreSQL with the database and its user on both VMs.
`side_effect` runs the role with `mybibliotheca_container` not a dictionary, a secret without `target`, without `SECRET_KEY`, without PostgreSQL,
the password of PostgreSQL in the environment, `KUZU_FORCE_RESET` and `SECURITY_PASSWORD_SALT`, `DEV_ADMIN_PASSWORD` as secret,
an invalid boolean, a line break in a value, too many workers, an administrator without password and a weak password
and checks that it fails with the expected message and the quadlet unit is unchanged (tasks marked `expect ERROR`),
then it changes `SITE_NAME`, the email and the password of the administrator on `molecule-mybibliotheca`,
MyBibliotheca has to restart and the administrator changes without a new user.
`verify` checks the quadlet unit with the secrets in the environment without their values, the service, the addresses and the environment of the container,
the health check and the state of the setup on PostgreSQL, logs in with curl and a cookie file with the password of the administrator,
a wrong password and the former password, opens the dashboard of the administration and checks the users in PostgreSQL.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd app_mybibliotheca
MOLECULE_TART_IMAGE='debian' molecule test
```
