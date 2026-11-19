BookStack runs in the container image of [linuxserver.io](https://docs.linuxserver.io/images/docker-bookstack/).
See the [BookStack documentation](https://www.bookstackapp.com/docs/) and its `.env.example.complete` for all keys.

### Configuration

BookStack reads `/config/www/.env`, the role writes `bookstack_config` to `<bookstack_home>/www/.env` (owner `bookstack_uid`, mode 0600).
`bookstack_config` is merged over the default of the role, the default sets `DB_DATABASE` and `DB_USERNAME` to `bookstack`.
Strings are written in double quotes, booleans as `true` or `false`, numbers as they are, `null` removes a key.
`APP_URL`, `DB_HOST`, `DB_DATABASE` and `DB_USERNAME` are required, the role checks them before it changes anything.

```yaml
bookstack_config:
  APP_URL: 'https://wiki.example.org'
  DB_HOST: '192.168.99.30'
  MAIL_DRIVER: 'smtp'
  MAIL_FROM: 'wiki@example.org'
  MAIL_PORT: 587
  SESSION_SECURE_COOKIE: true
```

`bookstack_environment` only takes the variables of the linuxserver image, e.g. `UMASK`.
`PUID` and `PGID` are set from `bookstack_uid` and `bookstack_gid` (defaults to `bookstack_uid`), they define the owner of the files in `bookstack_home`.
The time zone is set by podman with `bookstack_timezone` (`/etc/localtime` of the container).

### Secrets

`bookstack_secrets` is a list of podman secrets with `name`, `data` and `target`, the usual name of the key, e.g. `DB_PASSWORD`.
The role mounts every secret to `/run/secrets/<name>` and sets `FILE__<target>`, the linuxserver image reads the file at the start
and exports the key as environment variable, so the secret is neither part of the quadlet unit nor of `.env`.
`.env` cannot read files, the environment variables take precedence over `.env` (phpdotenv of Laravel does not overwrite them).
Allowed targets are `APP_KEY`, `DB_PASSWORD`, `DATABASE_URL`, `MYSQL_PASSWORD`, `MAIL_PASSWORD`, `LDAP_PASS`, `OIDC_CLIENT_SECRET`,
`STORAGE_S3_KEY`, `STORAGE_S3_SECRET` and the `*_APP_SECRET` of the social logins, they must not be set in `bookstack_config`.
`APP_KEY` and `DB_PASSWORD` are required.

`APP_KEY` is generated with `php artisan key:generate --show` or as `base64:` followed by 32 random bytes in base64, e.g. `echo "base64:$(openssl rand -base64 32)"`.

### Allowed variables

The role only allows the keys in `app_bookstack__config_allowed`, the environment variables in `app_bookstack__environment_allowed` and the secrets above,
it stops before any change if unknown keys, variables or secrets are set.
This prevents unexpected behavior by accident, e.g. by a typo or a key that has to be passed as secret.
The keys are generated from `.env.example.complete` and `app/Config/*.php` of BookStack v26.09.3 without the secrets and `TEST_DATABASE_URL`,
new versions of BookStack may add keys, the list in `defaults/main.yml` is generated again.
The environment allows `PUID`, `PGID`, `TZ` and `UMASK` of the linuxserver image and the file variables of the secrets (`FILE__<target>`) set by the role.
The check uses the environment of the container after merging `bookstack_container`, so variables set with `bookstack_container.environment` are checked as well.

### Container

Ports, volumes and additional hosts (`etc_hosts`) are changed with `bookstack_container`, it is merged over the default of the container.
The dependencies of the quadlet unit are lists in `bookstack_container`: `requires`, `wants`, `after`, `part_of` and `binds_to` are units,
`requires_mounts_for` are paths. They are written to `[Unit]` as `Requires=`, `Wants=`, `After=`, `PartOf=`, `BindsTo=` and `RequiresMountsFor=`.

```yaml
bookstack_container:
  requires: [ 'mariadb.service' ]
  after: [ 'mariadb.service' ]
```

### Validation

The role checks before any change:

- `bookstack_secrets` is a list of entries with `name`, `data` and `target` and unique names, the required secrets are set
- the required keys are set, neither a secret nor its file variable is set in `bookstack_config` or `bookstack_environment`
- only allowed keys, environment variables and secrets are used
- the values of `bookstack_config` are strings without line breaks, numbers, booleans or `null`, the environment contains no line breaks

If `bookstack_container` or `bookstack_config` is no dictionary, merging it with the default fails before anything changes.

### Check mode

The role runs with `--check` without failing, also on a host where it never ran before.
It reports the changes of `.env`, the secrets and the quadlet unit, the service is neither started nor restarted.

### Changes and restarts

A running container is restarted when `.env`, a secret or the quadlet unit changed, otherwise it is started and enabled.
If the start fails, the role stops with the last lines of the journal of the service.
Updates of the image are done by `container_update` with `bookstack_autoupdate_enabled: true` and `bookstack_autoupdate_schedule`.

### Migration

Former versions of the role generated `bookstack_home/www/.env` from single variables:

| Former variable | Former default | Now in `bookstack_config` or `bookstack_secrets` |
|---|---|---|
| `bookstack_url` | – | `APP_URL` |
| `bookstack_app_key` | – | secret with target `APP_KEY` |
| `bookstack_db_host` | – | `DB_HOST` |
| `bookstack_db_port` | `3306` | `DB_PORT` |
| `bookstack_db_name` | `bookstack` | `DB_DATABASE` |
| `bookstack_db_user` | `bookstack` | `DB_USERNAME` |
| `bookstack_db_pass` | – | secret with target `DB_PASSWORD` |
| `bookstack_mail_driver` | `sendmail` | `MAIL_DRIVER` (BookStack default `smtp`) |
| `bookstack_mail_from`, `bookstack_mail_from_name` | –, `BookStack` | `MAIL_FROM`, `MAIL_FROM_NAME` |
| `bookstack_mail_host`, `bookstack_mail_port` | `localhost`, `25` | `MAIL_HOST`, `MAIL_PORT` |
| `bookstack_mail_username`, `bookstack_mail_encryption` | `null` | `MAIL_USERNAME`, `MAIL_ENCRYPTION` |
| `bookstack_mail_password` | `null` | secret with target `MAIL_PASSWORD` |
| `bookstack_mail_sendmail_command` | `/usr/sbin/sendmail -bs` | `MAIL_SENDMAIL_COMMAND` |
| `bookstack_auth_method` | `standard` | `AUTH_METHOD` |
| `bookstack_ldap_*` | | `LDAP_*`, `bookstack_ldap_pass` as secret with target `LDAP_PASS` |
| `bookstack_oidc_*` | | `OIDC_*`, `bookstack_oidc_auto_initiate` as `AUTH_AUTO_INITIATE`, `bookstack_oidc_client_secret` as secret with target `OIDC_CLIENT_SECRET` |
| `bookstack_drawio` | – | `DRAWIO` |
| `bookstack_memcached_servers`, `bookstack_redis_servers` | – | `MEMCACHED_SERVERS`, `REDIS_SERVERS` (comma separated) |
| `bookstack_cache_driver`, `bookstack_session_driver` | `database` | `CACHE_DRIVER`, `SESSION_DRIVER` (BookStack default `file`) |
| `bookstack_session_cookie_name` | `bookstack_session` | `SESSION_COOKIE_NAME` |
| `bookstack_session_secure_cookie` | `true` | `SESSION_SECURE_COOKIE` (BookStack default `false`) |
| `bookstack_session_lifetime` | `120` | `SESSION_LIFETIME` |
| `bookstack_dark_mode` | `false` | `APP_DEFAULT_DARK_MODE` |
| `bookstack_view_books_as_grid` | `true` | `APP_VIEWS_BOOKS: 'grid'` (BookStack default `list`) |

The role does not set the former defaults anymore, BookStack uses its own defaults for keys not set in `bookstack_config`.
Set `MAIL_DRIVER`, `CACHE_DRIVER`, `SESSION_DRIVER`, `SESSION_SECURE_COOKIE` and `APP_VIEWS_BOOKS` explicitly to keep the former behavior.

Later changes of the role:

- The secrets are mounted as files and read with `FILE__<target>`, before they were passed as environment variables, `bookstack_secrets` stays the same.
- The keys of BookStack moved from `bookstack_environment` to `bookstack_config`, the role writes `www/.env` again.
  Every key keeps its name, e.g. `bookstack_environment.APP_URL` is `bookstack_config.APP_URL`, in `bookstack_environment` they are unknown variables now.
  `DB_DATABASE` and `DB_USERNAME` are defaults of `bookstack_config`.
- `/etc/timezone` and `/etc/localtime` of the host are not mounted anymore, the time zone is set by podman with `bookstack_timezone`.
- `wants`, `after`, `part_of`, `binds_to` and `requires_mounts_for` of `bookstack_container` are new, `requires` was supported before.
- `podman___update_mode` is not evaluated anymore, the role neither stops the container nor pulls the image or recreates the container.
- The tags are `app` and `app_bookstack`.

### Multiple instances

`tasks/loop.yml` runs the role for every entry in `bookstack_instances`.
Every entry takes the variables without the prefix `bookstack_`, e.g. `home`, `ip`, `config` and `secrets`.
Every instance needs its own container name (`container.name`) and its own secret names.

Include `tasks/loop.yml` in the play instead of the role:

```yaml
- name: 'Configure host.example.org'
  become: 'yes'
  hosts: 'host23'
  tasks:
    - tags: [ 'app_bookstack' ]
      ansible.builtin.include_tasks:
        file: 'roles/app_bookstack/tasks/loop.yml'
```

The instances are defined in `bookstack_instances`, e.g. in the host variables:

```yaml
bookstack_instances:
  - home: '/srv/container/bookstack-docs'
    hostname: 'docs.example.org'
    ip: '192.168.99.31'
    network: 'podman99'
    timezone: 'Europe/Berlin'
    uid: 1031
    container:
      name: 'bookstack-docs'
    config:
      APP_URL: 'https://docs.example.org'
      DB_HOST: '192.168.99.30'
      DB_DATABASE: 'bookstack_docs'
    secrets:
      - name: 'bookstack_docs_app_key'
        data: "{{ vault_bookstack_docs_app_key }}"
        target: 'APP_KEY'
      - name: 'bookstack_docs_db_password'
        data: "{{ vault_bookstack_docs_db_password }}"
        target: 'DB_PASSWORD'
```

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs are shared by all tart scenarios and live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-bookstack-default` | Only the mandatory variables, IPv4 only |
| `molecule-bookstack` | IPv4 and IPv6, dependencies of the quadlet unit, a string with quotes and a number in `bookstack_config` |

`prepare` sets up podman and the network `podman-molecule` with the role `container_podman`, pulls the images and starts a MariaDB container as database.
`check` runs `converge` with `--check` on the new VMs.
`side_effect` runs the role with `bookstack_container` and `bookstack_config` not a dictionary, a secret without name, without the secret of the application key,
the mail password and the file variable of the application key in the environment, a key of BookStack in the environment, without `APP_URL`,
an unknown key and the database password in `bookstack_config`, line breaks in `bookstack_config` and in the environment,
an unknown environment variable in `bookstack_container.environment` and an unknown secret
and checks that it fails with the expected message and the quadlet unit and `.env` are unchanged (tasks marked `expect ERROR`).
Then it waits for the first start and sets `APP_DEFAULT_DARK_MODE` on `molecule-bookstack`, `.env` changes and BookStack has to restart,
`molecule-bookstack-default` runs again without a change and must not restart.
`verify` checks the quadlet unit with the mounted secrets and the dependencies and without `/etc/localtime`, the podman secrets, the service,
the container addresses and the environment with `FILE__APP_KEY` and `FILE__DB_PASSWORD` without the secrets and the keys of BookStack,
the time zone of the container, `.env` with owner, mode and keys and without secrets, and requests the login page.
The first start of BookStack runs the database migrations, so the login page may take a few minutes.

The molecule scenario `loop` tests `tasks/loop.yml` in one VM `molecule-bookstack-loop`.
It deploys the two instances `bookstack-docs` (IPv4 only) and `bookstack-wiki` (IPv4 and IPv6) from `bookstack_instances`, each with its own container, quadlet unit, `.env`, secrets and database.
`verify` checks every instance like the scenario `default` and that the quadlet units only contain the secrets of their own instance.
The VMs need access to `lscr.io` and Docker Hub for the images.

Requirements on the controller: `tart`, `sshpass` (`brew install hudochenkov/sshpass/sshpass`), `molecule` and the collection `containers.podman`.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd app_bookstack
MOLECULE_TART_IMAGE='debian' molecule test
MOLECULE_TART_IMAGE='debian' molecule test -s loop
```
