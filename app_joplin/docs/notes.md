Joplin Server runs in the container image [joplin/server](https://hub.docker.com/r/joplin/server) (`latest` by default) as podman quadlet.
`<joplin_home>/data` is mounted to `/home/joplin/data`, it contains the sqlite database.
The image runs Joplin Server as the user `joplin` with the uid 1001, the role creates `data` with the owner `joplin_uid` (default 1001),
the server listens on port 22300.

### Configuration

Joplin Server is configured with `joplin_environment`, which is merged over the defaults of the role
(`APP_PORT` 22300, `DB_CLIENT` `sqlite3` and `SQLITE_DATABASE` `/home/joplin/data/db.sqlite`),
see the [configuration of Joplin Server](https://github.com/laurent22/joplin/blob/dev/packages/server/src/env.ts).
`APP_BASE_URL` is mandatory, it is the public URL of Joplin Server used by the clients and in the emails.
Booleans may be written as YAML booleans, the role passes them as `true` and `false`.

```yaml
joplin_environment:
  APP_BASE_URL: 'https://joplin.example.org'
  DB_CLIENT: 'pg'
  POSTGRES_HOST: 'postgres'
  POSTGRES_USER: 'joplin'
  POSTGRES_DATABASE: 'joplin'
  MAILER_ENABLED: true
  MAILER_HOST: 'mail.example.org'
  MAILER_PORT: 587
  MAILER_SECURITY: 'starttls'
  MAILER_AUTH_USER: 'joplin@example.org'
  MAILER_NOREPLY_NAME: 'Joplin Server'
  MAILER_NOREPLY_EMAIL: 'joplin@example.org'
```

The database is sqlite in `<joplin_home>/data` (`sqlite3`, the default) or PostgreSQL (`pg`).
`pg` needs `POSTGRES_HOST` and the secret `POSTGRES_PASSWORD`, or the secret `POSTGRES_CONNECTION_STRING` instead.

### Administrator

`joplin_admin` is the administrator of Joplin Server with `email`, `password` and optionally `full_name`,
the password needs at least 8 characters and Joplin Server rejects weak passwords.

```yaml
joplin_admin:
  email: 'admin@example.org'
  password: "{{ vault_joplin_admin_password }}"
  full_name: 'Administrator'
```

The first start of Joplin Server creates the administrator `admin@localhost` with `DEFAULT_ADMIN_PASSWORD` (`admin` by default)
and never changes its password, so `DEFAULT_ADMIN_PASSWORD` is not allowed.
The role uses its module `app_joplin_admin` (`library/`), it runs node in the container with the models of Joplin Server
and passes the email, the password and the name on stdin.
Joplin Server identifies users by their email: if no user has the email of `joplin_admin`, the module takes over `admin@localhost`
and changes its email, so no administrator with the default password remains, otherwise it creates the user.
It checks the password with `checkPassword` of Joplin Server and only sets it if it differs,
and keeps the user an enabled administrator with a confirmed email.
A changed email in `joplin_admin` creates a new administrator, the former one stays.

### Secrets

Variables carrying secrets are passed as podman secrets with `joplin_secrets` and must not be set in `joplin_environment`.
Every secret has a `name`, the `data` and the `target`, the name of the variable, e.g. `POSTGRES_PASSWORD`.

```yaml
joplin_secrets:
  - name: 'joplin_database_password'
    data: "{{ vault_joplin_db_password }}"
    target: 'POSTGRES_PASSWORD'
  - name: 'joplin_smtp_password'
    data: "{{ vault_joplin_smtp_password }}"
    target: 'MAILER_AUTH_PASSWORD'
```

Joplin Server reads its configuration only from the environment, it has no file variables,
and the image starts the server with `pm2` without an env file, so the secrets are passed with `type=env`.
They are not part of the quadlet unit, but part of the environment of the container.
The allowed targets are listed in `app_joplin__secrets_allowed`: the passwords and connection strings of PostgreSQL and its replica,
the password of the mail server, the keys of Stripe, `MFA_ENCRYPTION_KEY`, the bind passwords of LDAP, `TRANSCRIBE_API_KEY`,
and `STORAGE_DRIVER` and `STORAGE_DRIVER_FALLBACK`, which contain the keys of S3.

### Allowed variables

The role only allows the environment variables in `app_joplin__environment_allowed` and the secrets in `app_joplin__secrets_allowed`,
it stops before any change if unknown variables or secrets are set.
This prevents unexpected behavior by accident, e.g. by a typo, a deprecated variable or a variable that has to be passed as secret.
The variables are generated from `defaultEnvValues` in `packages/server/src/env.ts` of Joplin Server v3.7.5,
Joplin Server ignores every other variable, without the secrets and `DEFAULT_ADMIN_PASSWORD`.
The booleans (`app_joplin__environment_booleans`) are the variables with a boolean default.
New versions of Joplin Server may add variables, the lists are generated again.
The check uses the environment and the secrets of the container after merging `joplin_container`,
so variables set with `joplin_container.environment` or `joplin_container.secrets` are checked as well.

### Container

Ports, volumes, additional hosts (`etc_hosts`) and dependencies (`requires`) are changed with `joplin_container`, it is merged over the default of the container.
The merge is not recursive, `joplin_container.volumes` replaces the data directory,
`joplin_container.environment` replaces the environment including `joplin_environment`.
The role waits until `/api/ping` of Joplin Server answers, Joplin Server migrates the database before it listens, it shows the log of the service otherwise.

### Validation

The role checks before any change:

- `joplin_secrets` is a list of entries with `name`, `data` and `target` with unique names, the secrets have no line breaks
- `APP_BASE_URL` is set, `DB_CLIENT` is `sqlite3` or `pg`, `pg` has `POSTGRES_HOST` and `POSTGRES_PASSWORD` or `POSTGRES_CONNECTION_STRING`
- no secret is set in `joplin_environment`, the booleans are `true` or `false`, values have no line breaks
- `joplin_admin` has a valid email other than `admin@localhost`, a password with at least 8 characters and a `full_name` without line breaks
- only allowed environment variables and secrets are set in the container

If `joplin_container` is no dictionary, merging it with the default fails before anything changes.

### Restart and updates

Joplin Server is restarted if it was running and a secret or the quadlet unit changed, otherwise it is started and enabled.
A changed password of the administrator needs no restart.
Updates of the image are done by `container_update` with `joplin_autoupdate_enabled: true` and `joplin_autoupdate_schedule`,
without `joplin_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

- The single variables are replaced by `joplin_environment` and `joplin_secrets`:
  - `joplin_base_url` is `APP_BASE_URL`, `joplin_port` is `APP_PORT`
  - `joplin_db_host`, `joplin_db_port`, `joplin_db_user` and `joplin_db_name` are `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER` and `POSTGRES_DATABASE`
  - `joplin_db_pass` is the secret `POSTGRES_PASSWORD`, the former secret name `joplin_database_password` may stay
  - `joplin_mailer_enabled`, `joplin_mailer_host`, `joplin_mailer_port`, `joplin_mailer_security`, `joplin_mailer_auth_user`,
    `joplin_mailer_noreply_name` and `joplin_mailer_noreply_mail` are `MAILER_ENABLED`, `MAILER_HOST`, `MAILER_PORT`, `MAILER_SECURITY`,
    `MAILER_AUTH_USER`, `MAILER_NOREPLY_NAME` and `MAILER_NOREPLY_EMAIL`, the defaults of the role (e.g. `starttls` on port 25) are gone
  - `joplin_mailer_auth_password` is the secret `MAILER_AUTH_PASSWORD`, the former secret name `joplin_smtp_password` may stay
- The database is `sqlite3` by default now, existing installations with PostgreSQL set `DB_CLIENT: pg`.
- `joplin_home` and `joplin_admin` are new and mandatory, `joplin_admin` takes over `admin@localhost` or a user with the same email.
- `joplin_uid`, `joplin_autoupdate_schedule` and the other variables of Joplin Server are new.
- The volumes `/etc/localtime` and `/etc/timezone` are removed, the timezone is set by podman.
- The service is not stopped on every run anymore, `podman___update_mode` is removed.
- The tag `app_joplin` stays, the tag `app` is added.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-joplin-default` | Only the mandatory variables, sqlite and the administrator |
| `molecule-joplin` | IPv6, labels, PostgreSQL with the secret `POSTGRES_PASSWORD`, the name of the application, a boolean and the administrator with a name |

`prepare` creates the podman network, pulls the images and starts PostgreSQL on `molecule-joplin`.
`side_effect` runs the role with `joplin_container` not a dictionary, a secret without `target`, an unknown secret,
the database password in the environment, no `APP_BASE_URL`, an invalid database client, `pg` without the host, an invalid boolean,
a line break in a value, `DEFAULT_ADMIN_PASSWORD` in the environment, an administrator without password and a short password
and checks that it fails with the expected message and the quadlet unit is unchanged (tasks marked `expect ERROR`),
then it changes the name of the application and the password of the administrator on `molecule-joplin`,
Joplin Server has to restart and the password changes without a new user.
`verify` checks the quadlet unit with the secrets and without their values, the service, the addresses and the environment of the container,
the login to the API with the password, the refused former password and the refused `admin@localhost`,
the administrator, the name of the application and the database.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd app_joplin
MOLECULE_TART_IMAGE='debian' molecule test
```
