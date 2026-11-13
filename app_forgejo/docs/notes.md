Forgejo runs in the container image [forgejo/forgejo](https://codeberg.org/forgejo/-/packages/container/forgejo) (`17` by default) as podman quadlet.
See [codeberg.org](https://codeberg.org/forgejo/-/packages/container/forgejo/versions) for the values of `forgejo_version`.
`forgejo_home` is mounted to `/data`, it contains the repositories, `app.ini` in `gitea/conf` and the keys of sshd.
The image runs Forgejo as the user `git` with the uid and gid of `forgejo_uid` and `forgejo_gid` (defaults to `forgejo_uid`),
Forgejo listens on port 3000 for HTTP and sshd of the image on port 22.

### Configuration

Forgejo is configured with `forgejo_environment`, which is merged over the defaults of the role
(`USER_UID`, `USER_GID`, `FORGEJO__database__DB_TYPE: mysql` and `FORGEJO__security__INSTALL_LOCK: true`).
The image writes every variable `FORGEJO__<section>__<KEY>` to `app.ini` on every start, see the [configuration cheat sheet](https://forgejo.org/docs/latest/admin/config-cheat-sheet/).
The section is written in lower case, `.` and `-` in the names of sections and keys are encoded as `_0X2E_` and `_0X2D_`,
e.g. `FORGEJO__repository_0X2E_pull_0X2D_request__DEFAULT_MERGE_STYLE` for `DEFAULT_MERGE_STYLE` in `[repository.pull-request]`.
Booleans may be written as YAML booleans, the role passes them as `true` and `false`.

```yaml
forgejo_environment:
  FORGEJO__database__HOST: 'mariadb:3306'
  FORGEJO__database__NAME: 'forgejo'
  FORGEJO__database__USER: 'forgejo'
  FORGEJO__server__DOMAIN: 'git.example.org'
  FORGEJO__server__ROOT_URL: 'https://git.example.org/'
  FORGEJO__server__SSH_DOMAIN: 'git.example.org'
  FORGEJO__service__DISABLE_REGISTRATION: true
```

The database is MariaDB or MySQL (`mysql`, the default), PostgreSQL (`postgres`) or `sqlite3`.
`mysql` and `postgres` need `FORGEJO__database__HOST`, `FORGEJO__database__NAME`, `FORGEJO__database__USER` and the secret `FORGEJO__database__PASSWD`.
`INSTALL_LOCK` skips the installation page, Forgejo creates the tables of its database on the first start.

The variables `APP_NAME`, `DB_*`, `SECRET_KEY`, `INSTALL_LOCK` and the other variables of the template of the image are only used
when the image creates `app.ini`, they are not allowed, `FORGEJO__<section>__<KEY>` replaces them.

### Options with keys

Some sections of `app.ini` have free names or free keys, e.g. the storage `my_minio` in `[storage.my_minio]` or `core.longpaths` in `[git.config]`.
The names are declared in `forgejo_keys`, a dictionary with one list per family, the role generates the exact names of the variables from them:

| Entry of `forgejo_keys` | Section | Generated variables |
|---|---|---|
| `storage` | `[storage.<key>]` | `FORGEJO__storage_0X2E_<key>__STORAGE_TYPE`, `PATH`, `SERVE_DIRECT` and the `MINIO_*` options, the secret `MINIO_SECRET_ACCESS_KEY` |
| `queue` | `[queue.<key>]` | the options of `[queue]`, the secret `CONN_STR` |
| `log` | `[log.<key>]` | the options of the log writers (`MODE`, `LEVEL`, `FILE_NAME`, …) |
| `markup` | `[markup.<key>]` | the options of external renderers (`ENABLED`, `FILE_EXTENSIONS`, `RENDER_COMMAND`, …) |
| `markup.sanitizer` | `[markup.sanitizer.<key>]` | `ELEMENT`, `ALLOW_ATTR`, `REGEXP` |
| `funding` | `[funding.<key>]` | `TEMPLATE`, `TITLE`, `INPUT_PATTERN` |
| `git.config` | `[git.config]` | `FORGEJO__git_0X2E_config__<key>` |
| `repository.mimetype_mapping` | `[repository.mimetype_mapping]` | `FORGEJO__repository_0X2E_mimetype_mapping__<key>` |
| `highlight.mapping` | `[highlight.mapping]` | `FORGEJO__highlight_0X2E_mapping__<key>` |
| `mailer.override_header` | `[mailer.override_header]` | `FORGEJO__mailer_0X2E_override_header__<key>` |

The names of sections are lower case letters, digits and `_ . -`, free keys may contain upper case letters and start with `.`, e.g. `.apk`.

```yaml
forgejo_keys:
  storage: [ 'minio' ]
  git.config: [ 'core.longpaths' ]
forgejo_environment:
  FORGEJO__storage_0X2E_minio__STORAGE_TYPE: 'minio'
  FORGEJO__storage_0X2E_minio__MINIO_ENDPOINT: 's3.example.org'
  FORGEJO__storage_0X2E_minio__MINIO_ACCESS_KEY_ID: 'forgejo'
  FORGEJO__storage_0X2E_minio__MINIO_BUCKET: 'forgejo'
  FORGEJO__attachment__STORAGE_TYPE: 'minio'
  FORGEJO__git_0X2E_config__core_0X2E_longpaths: true
forgejo_secrets:
  - name: 'forgejo_minio_secret'
    data: "{{ vault_forgejo_minio_secret }}"
    target: 'FORGEJO__storage_0X2E_minio__MINIO_SECRET_ACCESS_KEY'
```

The storages of Forgejo (`[storage]`, `[storage.attachments]`, `[storage.lfs]`, `[storage.avatars]`, `[storage.repo-avatars]`, `[storage.repo-archive]`,
`[storage.packages]`, `[storage.actions_log]` and `[storage.actions_artifacts]`) and the log writers `console`, `file` and `conn` need no keys.

### Administrator

`forgejo_admin` is the administrator of Forgejo with `name`, `email` and `password`, the password needs at least 8 characters (`MIN_PASSWORD_LENGTH`).
The names `admin` and other reserved names of Forgejo cannot be used.

```yaml
forgejo_admin:
  name: 'forgejo-admin'
  email: 'admin@example.org'
  password: "{{ vault_forgejo_admin_password }}"
```

The role uses its module `app_forgejo_admin` (`library/`), it checks the password with the API of Forgejo and basic authentication.
A missing administrator is created with `forgejo admin user create` in the container and a random password,
the password, the email and the administrator flag are set with the API and a temporary access token, which is deleted afterwards.
The password is only set if it differs and it is never an argument of a process or part of the log.
The API needs `ENABLE_BASIC_AUTHENTICATION` (the default) and HTTP on the address of the container.

### Secrets

Variables carrying secrets are passed as podman secrets with `forgejo_secrets` and must not be set in `forgejo_environment`.
Every secret has a `name`, the `data` and the `target`, the name of the variable, e.g. `FORGEJO__security__SECRET_KEY`.
The role creates the secret with `podman secret create`, mounts it to `/run/secrets/<name>` and sets `<target>__FILE`,
Forgejo reads every variable from the file `<variable>__FILE`, so the secret is neither part of the quadlet unit nor of the environment of the container.

```yaml
forgejo_secrets:
  - name: 'forgejo_secret_key'
    data: "{{ vault_forgejo_secret_key }}"
    target: 'FORGEJO__security__SECRET_KEY'
  - name: 'forgejo_database_passwd'
    data: "{{ vault_forgejo_db_password }}"
    target: 'FORGEJO__database__PASSWD'
```

`FORGEJO__security__SECRET_KEY` is mandatory, without it Forgejo uses a fixed key known to everybody, e.g. created with `forgejo generate secret SECRET_KEY`.
`FORGEJO__database__PASSWD` is mandatory for `mysql` and `postgres`. `INTERNAL_TOKEN` and the secrets of JWT are created by Forgejo if they are missing.
The image writes the values of the secrets to `app.ini` like all variables, they are part of `forgejo_home` like in every installation of Forgejo.

The allowed targets are listed in `app_forgejo__secret_files`: the passwords of the database, the mailer, the incoming email and the issue indexer,
`SECRET_KEY`, `INTERNAL_TOKEN`, the secrets of OAuth2, LFS, camo and the captchas, the token of the metrics,
the connection strings of the indexers, the queue, the cache (`[cache] HOST`) and the session (`PROVIDER_CONFIG`) and the secret keys of the storages.

### Allowed variables

The role only allows the environment variables in `app_forgejo__environment_allowed` and the secrets in `app_forgejo__secret_files`,
it stops before any change if unknown variables or secrets are set.
This prevents unexpected behavior by accident, e.g. by a typo, a wrong encoding of a section or a variable that has to be passed as secret.
The variables are generated from the sections and keys of `custom/conf/app.example.ini` of Forgejo v17.0.1 and the storages of Forgejo without the secrets,
plus the file variables of the secrets, `USER_UID` and `USER_GID` of the entrypoint and the `SSH_*` variables of sshd of the image
(`SSH_PORT`, `SSH_LISTEN_PORT`, `SSH_LOG_LEVEL`, `SSH_MAX_SESSIONS`, `SSH_MAX_STARTUPS`, `SSH_INCLUDE_FILE`, `SSH_ED25519_CERT`, `SSH_ECDSA_CERT`, `SSH_RSA_CERT`).
The booleans (`app_forgejo__environment_booleans`) are the keys with `true` or `false` in `app.example.ini`.
The variables of sections with free names or keys are generated from `forgejo_keys`.
New versions of Forgejo may add options, the lists are generated again.
The check uses the environment of the container after merging `forgejo_container`, so variables set with `forgejo_container.environment` are checked as well.

### Container

Ports (e.g. SSH), volumes, additional hosts (`etc_hosts`) and dependencies (`requires`) are changed with `forgejo_container`, it is merged over the default of the container.
The merge is not recursive, `forgejo_container.volumes` replaces `/data`, `forgejo_container.environment` replaces the environment including `forgejo_environment`.
The role waits until `/api/healthz` of Forgejo answers, Forgejo migrates the database on start, it shows the log of the service otherwise.

```yaml
forgejo_container:
  publish: [ '2222:22' ]
```

### Validation

The role checks before any change:

- `forgejo_keys` is a dictionary of known families with lists of valid and unique keys
- `forgejo_secrets` is a list of entries with `name`, `data` and `target` with unique names, `SECRET_KEY` is set
- `FORGEJO__database__DB_TYPE` is `mysql`, `postgres` or `sqlite3`, `mysql` and `postgres` have the variables of the database and the secret `PASSWD`
- neither a secret nor its file variable is set in `forgejo_environment`, the booleans are `true` or `false`, values and secrets have no line breaks
- `forgejo_admin` has a valid name, a valid email and a password with at least 8 characters
- only allowed environment variables and secrets are set in the container

If `forgejo_container` is no dictionary, merging it with the default fails before anything changes.

### Restart and updates

Forgejo is restarted if it was running and a secret or the quadlet unit changed, otherwise it is started and enabled.
The image writes the variables to `app.ini` on start, a changed password of the administrator needs no restart.
Updates of the image are done by `container_update` with `forgejo_autoupdate_enabled: true` and `forgejo_autoupdate_schedule`,
without `forgejo_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

The single variables are replaced by `forgejo_environment` and `forgejo_secrets`:

| Former variable | Now |
|---|---|
| `forgejo_db_type` | `FORGEJO__database__DB_TYPE`, `mysql` stays the default |
| `forgejo_db_host`, `forgejo_db_port` | `FORGEJO__database__HOST` with the port, e.g. `mariadb:3306` |
| `forgejo_db_name`, `forgejo_db_user` | `FORGEJO__database__NAME`, `FORGEJO__database__USER`, the former default `forgejo` is removed |
| `forgejo_db_pass` | secret `FORGEJO__database__PASSWD`, use the name `forgejo_database_passwd` to keep the existing secret |
| `forgejo_publish` | `forgejo_container.publish` |
| `forgejo_home`, `forgejo_ip`, `forgejo_ipv6`, `forgejo_network`, `forgejo_hostname`, `forgejo_timezone`, `forgejo_labels`, `forgejo_uid`, `forgejo_gid`, `forgejo_version`, `forgejo_container`, `forgejo_autoupdate_enabled` | stay |

- The database password was passed with `type=env`, it is passed as file with `FORGEJO__database__PASSWD__FILE` now.
- The default of `forgejo_version` changes from `16` to `17`.
- `FORGEJO__security__SECRET_KEY` is mandatory, use the value of `SECRET_KEY` in `<forgejo_home>/gitea/conf/app.ini` of an existing installation,
  otherwise the secrets of the users, e.g. their two-factor authentication, cannot be read anymore.
- `forgejo_admin` is new and mandatory, an existing administrator with the same name gets the password and the email of `forgejo_admin`.
- `forgejo_environment`, `forgejo_secrets`, `forgejo_keys` and `forgejo_autoupdate_schedule` are new.
- The volumes `/etc/localtime` and `/etc/timezone` are removed, the timezone is set by podman.
- The service is not stopped on every run anymore, `podman___update_mode` is removed.
- The tag `app_forgejo` stays, the tag `app` is added.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-forgejo-default` | Only the mandatory variables, MariaDB and the administrator |
| `molecule-forgejo` | IPv6, labels, PostgreSQL, the keys `git.config` and `storage`, options, the secret `FORGEJO__metrics__TOKEN` and the administrator |

`prepare` creates the podman network, pulls the images and starts MariaDB on `molecule-forgejo-default` and PostgreSQL on `molecule-forgejo`.
`side_effect` runs the role with `forgejo_container` not a dictionary, `forgejo_keys` not a dictionary, an unknown family, an invalid key,
a secret without `target`, no `SECRET_KEY`, the database password in the environment, `mysql` without the host, an invalid database type,
an invalid boolean, a line break in a value, an administrator without password, a short password, an option of a storage missing in `forgejo_keys`
and an unknown secret and checks that it fails with the expected message and the quadlet unit is unchanged (tasks marked `expect ERROR`),
then it changes the theme and the password of the administrator on `molecule-forgejo`, Forgejo has to restart and the password changes without a new administrator.
`verify` checks the quadlet unit with the secrets as files and without their values, the service, the addresses and the environment of the container,
the options in `app.ini`, `/api/healthz`, the login of the administrator with the password and the refused former password,
`/metrics` with the token and without and the tables of Forgejo in the database.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd app_forgejo
MOLECULE_TART_IMAGE='debian' molecule test
```
