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
  GF_SECURITY_ADMIN_PASSWORD: '$__file{/run/secrets/grafana_admin_password}'
  GF_DATABASE_TYPE: 'postgres'
  GF_DATABASE_HOST: 'postgresql:5432'
  GF_DATABASE_NAME: 'grafana'
  GF_DATABASE_USER: 'grafana'
  GF_DATABASE_PASSWORD: '$__file{/run/secrets/grafana_database_password}'
  GF_AUTH_ANONYMOUS_ENABLED: 'true'
  GF_AUTH_ANONYMOUS_ORG_ROLE: 'Viewer'
  GF_ANALYTICS_REPORTING_ENABLED: 'false'
  GF_PLUGINS_PREINSTALL: 'grafana-clock-panel'
```

Grafana applies the environment variables to the sections it knows, sections that do not exist in `conf/defaults.ini` cannot be created.
Feature toggles are enabled with `GF_FEATURE_TOGGLES_ENABLE`.
Grafana requires no environment variables.

### Secrets

`grafana_secrets` is a list of podman secrets with `name` and `data`, each one is mounted to `/run/secrets/<name>` in the container.
The environment references them with `$__file{/run/secrets/<name>}`, Grafana reads the file at the start,
so passwords are neither part of the quadlet unit nor of the environment of the container.
Never set a password in plain text in `grafana_environment`.

```yaml
grafana_secrets:
  - name: 'grafana_admin_password'
    data: "{{ vault_grafana_admin_password }}"
  - name: 'grafana_database_password'
    data: "{{ vault_grafana_database_password }}"
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

The role only allows the environment variables in `app_grafana__environment_allowed` and the secrets in `app_grafana__secrets_allowed`,
it stops before any change if unknown variables or secrets are set.
This prevents unexpected behavior by accident, e.g. by a typo or a variable that has to be passed as secret.
The check uses the environment and the secrets of the container after merging `grafana_container`,
so variables set with `grafana_container.environment` and secrets set with `grafana_container.secrets` are checked as well.

The allowed environment variables are all options of `conf/defaults.ini` of Grafana v13.3.1 as `GF_<SECTION>_<KEY>`,
except `GF_PATHS_*`, they are set by the image.
New versions of Grafana may add options, the list in `defaults/main.yml` is generated again from
`https://raw.githubusercontent.com/grafana/grafana/<version>/conf/defaults.ini`.
`GF_INSTALL_PLUGINS` is deprecated by Grafana and not allowed, use `GF_PLUGINS_PREINSTALL`.

Allowed secrets, the names of the secrets, the files below `/run/secrets`, the name has to match exactly:

- `grafana_admin_password`
- `grafana_secret_key`
- `grafana_database_password`
- `grafana_smtp_password`
- `grafana_oauth_client_secret`

### Container

Ports, volumes and additional hosts (`etc_hosts`) are changed with `grafana_container`, it is merged over the default of the container.
The merge is not recursive, `publish` and `volumes` replace the values of the default completely,
`grafana_container.environment` replaces the environment including `grafana_environment`, use `grafana_environment` instead.
For a reverse proxy, e.g. Traefik, the labels are set with `grafana_labels`.

### Validation

The role checks before any change that only allowed environment variables and secrets are set in the container, that the required environment variables are set and not empty
and that the entries of `grafana_secrets` have `name` and `data`, the names are restricted by the allowed secrets.
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
  `grafana_db_pass` is `GF_DATABASE_PASSWORD` with `$__file{}` from a secret
- `grafana_auth_anonymous`, `grafana_auth_anonymous_org_name` and `grafana_auth_anonymous_org_role` are
  `GF_AUTH_ANONYMOUS_ENABLED`, `GF_AUTH_ANONYMOUS_ORG_NAME` and `GF_AUTH_ANONYMOUS_ORG_ROLE`
- `grafana_auth_basic` is `GF_AUTH_BASIC_ENABLED`, Grafana enables it by default

The template set `enforce_domain = true`, logged to the console and to files and contained the obsolete section `session`,
these settings are gone, Grafana uses its defaults.
The image `grafana/grafana-oss` is not updated anymore since Grafana 12.4, the role uses `grafana/grafana`.
The environment in `grafana_container.environment` is replaced by `grafana_environment`.
`podman___update_mode` is not evaluated anymore, the role neither stops the container nor pulls the image or recreates the container.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-grafana-default` | Only the mandatory variables, the admin `admin` with the password `admin` |
| `molecule-grafana` | IPv6, labels, `GF_DEFAULT_INSTANCE_NAME`, `GF_LOG_LEVEL` and the admin `molecule` with the password from a secret with `$__file{}` in `grafana_environment` |

`prepare` creates the podman network and pulls the image.
`side_effect` runs the role with `grafana_container` not a dictionary, an invalid name of a secret, an unknown environment variable in `grafana_environment` and in `grafana_container.environment` and an unknown secret
and checks that it fails with the expected message and the quadlet unit is unchanged (tasks marked `expect ERROR`),
then it enables the anonymous access with `GF_AUTH_ANONYMOUS_*` on `molecule-grafana`, the quadlet unit changes and Grafana has to restart.
`verify` checks the quadlet unit without a volume for `/etc/grafana`, the service, owner and mode of `data` and `log`, the addresses and the environment of the container,
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
