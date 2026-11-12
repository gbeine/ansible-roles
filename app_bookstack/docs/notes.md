BookStack runs in the container image of [linuxserver.io](https://docs.linuxserver.io/images/docker-bookstack/) and is configured with environment variables.
See the [BookStack documentation](https://www.bookstackapp.com/docs/) and its `.env.example.complete` for all variables.

### Environment and secrets

All variables are set with `bookstack_environment`, which is merged over the defaults of the role.
Variables carrying secrets are passed as podman secrets with `bookstack_secrets` and must not be set in `bookstack_environment`.
Every secret has a `name`, the `data` and the `target`, the usual name of the variable, e.g. `DB_PASSWORD`.
The role creates the secret with `podman secret create`, mounts it to `/run/secrets/<name>` and sets `FILE__<target>`,
the linuxserver image reads the variable from this file at the start, so the secret is neither part of the quadlet unit nor of the environment of the container.
Allowed targets are `APP_KEY`, `DB_PASSWORD`, `DATABASE_URL`, `MYSQL_PASSWORD`, `MAIL_PASSWORD`, `LDAP_PASS`, `OIDC_CLIENT_SECRET`,
`STORAGE_S3_KEY`, `STORAGE_S3_SECRET` and the `*_APP_SECRET` of the social logins, they must not be set in `bookstack_environment`.

The role requires the following variables and checks them before it changes anything:

| Variable | Set with | Default of the role |
|---|---|---|
| `APP_URL` | `bookstack_environment` | – |
| `DB_HOST` | `bookstack_environment` | – |
| `DB_DATABASE` | `bookstack_environment` | `bookstack` |
| `DB_USERNAME` | `bookstack_environment` | `bookstack` |
| `APP_KEY` | `bookstack_secrets` | – |
| `DB_PASSWORD` | `bookstack_secrets` | – |

`PUID` and `PGID` are set from `bookstack_uid` and `bookstack_gid` (defaults to `bookstack_uid`), they define the owner of the files in `bookstack_home`.

`APP_KEY` is generated with `php artisan key:generate --show` or as `base64:` followed by 32 random bytes in base64, e.g. `echo "base64:$(openssl rand -base64 32)"`.

### Allowed variables

The role only allows the environment variables in `app_bookstack__environment_allowed` and the secrets above,
it stops before any change if unknown variables or secrets are set.
This prevents unexpected behavior by accident, e.g. by a typo or a variable that has to be passed as secret.
The check uses the environment and the secrets of the container after merging `bookstack_container`,
so variables set with `bookstack_container.environment` are checked as well.
The allowed variables are `PUID`, `PGID`, `TZ` and `UMASK` of the linuxserver image and the keys of BookStack,
generated from `.env.example.complete` and `app/Config/*.php` of BookStack v26.09.3 without the secrets and `TEST_DATABASE_URL`,
and the file variables of the secrets (`FILE__<target>`). The role sets them from `bookstack_secrets`, they must not be set in `bookstack_environment`.
New versions of BookStack may add keys, the list in `defaults/main.yml` is generated again.

### Validation

The role checks before any change that `bookstack_secrets` is a list of entries with `name`, `data` and `target` and unique names,
that the required variables and secrets are set, that neither a secret nor its file variable is set in `bookstack_environment`
and that only allowed variables and secrets are used.
If `bookstack_container` is no dictionary, merging it with the default fails before anything changes.

### Changes and restarts

A running container is restarted when a secret or the quadlet unit changed, e.g. after changing `bookstack_environment`.
The first start of the container does not trigger an additional restart.
Updates of the image are done by `container_update` with `bookstack_autoupdate_enabled: true` and `bookstack_autoupdate_schedule`.

### Migration from the single variables and the `.env` file

Former versions of the role generated `bookstack_home/www/.env` from single variables.
The role does not generate this file anymore, set the variables in `bookstack_environment` and `bookstack_secrets` instead:

| Former variable | Former default | Now |
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

The role does not set the former defaults anymore, BookStack uses its own defaults for variables not set in `bookstack_environment`.
Set `MAIL_DRIVER`, `CACHE_DRIVER`, `SESSION_DRIVER`, `SESSION_SECURE_COOKIE` and `APP_VIEWS_BOOKS` explicitly to keep the former behavior.

Environment variables take precedence over `www/.env`, but values only set in the old file still apply.
Remove `bookstack_home/www/.env` after the migration, the container creates a new one from the environment variables.
The old file also contains the database password and the application key in plain text.

Later changes of the role:

- The secrets are mounted as files and read with `FILE__<target>`, before they were passed as environment variables, `bookstack_secrets` stays the same.
- `podman___update_mode` is not evaluated anymore, the role neither stops the container nor pulls the image or recreates the container.
- The tags are `app` and `app_bookstack`.

### Multiple instances

`tasks/loop.yml` runs the role for every entry in `bookstack_instances`.
Every entry takes the variables without the prefix `bookstack_`, e.g. `home`, `ip`, `environment` and `secrets`.
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
    environment:
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
The base VM is cloned for every platform and the clones are deleted afterwards, the base VM itself is never changed.
The playbooks creating and destroying the VMs are shared by all tart scenarios and live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-bookstack-ipv4-only` | Container with IPv4 address only |
| `molecule-bookstack-ipv6` | Container with IPv4 and IPv6 address |

`prepare` sets up podman and the network `podman-molecule` with the role `container_podman`, pulls the images and starts a MariaDB container as database.
`side_effect` runs the role with `bookstack_container` not a dictionary, a secret without name, without the secret of the application key,
the mail password and the file variable of the application key in the environment, an unknown environment variable in `bookstack_environment` and in `bookstack_container.environment` and an unknown secret
and checks that it fails with the expected message and the quadlet unit is unchanged (tasks marked `expect ERROR`),
then it waits for the first start and sets `APP_DEFAULT_DARK_MODE` on `molecule-bookstack-ipv6`, the quadlet unit changes and BookStack has to restart.
`verify` checks the quadlet unit with the mounted secrets, the podman secrets, the service, the container addresses and the environment with `FILE__APP_KEY` and `FILE__DB_PASSWORD` without the secrets,
requests the login page and checks that `www/.env` was not generated by the role.
The first start of BookStack runs the database migrations, so the login page may take a few minutes.

The molecule scenario `loop` tests `tasks/loop.yml` in one VM `molecule-bookstack-loop`.
It deploys the two instances `bookstack-docs` (IPv4 only) and `bookstack-wiki` (IPv4 and IPv6) from `bookstack_instances`, each with its own container, quadlet unit, secrets and database.
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
