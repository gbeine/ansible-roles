phpRedisAdmin runs in the container image [erikdubbelboer/phpredisadmin](https://hub.docker.com/r/erikdubbelboer/phpredisadmin) (`latest` by default, `phpredisadmin_version` sets the tag) as podman quadlet.
The image runs the built-in web server of PHP, the web interface listens on port 80. phpRedisAdmin keeps no data, the role creates no directories.
The Redis servers are not part of the role.

### Configuration

phpRedisAdmin is configured completely with environment variables in `phpredisadmin_environment`, merged over the default of the role.
The default sets `TZ` to `phpredisadmin_timezone`, the passwords are passed with `phpredisadmin_secrets` (see Secrets). Values are strings, e.g. `'true'`.

The options of phpRedisAdmin are read by `includes/config.environment.inc.php` of the image, e.g. `FILTER`, `SEPERATOR`, `SCAN_SIZE`, `HIDE_EMPTY_DBS` or `COOKIE_AUTH`.
The web interface needs an authentication: `ADMIN_USER` together with a secret with the target `ADMIN_PASS`,
or `ALLOW_NO_AUTH: 'true'` for an instance without login, e.g. behind a reverse proxy with its own authentication.
Without `COOKIE_AUTH: 'true'` phpRedisAdmin uses the HTTP digest authentication.

```yaml
phpredisadmin_keys:
  redis: [ 1, 2 ]

phpredisadmin_environment:
  ADMIN_USER: 'admin'
  REDIS_1_HOST: 'redis'
  REDIS_1_NAME: 'Cache'
  REDIS_2_HOST: 'redis-sessions'
  REDIS_2_NAME: 'Sessions'
  REDIS_2_DATABASES: '4'

phpredisadmin_secrets:
  - name: 'phpredisadmin_admin_pass'
    data: "{{ vault_phpredisadmin_admin_pass }}"
    target: 'ADMIN_PASS'
  - name: 'phpredisadmin_redis_sessions'
    data: "{{ vault_redis_sessions_password }}"
    target: 'REDIS_2_AUTH'
```

### Options with keys

The Redis servers are numbered, phpRedisAdmin reads `REDIS_1_*`, `REDIS_2_*` and so on and stops at the first number without `REDIS_<n>_HOST`.
The numbers are declared in `phpredisadmin_keys`, a dictionary with one list of keys per family, the role generates the allowed names from them.
The numbers have to start with 1 without gaps, every number needs `REDIS_<n>_HOST`.

| Family | Keys | Generated environment variables | Generated secret |
|---|---|---|---|
| `redis` | numbers from 1 | `REDIS_<n>_HOST`, `REDIS_<n>_NAME`, `REDIS_<n>_PORT`, `REDIS_<n>_SCHEME`, `REDIS_<n>_DATABASES` | `REDIS_<n>_AUTH`, the role sets `REDIS_<n>_AUTH_FILE` |

`REDIS_<n>_PORT` is `6379` by default, `REDIS_<n>_SCHEME` is `tcp` by default, e.g. `unix` for a socket in `REDIS_<n>_HOST`.
`REDIS_<n>_NAME` is shown in the web interface, the default is the host.

### Secrets

`phpredisadmin_secrets` is a list of podman secrets with `name`, `data` and `target`, the usual name of the variable, e.g. `ADMIN_PASS`.
No secret is required.

| Target | Passed as |
|---|---|
| `REDIS_<n>_AUTH`, the password of the Redis server `<n>` | file `/run/secrets/<name>`, the role sets `REDIS_<n>_AUTH_FILE` |
| `ADMIN_PASS`, the password of `ADMIN_USER` | environment variable `ADMIN_PASS` |

The passwords of the Redis servers are mounted to `/run/secrets/<name>` and read by phpRedisAdmin from `REDIS_<n>_AUTH_FILE`,
they are neither part of the quadlet unit nor of the environment of the container.
`ADMIN_PASS` is passed with `type=env`, because `includes/config.environment.inc.php` of the image reads it only with `getenv('ADMIN_PASS')`
and has no file variable for it. The password is not part of the quadlet unit, podman sets it when the container starts.

The targets are the keys of `database_phpredisadmin__secret_files` and `database_phpredisadmin__secrets_env`.
Neither a target nor a file variable may be set in `phpredisadmin_environment`.

### Allowed variables

The role only allows the environment variables in `database_phpredisadmin__environment_allowed` and the secrets with the targets listed in Secrets,
it stops before any change if unknown variables or secrets are set.
This prevents unexpected behavior by accident, e.g. by a typo or a variable that has to be passed as secret.
The check uses the environment and the secrets of the container after merging `phpredisadmin_container`,
so variables set with `phpredisadmin_container.environment` are checked as well.

Allowed environment variables:

- the options read by `includes/config.environment.inc.php` of the image: `COOKIE_AUTH`, `COUNT_ELEMENTS_PAGE`, `FASTER`, `FILTER`, `HIDE_EMPTY_DBS`, `KEYS`,
  `MAX_KEY_LEN`, `SCAN_SIZE`, `SCAN_MAX`, `SEPERATOR`, `SHOW_EMPTY_NAMESPACE_AS_KEY`, `ADMIN_USER` and `ALLOW_NO_AUTH`
- `PORT` of the `Dockerfile` and `TZ`
- the options of the Redis servers declared in `phpredisadmin_keys` (see Options with keys), including `REDIS_<n>_AUTH_FILE`,
  the role sets it from `phpredisadmin_secrets`, it must not be set in `phpredisadmin_environment`

The list is generated from `includes/config.environment.inc.php` and the `Dockerfile` of [phpRedisAdmin](https://github.com/erikdubbelboer/phpRedisAdmin) v1.28.0,
new versions of the image may add variables.

### Container

Ports, volumes, additional hosts (`etc_hosts`) and dependencies (`requires`) are changed with `phpredisadmin_container`, it is merged over the default of the container.
The merge is not recursive, `phpredisadmin_container.environment` replaces the environment including `phpredisadmin_environment`, use `phpredisadmin_environment` instead.
For a reverse proxy, e.g. Traefik, the labels are set with `phpredisadmin_labels`.

### Validation

The role checks before any change:

- `phpredisadmin_keys` is a dictionary of known families, every family is a list of unique numbers starting with 1 without gaps
- `phpredisadmin_secrets` is a list of entries with `name`, `data` and `target` and unique names
- at least one Redis server is declared and every declared server has `REDIS_<n>_HOST`
- `ADMIN_USER` and the secret `ADMIN_PASS` are set together, without both `ALLOW_NO_AUTH` is `'true'`
- `ALLOW_NO_AUTH` is `'true'` or `'false'`, the image compares it with the string `true`
- neither a secret nor a file variable is set in `phpredisadmin_environment`
- only allowed environment variables and secrets are set in the container

If `phpredisadmin_container` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Restart and updates

phpRedisAdmin is restarted if it was running and a secret or the quadlet unit changed, e.g. after changing `phpredisadmin_environment`, otherwise it is started and enabled.
Updates of the image are done by `container_update` with `phpredisadmin_autoupdate_enabled: true` and `phpredisadmin_autoupdate_schedule`,
without `phpredisadmin_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

The single variables of former versions are replaced by `phpredisadmin_environment` and `phpredisadmin_secrets`:

- `phpredisadmin_admin_user` is `ADMIN_USER`, the former default `pra` has to be set
- `phpredisadmin_admin_password` is a secret with the target `ADMIN_PASS`

The former role set no Redis server, phpRedisAdmin could not connect to any server. The servers are set with `phpredisadmin_keys` and `REDIS_<n>_*` now.
The fixed name of the secret `pra_admin_password` is gone, the name is free. The former secret is not removed by the role,
remove it with `podman secret rm pra_admin_password`.
The authentication was mandatory, now `ALLOW_NO_AUTH: 'true'` allows an instance without login.
The tag of the image is set with `phpredisadmin_version`.
`phpredisadmin_labels` has no default anymore, without it the container has no labels.
`podman___update_mode` is not evaluated anymore, the role neither stops the container nor pulls the image or recreates the container.
The tag `database_phpredisadmin` stays, the tag `database` is added.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-phpredisadmin-default` | Only the mandatory variables, one Redis server without password and `ALLOW_NO_AUTH` |
| `molecule-phpredisadmin` | IPv6, labels, two Redis servers, the password of the second one from a secret with the target `REDIS_2_AUTH`, `ADMIN_USER` and the secret `ADMIN_PASS` |

`prepare` installs curl, creates the podman network, pulls the images and starts two Redis containers, the second one with a password.
`side_effect` runs the role with `phpredisadmin_container` not a dictionary, `phpredisadmin_keys` not a dictionary, with an unknown family, a gap and a duplicate key,
a key without `REDIS_<n>_HOST`, `REDIS_3_HOST` without key, a secret without `target`, `ADMIN_USER` without `ADMIN_PASS`, without authentication,
`ALLOW_NO_AUTH: 'yes'`, `ADMIN_PASS` and `REDIS_1_AUTH_FILE` in the environment, an unknown environment variable in `phpredisadmin_container.environment` and an unknown secret
and checks that it fails with the expected message and the quadlet unit is unchanged (tasks marked `expect ERROR`),
then it changes `REDIS_2_NAME` on `molecule-phpredisadmin`, the quadlet unit changes and phpRedisAdmin has to restart.
`verify` checks the quadlet unit with the secrets, the service, the addresses and the environment of the container with the file variable set by the role,
the file of the secret, that the overview needs the login if `ADMIN_USER` is set and reads the overview with curl and the digest authentication,
every Redis server has to be shown without an error, so the password of the second server was read from the file.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd database_phpredisadmin
MOLECULE_TART_IMAGE='debian' molecule test
```
