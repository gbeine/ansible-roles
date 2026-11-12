Grafana runs in the container image [grafana/grafana](https://hub.docker.com/r/grafana/grafana) (`latest` by default) as podman quadlet.
The container runs as user `grafana` (UID 472), the web interface and the API listen on port 3000.
Below `grafana_home` the role creates `data` (mounted to `/var/lib/grafana`) and `log` (`/var/log/grafana`).

### Configuration

Grafana is configured completely with environment variables in `grafana_environment`, the role does not generate `grafana.ini`.
`/etc/grafana` is not mounted, the container uses the `grafana.ini` of the image, all options in it are commented out.
Every option of `grafana.ini` is set with `GF_<SECTION>_<KEY>`: section and key in upper case, `.` and `-` replaced by `_`,
keys without section (e.g. `instance_name`) use the section `DEFAULT`.
Examples: `root_url` in `server` is `GF_SERVER_ROOT_URL`, `enabled` in `auth.anonymous` is `GF_AUTH_ANONYMOUS_ENABLED`,
`instance_name` is `GF_DEFAULT_INSTANCE_NAME`.
Everything not set uses the defaults of Grafana (`conf/defaults.ini` of the image), see the [documentation](https://grafana.com/docs/grafana/latest/setup-grafana/configure-grafana/#override-configuration-with-environment-variables).
`grafana_environment` is merged over the default of the role, it only sets `GF_SERVER_DOMAIN` to `grafana_hostname`.
Values are strings, e.g. `'true'`.

```yaml
grafana_environment:
  GF_DEFAULT_INSTANCE_NAME: 'grafana'
  GF_SERVER_DOMAIN: 'grafana.example.org'
  GF_SERVER_ROOT_URL: 'https://grafana.example.org/'
  GF_SECURITY_ADMIN_USER: 'admin'
  GF_DATABASE_TYPE: 'postgres'
  GF_DATABASE_HOST: 'postgresql:5432'
  GF_DATABASE_NAME: 'grafana'
  GF_DATABASE_USER: 'grafana'
  GF_AUTH_ANONYMOUS_ENABLED: 'true'
  GF_AUTH_ANONYMOUS_ORG_ROLE: 'Viewer'
  GF_ANALYTICS_REPORTING_ENABLED: 'false'
  GF_PLUGINS_PREINSTALL: 'grafana-clock-panel'
```

Grafana applies the environment variables to the sections it knows, sections that do not exist in `conf/defaults.ini` cannot be created.
Feature toggles are enabled with `GF_FEATURE_TOGGLES_ENABLE`.
Grafana requires no environment variables.

### Secrets

`grafana_secrets` is a list of podman secrets with `name`, `data` and `target`, the usual name of the variable, e.g. `GF_SECURITY_ADMIN_PASSWORD`.
The role creates the secret, mounts it to `/run/secrets/<name>` and sets `<target>__FILE=/run/secrets/<name>`,
the image (`run.sh`) reads the file at the start and passes the value to Grafana,
so passwords are neither part of the quadlet unit nor of the environment of the container.

The targets are the keys of `app_grafana__secret_files`, selected from `conf/defaults.ini` of Grafana v13.3.1:
the passwords (e.g. `GF_DATABASE_PASSWORD`, `GF_SMTP_PASSWORD`), the client secrets of the OAuth providers (e.g. `GF_AUTH_GENERIC_OAUTH_CLIENT_SECRET`),
the tokens and keys of credentials (e.g. `GF_SECURITY_SECRET_KEY`, `GF_RENDERING_RENDERER_TOKEN`).
They can only be set as secrets, neither a target nor its file variable may be set in `grafana_environment`.

```yaml
grafana_secrets:
  - name: 'grafana_admin_password'
    data: "{{ vault_grafana_admin_password }}"
    target: 'GF_SECURITY_ADMIN_PASSWORD'
  - name: 'grafana_database_password'
    data: "{{ vault_grafana_database_password }}"
    target: 'GF_DATABASE_PASSWORD'
```

`GF_SECURITY_ADMIN_USER` and `GF_SECURITY_ADMIN_PASSWORD` are only used by the first start of Grafana, while the database is empty.
Later the password of the admin is changed in the web interface or with `grafana cli admin reset-admin-password`.

### Provisioning

Data sources, dashboards and alerting are provisioned with files in `/etc/grafana/provisioning`,
mount a directory with `grafana_container.volumes`, the volumes of the default have to be repeated:

```yaml
grafana_container:
  volumes:
    - '/etc/timezone:/etc/timezone:ro'
    - '/etc/localtime:/etc/localtime:ro'
    - '/opt/grafana/data:/var/lib/grafana'
    - '/opt/grafana/log:/var/log/grafana'
    - '/opt/grafana/provisioning:/etc/grafana/provisioning:ro'
```

### Allowed variables

The role only allows the environment variables in `app_grafana__environment_allowed` and the secrets with a target in `app_grafana__secret_files`,
it stops before any change if unknown variables or secrets are set.
This prevents unexpected behavior by accident, e.g. by a typo or a variable that has to be passed as secret.
The check uses the environment and the secrets of the container after merging `grafana_container`,
so variables set with `grafana_container.environment` are checked as well.

The allowed environment variables are all options of `conf/defaults.ini` of Grafana v13.3.1 as `GF_<SECTION>_<KEY>`,
except `GF_PATHS_*`, they are set by the image, and except the secrets of `app_grafana__secret_files`.
The list contains the file variables of the secrets (`<target>__FILE`), the role sets them from `grafana_secrets`,
they must not be set in `grafana_environment`.
New versions of Grafana may add options, the list in `defaults/main.yml` is generated again from
`https://raw.githubusercontent.com/grafana/grafana/<version>/conf/defaults.ini`.
`GF_INSTALL_PLUGINS` is deprecated by Grafana and not allowed, use `GF_PLUGINS_PREINSTALL`.

### Container

Ports, volumes and additional hosts (`etc_hosts`) are changed with `grafana_container`, it is merged over the default of the container.
The merge is not recursive, `publish` and `volumes` replace the values of the default completely,
`grafana_container.environment` replaces the environment including `grafana_environment`, use `grafana_environment` instead.
For a reverse proxy, e.g. Traefik, the labels are set with `grafana_labels`.

### Validation

The role checks before any change that only allowed environment variables and secrets are set in the container, that the required environment variables are set and not empty
that `grafana_secrets` is a list of entries with `name`, `data` and `target` and unique names
and that neither a secret nor its file variable is set in `grafana_environment`.
If `grafana_container` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Restart and updates

Grafana is restarted if it was running and a secret or the quadlet unit changed, e.g. after changing `grafana_environment`, otherwise it is started and enabled.
Updates of the image are done by `container_update` with `grafana_autoupdate_enabled: true` and `grafana_autoupdate_schedule`,
without `grafana_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

`grafana_config` and the generated `grafana.ini` are replaced by `grafana_environment`,
every key `<key>` in the section `<section>` of `grafana_config` is `GF_<SECTION>_<KEY>`, see above.
`<grafana_home>/etc` is not used anymore and can be removed after the migration, move provisioning files to an own volume.

Former versions of the role generated `grafana.ini` from a template with single variables:

- `grafana_app_mode` is `GF_DEFAULT_APP_MODE`
- `grafana_protocol`, `grafana_http_addr`, `grafana_http_port`, `grafana_domain` and `grafana_static_root_path` are
  `GF_SERVER_PROTOCOL`, `GF_SERVER_HTTP_ADDR`, `GF_SERVER_HTTP_PORT`, `GF_SERVER_DOMAIN` and `GF_SERVER_STATIC_ROOT_PATH`
- `grafana_db_type`, `grafana_db_name` and `grafana_db_user` are `GF_DATABASE_TYPE`, `GF_DATABASE_NAME` and `GF_DATABASE_USER`,
  `grafana_db_host` and `grafana_db_port` are `GF_DATABASE_HOST` as `<host>:<port>`,
  `grafana_db_pass` is a secret with the target `GF_DATABASE_PASSWORD`
- `grafana_auth_anonymous`, `grafana_auth_anonymous_org_name` and `grafana_auth_anonymous_org_role` are
  `GF_AUTH_ANONYMOUS_ENABLED`, `GF_AUTH_ANONYMOUS_ORG_NAME` and `GF_AUTH_ANONYMOUS_ORG_ROLE`
- `grafana_auth_basic` is `GF_AUTH_BASIC_ENABLED`, Grafana enables it by default

The template set `enforce_domain = true`, logged to the console and to files and contained the obsolete section `session`,
these settings are gone, Grafana uses its defaults.
The image `grafana/grafana-oss` is not updated anymore since Grafana 12.4, the role uses `grafana/grafana`.
The environment in `grafana_container.environment` is replaced by `grafana_environment`.
Secrets need a `target`, the role sets `<target>__FILE`. References with `$__file{/run/secrets/<name>}` in `grafana_environment` are replaced by `target`,
the plain variables of the secrets (e.g. `GF_SECURITY_ADMIN_PASSWORD`) are not allowed in `grafana_environment` anymore.
The names of the secrets are free, the fixed list of allowed names is gone.
`podman___update_mode` is not evaluated anymore, the role neither stops the container nor pulls the image or recreates the container.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-grafana-default` | Only the mandatory variables, the admin `admin` with the password `admin` |
| `molecule-grafana` | IPv6, labels, `GF_DEFAULT_INSTANCE_NAME`, `GF_LOG_LEVEL` and the admin `molecule` with the password from a secret with the target `GF_SECURITY_ADMIN_PASSWORD` |

`prepare` creates the podman network and pulls the image.
`side_effect` runs the role with `grafana_container` not a dictionary, a secret without target,
the admin password and its file variable in the environment, an unknown environment variable in `grafana_environment` and in `grafana_container.environment` and an unknown secret
and checks that it fails with the expected message and the quadlet unit is unchanged (tasks marked `expect ERROR`),
then it enables the anonymous access with `GF_AUTH_ANONYMOUS_*` on `molecule-grafana`, the quadlet unit changes and Grafana has to restart.
`verify` checks the quadlet unit without a volume for `/etc/grafana`, the service, owner and mode of `data` and `log`, the addresses and the environment of the container with `GF_SECURITY_ADMIN_PASSWORD__FILE` and without the password,
waits until `/api/health` reports the database `ok` and requests `/api/org` without credentials and as admin.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd app_grafana
MOLECULE_TART_IMAGE='debian' molecule test
```
