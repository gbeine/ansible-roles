pgAdmin runs in the container image [dpage/pgadmin4](https://hub.docker.com/r/dpage/pgadmin4) (`latest` by default, `pgadmin_version` sets the tag) as podman quadlet.
The image runs pgAdmin with gunicorn as the user 5050, the web interface listens on port 80.
Below `pgadmin_home` the role creates `data`, owned by the user 5050 and mounted to `/var/lib/pgadmin`,
it holds the database of pgAdmin with the users, the servers and the preferences, the sessions and the storage of the users.
The PostgreSQL servers are not part of the role.

### Configuration

The settings of `config.py` of pgAdmin are set with `pgadmin_config`, a dictionary of the settings, see the
[configuration of pgAdmin](https://www.pgadmin.org/docs/pgadmin4/latest/config_py.html), there is no default.
The role writes them to `pgadmin_home/config_system.py`, mounted read only to `/etc/pgadmin/config_system.py`,
pgAdmin imports this file last, it overrides `config_distro.py` and `config_local.py` of the image.
Every setting is written as JSON and read with `json.loads`, strings, numbers, `true`, `false`, lists and dictionaries are possible, `null` removes a setting.
pgAdmin checks the types of some settings itself, e.g. `SERVER_MODE` is a boolean and `MAIL_PORT` an integer.

```yaml
pgadmin_config:
  ENHANCED_COOKIE_PROTECTION: true
  MAIL_SERVER: 'smtp.example.org'
  MAIL_PORT: 587
  MAIL_USE_TLS: true
  MAIL_USERNAME: 'pgadmin@example.org'
  SECURITY_EMAIL_SENDER: 'pgadmin@example.org'
```

`pgadmin_environment` takes the variables of the image that are no settings of pgAdmin, e.g. `PGADMIN_LISTEN_PORT`, `PGADMIN_DISABLE_POSTFIX`
or `GUNICORN_THREADS`, see the [documentation of the container](https://www.pgadmin.org/docs/pgadmin4/latest/container_deployment.html), there is no default.
`PGADMIN_DEFAULT_EMAIL` is required, it is the email address of the admin created by the initialization (see Initialization).

`pgadmin_servers` is the content of `servers.json`, a dictionary with `Servers`, see the [documentation of the import](https://www.pgadmin.org/docs/pgadmin4/latest/import_export_servers.html).
The role writes it to `pgadmin_home/servers.json`, the initialization loads the servers for `PGADMIN_DEFAULT_EMAIL`, changes later have no effect.

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

`pgadmin_secrets` is a list of podman secrets with `name`, `data` and `target`, the secret `PGADMIN_DEFAULT_PASSWORD` is required.

- `PGADMIN_DEFAULT_PASSWORD`, the password of the admin, is only mounted in the container of the initialization,
  the entrypoint reads it from the file of `PGADMIN_DEFAULT_PASSWORD_FILE`.
- `MAIL_PASSWORD`, `LDAP_BIND_PASSWORD`, `WEBSERVER_SHARED_SECRET` and `CONFIG_DATABASE_URI` are settings of pgAdmin,
  they are mounted to `/run/secrets/<name>` for the user of the image and `config_system.py` reads them with `open('/run/secrets/<name>')`.
  The configuration is Python and reads the files itself, the passwords are neither part of `config_system.py`, the quadlet unit nor of the environment.

```yaml
pgadmin_secrets:
  - name: 'pgadmin_default_password'
    data: "{{ vault_pgadmin_default_password }}"
    target: 'PGADMIN_DEFAULT_PASSWORD'
  - name: 'pgadmin_mail_password'
    data: "{{ vault_pgadmin_mail_password }}"
    target: 'MAIL_PASSWORD'
```

Changing `PGADMIN_DEFAULT_PASSWORD` later does not change the password of the admin.

### Initialization

The image creates the database of pgAdmin with the admin and loads `servers.json` only if `pgadmin_home/data/pgadmin4.db` is missing.
The role runs the initialization once in the container `pgadmin-init` without network, with `PGADMIN_DEFAULT_EMAIL`, the secrets and `servers.json`,
waits until gunicorn listens (`Listening at:`) and removes the container, also if the initialization failed.
A failed initialization names the data directory whose content has to be removed before the next run.
With `SERVER_MODE: false` or the secret `CONFIG_DATABASE_URI` the role passes them to the initialization as `PGADMIN_CONFIG_SERVER_MODE`
and `PGADMIN_CONFIG_CONFIG_DATABASE_URI_FILE`, the entrypoint reads them from the environment.
The quadlet unit contains neither the email, the password of the admin nor `servers.json`.

### Allowed variables

The role only allows the settings of `database_pgadmin__config_allowed` in `pgadmin_config`, generated from `web/config.py` of [pgAdmin](https://github.com/pgadmin-org/pgadmin4) 9.19
without the settings carrying secrets, the variables of `database_pgadmin__environment_allowed` in the environment
and the secrets with a target in `database_pgadmin__secrets_allowed`, it stops before any change if unknown settings, variables or secrets are set.
This prevents unexpected behavior by accident, e.g. by a typo or a password in plain text.
The check of the environment uses `pgadmin_environment` and the environment of the container after merging `pgadmin_container`.

The allowed variables are the variables of `pkg/docker/entrypoint.sh` of pgAdmin 9.19 without `PGADMIN_CONFIG_*`, which are set with `pgadmin_config`,
and without the variables of the initialization managed by the role (`PGADMIN_SERVER_JSON_FILE`, `PGADMIN_PREFERENCES_JSON_FILE`,
`PGADMIN_REPLACE_SERVERS_ON_STARTUP`, `PGPASS_FILE`, `PGADMIN_CUSTOM_CONFIG_DISTRO_FILE`), and `TZ`.
New versions of pgAdmin may add settings, the lists are generated again.

### Container

Ports, volumes, additional hosts (`etc_hosts`) and dependencies are changed with `pgadmin_container`, it is merged over the default of the container.
The merge is not recursive, `pgadmin_container.volumes` replaces the data directory and `config_system.py`,
`pgadmin_container.environment` replaces the environment including `pgadmin_environment`, use `pgadmin_environment` instead.
The time zone of the container is set by podman with `pgadmin_timezone`.
For a reverse proxy, e.g. Traefik, the labels are set with `pgadmin_labels`, the web interface listens on port 80.

The dependencies of the quadlet unit are set with `requires`, `wants`, `after`, `part_of`, `binds_to` and `requires_mounts_for`
in `pgadmin_container`, the role writes them to `[Unit]` as `Requires=`, `Wants=`, `After=`, `PartOf=`, `BindsTo=` and `RequiresMountsFor=`:

```yaml
pgadmin_container:
  wants: [ 'network-online.target' ]
  after: [ 'network-online.target' ]
  requires_mounts_for: [ '/opt/pgadmin' ]
```

### Validation

The role checks before any change:

- `pgadmin_secrets` is a list of entries with `name`, `data` and `target` and unique names, the secret `PGADMIN_DEFAULT_PASSWORD` exists
- `PGADMIN_DEFAULT_EMAIL` is set, neither a secret nor its file variable is set in `pgadmin_environment`
- `pgadmin_servers` is a dictionary with `Servers`
- `pgadmin_config` is a dictionary of known settings without secrets, the boolean and integer settings checked by pgAdmin have the right type,
  the values are strings without line breaks, numbers, booleans, lists, dictionaries or `null`
- only allowed environment variables without line breaks and secrets are set

If `pgadmin_container` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Check mode

The role runs with `--check` also on a host where it never ran before and compares `config_system.py`, `servers.json`, the secrets and the quadlet unit.
The initialization and the start do not run in check mode.

### Restart and updates

pgAdmin is restarted if it was running and `config_system.py`, a secret or the quadlet unit changed, otherwise it is started and enabled.
A failed start reports the journal of the service.
Updates of the image are done by `container_update` with `pgadmin_autoupdate_enabled: true` and `pgadmin_autoupdate_schedule`,
without `pgadmin_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

The settings of pgAdmin are set in `config_system.py` with `pgadmin_config` instead of `PGADMIN_CONFIG_<SETTING>` in `pgadmin_environment`,
the values are YAML instead of Python literals, e.g.:

- `PGADMIN_CONFIG_MAIL_SERVER: "'smtp.example.org'"` is `MAIL_SERVER: 'smtp.example.org'`
- `PGADMIN_CONFIG_MAIL_PORT: '587'` is `MAIL_PORT: 587`
- `PGADMIN_CONFIG_ENHANCED_COOKIE_PROTECTION: 'True'` is `ENHANCED_COOKIE_PROTECTION: true`

The targets of the secrets of the settings are the settings: `PGADMIN_CONFIG_MAIL_PASSWORD` is `MAIL_PASSWORD`, `PGADMIN_CONFIG_LDAP_BIND_PASSWORD` is `LDAP_BIND_PASSWORD`,
`PGADMIN_CONFIG_WEBSERVER_SHARED_SECRET` is `WEBSERVER_SHARED_SECRET`, `PGADMIN_CONFIG_CONFIG_DATABASE_URI` is `CONFIG_DATABASE_URI`,
the passwords are read from files by `config_system.py` and are no longer passed in the environment.
The admin is created and `servers.json` is loaded in the container `pgadmin-init`, the quadlet unit no longer contains them,
`PGADMIN_REPLACE_SERVERS_ON_STARTUP` is not supported anymore.
`TZ` is not set by default anymore, the time zone is set by podman with `pgadmin_timezone`.

Changes of former versions:

The single variables of former versions are replaced by `pgadmin_environment`, `pgadmin_secrets` and `pgadmin_servers`:

- `pgadmin_user` is `PGADMIN_DEFAULT_EMAIL`
- `pgadmin_pass` is a secret with the target `PGADMIN_DEFAULT_PASSWORD`
- `pgadmin_server` is `pgadmin_servers`, the content is the same

The former role had no volume for `/var/lib/pgadmin`, users, servers, saved passwords and preferences were lost whenever the container was created again.
Now they are kept in `pgadmin_home/data`, the first start with the new role creates the admin and loads the servers again.
The password of the admin is mounted as file now instead of being passed as environment variable,
the fixed name of the secret `pgadmin_password` is gone, the name is free. The former secret is not removed by the role,
remove it with `podman secret rm pgadmin_password`.
`/etc/localtime` and `/etc/timezone` are not mounted anymore, the timezone is set with the timezone of the container.
`pgadmin_labels` has no default anymore, without it the container has no labels.
`podman___update_mode` is not evaluated anymore, the role neither stops the container nor pulls the image or recreates the container.
The tag `database_pgadmin` stays, the tag `database` is added.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-pgadmin-default` | Only the mandatory variables, `PGADMIN_DEFAULT_EMAIL` and the secret `PGADMIN_DEFAULT_PASSWORD` |
| `molecule-pgadmin` | IPv6, labels, dependencies, `GUNICORN_THREADS`, a server in `pgadmin_servers`, `LOGIN_BANNER`, `MAIL_SERVER` and `MAIL_PORT` in `pgadmin_config` and the secret `MAIL_PASSWORD` |

`prepare` installs curl, creates the podman network, pulls the images and starts a PostgreSQL container, `check` runs `converge` with `--check` on the fresh VMs.
`side_effect` runs the role with invalid variables and checks that it fails with the expected message and the quadlet unit, `config_system.py` and `servers.json`
are unchanged (tasks marked `expect ERROR`): `pgadmin_container` and `pgadmin_config` not a dictionary, a secret without `target`, without `PGADMIN_DEFAULT_EMAIL`,
without the secret `PGADMIN_DEFAULT_PASSWORD`, `PGADMIN_DEFAULT_PASSWORD_FILE` and `PGADMIN_CONFIG_LOGIN_BANNER` in the environment, `MAIL_PASSWORD` in `pgadmin_config`,
`SERVER_MODE` as string, a line break in a setting and in the environment, `pgadmin_servers` without `Servers`, an unknown setting,
an unknown environment variable in `pgadmin_container.environment` and an unknown secret.
Then it waits for the login page and runs the role with `side_effect.role_vars` of the test case: `molecule-pgadmin` changes `LOGIN_BANNER`,
only `config_system.py` changes and pgAdmin has to restart, `molecule-pgadmin-default` runs again without a change and must not restart,
the initialization must not run again.
`verify` checks the quadlet unit with the volumes, the mounted secret and the dependencies and without email, password, `TZ` and `servers.json`,
the service, the addresses and the environment of the container, `config_system.py` and the settings pgAdmin reads from it in the container
including the password of the mail server, that `pgadmin-init` was removed, the data directory with the database of pgAdmin,
logs in as admin with curl and checks the servers of the admin exported with `setup.py dump-servers`.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd database_pgadmin
MOLECULE_TART_IMAGE='debian' molecule test
```
