pgAdmin runs in the container image [dpage/pgadmin4](https://hub.docker.com/r/dpage/pgadmin4) (`latest` by default, `pgadmin_version` sets the tag) as podman quadlet.
The image runs pgAdmin with gunicorn as the user 5050, the web interface listens on port 80.
Below `pgadmin_home` the role creates `data`, owned by the user 5050 and mounted to `/var/lib/pgadmin`,
it holds the database of pgAdmin with the users, the servers and the preferences, the sessions and the storage of the users.
The PostgreSQL servers are not part of the role.

### Configuration

pgAdmin is configured completely with environment variables in `pgadmin_environment`, merged over the default of the role.
The default sets `TZ` to `pgadmin_timezone`, the passwords are passed with `pgadmin_secrets` (see Secrets).
`PGADMIN_DEFAULT_EMAIL` is required, it is the email address of the admin created by the first start.

The variables of the image are described in the [documentation of the container](https://www.pgadmin.org/docs/pgadmin4/latest/container_deployment.html),
e.g. `PGADMIN_LISTEN_PORT`, `PGADMIN_DISABLE_POSTFIX` or `PGADMIN_REPLACE_SERVERS_ON_STARTUP`.
Every setting of `config.py` of pgAdmin is set with `PGADMIN_CONFIG_<SETTING>`, the image writes it as `<SETTING> = <value>` to `config_distro.py` at every start.
The values are Python literals, strings need quotes, e.g. `"'smtp.example.org'"`, `true` and `false` are written as `True` and `False`.

```yaml
pgadmin_environment:
  PGADMIN_DEFAULT_EMAIL: 'admin@example.org'
  PGADMIN_CONFIG_ENHANCED_COOKIE_PROTECTION: 'True'
  PGADMIN_CONFIG_MAIL_SERVER: "'smtp.example.org'"
  PGADMIN_CONFIG_MAIL_PORT: '587'
  PGADMIN_CONFIG_MAIL_USE_TLS: 'True'
  PGADMIN_CONFIG_MAIL_USERNAME: "'pgadmin@example.org'"
  PGADMIN_CONFIG_SECURITY_EMAIL_SENDER: "'pgadmin@example.org'"
```

`pgadmin_servers` is the content of `servers.json`, a dictionary with `Servers`, see the [documentation of the import](https://www.pgadmin.org/docs/pgadmin4/latest/import_export_servers.html).
The role writes it to `pgadmin_home/servers.json` and mounts it to `/pgadmin4/servers.json`, a change restarts pgAdmin.
pgAdmin loads the servers for `PGADMIN_DEFAULT_EMAIL` only at the first start with an empty data directory,
with `PGADMIN_REPLACE_SERVERS_ON_STARTUP: 'True'` it replaces the servers of the admin at every start.
The first start creates the database of pgAdmin and loads the servers afterwards, if pgAdmin is restarted in between, e.g. by a second run of the role with changes,
the servers are not loaded, `PGADMIN_REPLACE_SERVERS_ON_STARTUP: 'True'` loads them at the next start.

```yaml
pgadmin_servers:
  Servers:
    '1':
      Name: 'PostgreSQL'
      Group: 'Servers'
      Host: 'postgresql'
      Port: 5432
      MaintenanceDB: 'postgres'
      Username: 'postgres'
      SSLMode: 'prefer'
```

### Secrets

`pgadmin_secrets` is a list of podman secrets with `name`, `data` and `target`, the usual name of the variable, e.g. `PGADMIN_DEFAULT_PASSWORD`.
The secret `PGADMIN_DEFAULT_PASSWORD` is required.

| Target | Passed as |
|---|---|
| `PGADMIN_DEFAULT_PASSWORD`, the password of the admin | file `/run/secrets/<name>`, the role sets `PGADMIN_DEFAULT_PASSWORD_FILE` |
| `PGADMIN_CONFIG_CONFIG_DATABASE_URI`, an external configuration database | file `/run/secrets/<name>`, the role sets `PGADMIN_CONFIG_CONFIG_DATABASE_URI_FILE` |
| `PGADMIN_CONFIG_MAIL_PASSWORD`, `PGADMIN_CONFIG_LDAP_BIND_PASSWORD`, `PGADMIN_CONFIG_WEBSERVER_SHARED_SECRET` | environment variable |

The secrets with a file variable are mounted to `/run/secrets/<name>`, the entrypoint of the image reads them with `file_env`,
they are neither part of the quadlet unit nor of the environment of the container.
The entrypoint has no file variable for the other settings of pgAdmin, so the passwords of the mail server, of the LDAP bind user
and the shared secret of the web server authentication are passed with `type=env`, podman sets them when the container starts.
Like every setting the data of these secrets and of `PGADMIN_CONFIG_CONFIG_DATABASE_URI` are Python literals, e.g. `"'secret'"`,
the data of `PGADMIN_DEFAULT_PASSWORD` is the plain password.

```yaml
pgadmin_secrets:
  - name: 'pgadmin_default_password'
    data: "{{ vault_pgadmin_default_password }}"
    target: 'PGADMIN_DEFAULT_PASSWORD'
  - name: 'pgadmin_mail_password'
    data: "'{{ vault_pgadmin_mail_password }}'"
    target: 'PGADMIN_CONFIG_MAIL_PASSWORD'
```

The targets are the keys of `database_pgadmin__secret_files` and `database_pgadmin__secrets_env`.
Neither a target nor a file variable may be set in `pgadmin_environment`.
`PGADMIN_DEFAULT_PASSWORD` is only used by the first start with an empty data directory, later changes of the password are done in pgAdmin.

### Allowed variables

The role only allows the environment variables in `database_pgadmin__environment_allowed` and the secrets with the targets listed in Secrets,
it stops before any change if unknown variables or secrets are set.
This prevents unexpected behavior by accident, e.g. by a typo or a variable that has to be passed as secret.
The check uses the environment and the secrets of the container after merging `pgadmin_container`,
so variables set with `pgadmin_container.environment` are checked as well.

Allowed environment variables:

- the variables of `pkg/docker/entrypoint.sh` of the image (`PGADMIN_*`, `PGPASS_FILE`, `PUID`, `PGID`, `GUNICORN_*`) and `TZ`
- `PGADMIN_CONFIG_<SETTING>` for every setting of `web/config.py` of pgAdmin, except the settings passed as secrets
- the file variables of the secrets (`PGADMIN_DEFAULT_PASSWORD_FILE`, `PGADMIN_CONFIG_CONFIG_DATABASE_URI_FILE`),
  the role sets them from `pgadmin_secrets`, they must not be set in `pgadmin_environment`

The list is generated from `pkg/docker/entrypoint.sh` and `web/config.py` of [pgAdmin](https://github.com/pgadmin-org/pgadmin4) 9.19,
new versions of the image may add variables or settings.

### Container

Ports, volumes, additional hosts (`etc_hosts`) and dependencies (`requires`) are changed with `pgadmin_container`, it is merged over the default of the container.
The merge is not recursive, `pgadmin_container.volumes` replaces the data directory and `servers.json`,
`pgadmin_container.environment` replaces the environment including `pgadmin_environment`, use `pgadmin_environment` instead.
For a reverse proxy, e.g. Traefik, the labels are set with `pgadmin_labels`.

### Validation

The role checks before any change:

- `pgadmin_secrets` is a list of entries with `name`, `data` and `target` and unique names
- `PGADMIN_DEFAULT_EMAIL` is set and not empty, the secret `PGADMIN_DEFAULT_PASSWORD` exists
- `pgadmin_servers` is empty or a dictionary with the dictionary `Servers`
- neither a secret nor a file variable is set in `pgadmin_environment`
- only allowed environment variables and secrets are set in the container

If `pgadmin_container` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Restart and updates

pgAdmin is restarted if it was running and a secret, the quadlet unit or `servers.json` changed, e.g. after changing `pgadmin_environment`,
otherwise it is started and enabled.
Updates of the image are done by `container_update` with `pgadmin_autoupdate_enabled: true` and `pgadmin_autoupdate_schedule`,
without `pgadmin_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

The single variables of former versions are replaced by `pgadmin_environment`, `pgadmin_secrets` and `pgadmin_servers`:

- `pgadmin_user` is `PGADMIN_DEFAULT_EMAIL`
- `pgadmin_pass` is a secret with the target `PGADMIN_DEFAULT_PASSWORD`
- `pgadmin_server` is `pgadmin_servers`, the content is the same

The former role had no volume for `/var/lib/pgadmin`, users, servers, saved passwords and preferences were lost whenever the container was created again.
Now they are kept in `pgadmin_home/data`, the first start with the new role creates the admin and loads the servers again.
The password of the admin is mounted as file now instead of being passed as environment variable,
the fixed name of the secret `pgadmin_password` is gone, the name is free. The former secret is not removed by the role,
remove it with `podman secret rm pgadmin_password`.
`/etc/localtime` and `/etc/timezone` are not mounted anymore, the timezone is set with `TZ` and the timezone of the container.
`pgadmin_labels` has no default anymore, without it the container has no labels.
`podman___update_mode` is not evaluated anymore, the role neither stops the container nor pulls the image or recreates the container.
The tag `database_pgadmin` stays, the tag `database` is added.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-pgadmin-default` | Only the mandatory variables, `PGADMIN_DEFAULT_EMAIL` and the secret `PGADMIN_DEFAULT_PASSWORD` |
| `molecule-pgadmin` | IPv6, labels, a server in `pgadmin_servers`, `PGADMIN_CONFIG_LOGIN_BANNER`, `PGADMIN_CONFIG_MAIL_SERVER` and the secret `PGADMIN_CONFIG_MAIL_PASSWORD` in the environment |

`prepare` installs curl, creates the podman network, pulls the images and starts a PostgreSQL container.
`side_effect` runs the role with `pgadmin_container` not a dictionary, a secret without `target`, without `PGADMIN_DEFAULT_EMAIL`, without the secret `PGADMIN_DEFAULT_PASSWORD`,
`PGADMIN_DEFAULT_PASSWORD_FILE` and `PGADMIN_CONFIG_MAIL_PASSWORD` in the environment, `pgadmin_servers` without `Servers`,
an unknown setting `PGADMIN_CONFIG_FOO`, an unknown environment variable in `pgadmin_container.environment` and an unknown secret
and checks that it fails with the expected message and the quadlet unit and `servers.json` are unchanged (tasks marked `expect ERROR`),
then it waits until the first start of pgAdmin on `molecule-pgadmin` has finished and changes `PGADMIN_CONFIG_LOGIN_BANNER`, the quadlet unit changes and pgAdmin has to restart.
`verify` checks the quadlet unit with the volumes and the secrets, the service, the addresses and the environment of the container
with the file variable set by the role and without the password, the file of the secret, the settings in `config_distro.py` including the password of the mail server,
the data directory with the database of pgAdmin, logs in as admin with curl and checks the servers of the admin exported with `setup.py dump-servers`.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd database_pgadmin
MOLECULE_TART_IMAGE='debian' molecule test
```
