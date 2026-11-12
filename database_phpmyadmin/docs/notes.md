phpMyAdmin runs in the official container image [phpmyadmin](https://hub.docker.com/_/phpmyadmin) (`latest` by default, `phpmyadmin_version` sets the tag) as podman quadlet.
The image contains Apache and PHP, the web interface listens on port 80. phpMyAdmin keeps no data in the container, the role creates no directories.
The database servers are not part of the role.

### Configuration

phpMyAdmin is configured completely with environment variables in `phpmyadmin_environment`, merged over the default of the role.
The default sets `TZ` to `phpmyadmin_timezone`, the passwords are passed with `phpmyadmin_secrets` (see Secrets). Values are strings, e.g. `'3306'`.

phpMyAdmin needs a server, one of `PMA_HOST`, `PMA_HOSTS`, `PMA_SOCKET`, `PMA_SOCKETS` or `PMA_ARBITRARY` has to be set,
the role checks it before it changes anything.
The variables are described in the [documentation of the image](https://hub.docker.com/_/phpmyadmin), e.g.
`PMA_PORT`, `PMA_ABSOLUTE_URI` for a reverse proxy, `PMA_PMADB`, `PMA_CONTROLUSER` and `PMA_CONTROLHOST` for the configuration storage,
`UPLOAD_LIMIT`, `MEMORY_LIMIT` and `MAX_EXECUTION_TIME` for PHP.
`PMA_CONFIG_BASE64` and `PMA_USER_CONFIG_BASE64` replace `config.inc.php` or add `config.user.inc.php`, both base64 encoded.

```yaml
phpmyadmin_environment:
  PMA_HOST: 'mariadb'
  PMA_PORT: '3306'
  PMA_ABSOLUTE_URI: 'https://phpmyadmin.example.org/'
  PMA_PMADB: 'phpmyadmin'
  PMA_CONTROLUSER: 'phpmyadmin'
  UPLOAD_LIMIT: '64M'
```

The tables of the configuration storage in `PMA_PMADB` are not created by the role,
phpMyAdmin creates them after the login, see the [documentation of phpMyAdmin](https://docs.phpmyadmin.net/en/latest/setup.html#phpmyadmin-configuration-storage).

### Secrets

`phpmyadmin_secrets` is a list of podman secrets with `name`, `data` and `target`, the usual name of the variable, e.g. `PMA_CONTROLPASS`.
The role creates the secret, mounts it to `/run/secrets/<name>` and sets the file variable of the target, e.g. `PMA_CONTROLPASS_FILE=/run/secrets/<name>`,
the entrypoint of the image reads the file at the start, so passwords are neither part of the quadlet unit nor of the environment of the container.
No secret is required.

| Target | File variable set by the role | Description |
|---|---|---|
| `PMA_CONTROLPASS` | `PMA_CONTROLPASS_FILE` | Password of `PMA_CONTROLUSER` for the configuration storage |
| `PMA_PASSWORD` | `PMA_PASSWORD_FILE` | Password of `PMA_USER` for the authentication type `config`, every visitor is logged in without a login form |

The targets are the keys of `database_phpmyadmin__secret_files`. Neither a target nor its file variable may be set in `phpmyadmin_environment`.

```yaml
phpmyadmin_secrets:
  - name: 'phpmyadmin_controlpass'
    data: "{{ vault_phpmyadmin_controlpass }}"
    target: 'PMA_CONTROLPASS'
```

The entrypoint reads `MYSQL_ROOT_PASSWORD_FILE` and `MYSQL_PASSWORD_FILE` as well, phpMyAdmin does not use them, they are not allowed.

### Allowed variables

The role only allows the environment variables in `database_phpmyadmin__environment_allowed` and the secrets with a target in `database_phpmyadmin__secret_files`,
it stops before any change if unknown variables or secrets are set.
This prevents unexpected behavior by accident, e.g. by a typo or a variable that has to be passed as secret.
The check uses the environment and the secrets of the container after merging `phpmyadmin_container`,
so variables set with `phpmyadmin_container.environment` are checked as well.

Allowed environment variables:

- the variables read by `config.inc.php` of the image (`PMA_*` without the passwords, `MAX_EXECUTION_TIME`, `MEMORY_LIMIT`, `UPLOAD_LIMIT`)
- the variables of `docker-entrypoint.sh` and the `Dockerfile` of the image: `PMA_CONFIG_BASE64`, `PMA_USER_CONFIG_BASE64`, `HIDE_PHP_VERSION`,
  `APACHE_PORT`, `SESSION_SAVE_PATH` and `TZ`
- the file variables of the secrets (`PMA_CONTROLPASS_FILE`, `PMA_PASSWORD_FILE`),
  the role sets them from `phpmyadmin_secrets`, they must not be set in `phpmyadmin_environment`

The list is generated from `config.inc.php`, `docker-entrypoint.sh` and `apache/Dockerfile` of [phpmyadmin/docker](https://github.com/phpmyadmin/docker)
for phpMyAdmin 5.2.3, new versions of the image may add variables.

### Container

Ports, volumes, additional hosts (`etc_hosts`) and dependencies (`requires`) are changed with `phpmyadmin_container`, it is merged over the default of the container.
The merge is not recursive, `phpmyadmin_container.environment` replaces the environment including `phpmyadmin_environment`, use `phpmyadmin_environment` instead.
For a reverse proxy, e.g. Traefik, the labels are set with `phpmyadmin_labels`.

### Validation

The role checks before any change:

- `phpmyadmin_secrets` is a list of entries with `name`, `data` and `target` and unique names
- one of the variables of the server is set in `phpmyadmin_environment`
- neither a secret nor its file variable is set in `phpmyadmin_environment`
- only allowed environment variables and secrets are set in the container

If `phpmyadmin_container` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Restart and updates

phpMyAdmin is restarted if it was running and a secret or the quadlet unit changed, e.g. after changing `phpmyadmin_environment`, otherwise it is started and enabled.
Updates of the image are done by `container_update` with `phpmyadmin_autoupdate_enabled: true` and `phpmyadmin_autoupdate_schedule`,
without `phpmyadmin_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

The single variables of former versions are replaced by `phpmyadmin_environment` and `phpmyadmin_secrets`:

- `phpmyadmin_db_host` is `PMA_HOST`
- `phpmyadmin_db_port` is `PMA_PORT`, the former default `3306` is the default of phpMyAdmin
- `phpmyadmin_db` is `PMA_PMADB`, the former default `phpmyadmin` has to be set
- `phpmyadmin_db_user` is `PMA_CONTROLUSER`, the former default `phpmyadmin` has to be set
- `phpmyadmin_db_pass` is a secret with the target `PMA_CONTROLPASS`
- `phpmyadmin_base_url` is `PMA_ABSOLUTE_URI`

The configuration storage and the control user were mandatory, now they are optional.
The password of the control user is mounted as file now instead of being passed as environment variable,
the fixed name of the secret `pma_controluser_password` is gone, the name is free. The former secret is not removed by the role,
remove it with `podman secret rm pma_controluser_password`.
The image is `docker.io/library/phpmyadmin`, the same image as the former `docker.io/phpmyadmin`, the tag is set with `phpmyadmin_version`.
`phpmyadmin_labels` has no default anymore, without it the container has no labels.
`podman___update_mode` is not evaluated anymore, the role neither stops the container nor pulls the image or recreates the container.
The tag `database_phpmyadmin` stays, the tag `database` is added.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-phpmyadmin-default` | Only the mandatory variables and `PMA_HOST` |
| `molecule-phpmyadmin` | IPv6, labels, `PMA_PORT`, `PMA_ABSOLUTE_URI`, the configuration storage with `PMA_PMADB`, `PMA_CONTROLUSER` and its password from a secret with the target `PMA_CONTROLPASS` |

`prepare` installs curl, creates the podman network, pulls the images and starts a MariaDB container with a database and a user.
`side_effect` runs the role with `phpmyadmin_container` not a dictionary, a secret without `target`, without a server,
the password of the control user and its file variable in the environment, an unknown environment variable in `phpmyadmin_environment` and in `phpmyadmin_container.environment` and an unknown secret
and checks that it fails with the expected message and the quadlet unit is unchanged (tasks marked `expect ERROR`),
then it changes `MEMORY_LIMIT` on `molecule-phpmyadmin`, the quadlet unit changes and phpMyAdmin has to restart.
`verify` checks the quadlet unit with the mounted secret, the service, the addresses and the environment of the container
with the file variable set by the role and without passwords, the file of the secret and the password exported by the entrypoint,
logs in with the user of the database using curl with a cookie file and checks the list of the databases.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd database_phpmyadmin
MOLECULE_TART_IMAGE='debian' molecule test
```
