Grafana runs in the container image [grafana/grafana](https://hub.docker.com/r/grafana/grafana) (`latest` by default) as podman quadlet.
The container runs as user `grafana` (UID 472), the web interface and the API listen on port 3000.
Below `grafana_home` the role creates `grafana.ini` (mounted to `/etc/grafana/grafana.ini`), `data` (`/var/lib/grafana`) and `log` (`/var/log/grafana`).

### Configuration

Grafana is configured with `grafana_config`, the role writes it to `<grafana_home>/grafana.ini`, everything not set uses the defaults
of Grafana (`conf/defaults.ini` of the image), see the [documentation](https://grafana.com/docs/grafana/latest/setup-grafana/configure-grafana/).
Keys with a value are options of the default section before the first section (`app_mode`, `instance_name`, `target`),
keys with a dictionary are sections, the name of a section is written as in `grafana.ini`, e.g. `auth.anonymous`.
`grafana_config` is merged recursively over the default of the role, it only sets `domain` in `server` to `grafana_hostname`.

```yaml
grafana_config:
  instance_name: 'grafana'
  server:
    domain: 'grafana.example.org'
    root_url: 'https://grafana.example.org/'
  security:
    admin_user: 'admin'
  database:
    type: 'postgres'
    host: 'postgresql:5432'
    name: 'grafana'
    user: 'grafana'
  auth.anonymous:
    enabled: true
    org_role: 'Viewer'
  analytics:
    reporting_enabled: false
  plugins:
    preinstall: [ 'grafana-clock-panel' ]
```

- a string or number writes `key = value`, a list writes the elements separated by commas, e.g. `preinstall`,
  options separated by spaces (e.g. `mode` in `log`) are set as string
- `true` and `false` write `true` and `false`
- `null` removes the option, e.g. an option of the default
- values with ` #` or ` ;`, leading quotes or spaces at the start or the end are written as `"""value"""`, Grafana would cut them otherwise
- `${NAME}` and `$__file{…}` in values are expanded by Grafana

### Options with keys

The keys of most sections are fixed, the sections without keys in `conf/defaults.ini` take free keys, e.g. the names of headers or labels:
`server.custom_response_headers`, `smtp.static_headers`, `recording_rules.custom_headers`, `unified_alerting.state_history.external_labels`,
`unified_alerting.notification_history.external_labels`, `navigation.app_sections`, `navigation.app_standalone_pages`,
`feature_toggles.openfeature.context`, `plugins.restricted_apis_blocklist`, `metrics.environment_info`, `external_image_storage.local`,
`grafana-apiserver` and `feature_toggles` (the names of the feature toggles).
Free keys start with a letter or digit, followed by letters, digits, `.`, `_` and `-`.

The settings of a plugin are the section `plugin.<id>` with free keys, the ids are declared in `grafana_keys`:

| Family | Generated sections |
|---|---|
| `plugin` | `plugin.<key>` |

```yaml
grafana_keys:
  plugin: [ 'grafana-image-renderer' ]
grafana_config:
  plugin.grafana-image-renderer:
    rendering_ignore_https_errors: true
  server.custom_response_headers:
    X-Frame-Options: 'SAMEORIGIN'
```

### Secrets

`grafana_secrets` is a list of podman secrets with `name`, `data` and `target`, the target is the option of `grafana.ini` as `<section>.<key>`,
e.g. `security.admin_password`. The role creates the secret, mounts it to `/run/secrets/<name>` and writes `<key> = $__file{/run/secrets/<name>}`
to the section, Grafana reads the file at the start. Passwords are neither part of `grafana.ini`, nor of the quadlet unit or the environment of the container.

The targets are the keys of `app_grafana__secrets_allowed`, selected from `conf/defaults.ini` of Grafana v13.3.1:
the passwords (e.g. `database.password`, `smtp.password`), the client secrets of the OAuth providers (e.g. `auth.generic_oauth.client_secret`),
the tokens and keys of credentials (e.g. `security.secret_key`, `rendering.renderer_token`).
They can only be set as secrets, a target must not be set in `grafana_config`, every target is set once.

```yaml
grafana_secrets:
  - name: 'grafana_admin_password'
    data: "{{ vault_grafana_admin_password }}"
    target: 'security.admin_password'
  - name: 'grafana_database_password'
    data: "{{ vault_grafana_database_password }}"
    target: 'database.password'
```

`admin_user` and `admin_password` in `security` are only used by the first start of Grafana, while the database is empty.
Later the password of the admin is changed in the web interface or with `grafana cli admin reset-admin-password`.

### Provisioning

Data sources, dashboards and alerting are provisioned with files in `/etc/grafana/provisioning`,
mount a directory with `grafana_container.volumes`, the volumes of the default have to be repeated:

```yaml
grafana_container:
  volumes:
    - '/opt/grafana/grafana.ini:/etc/grafana/grafana.ini:ro'
    - '/opt/grafana/data:/var/lib/grafana'
    - '/opt/grafana/log:/var/log/grafana'
    - '/opt/grafana/provisioning:/etc/grafana/provisioning:ro'
```

### Allowed variables

The role only allows the sections and options of `app_grafana__config_allowed`, the sections with free keys, the sections of `grafana_keys`,
the secrets with a target in `app_grafana__secrets_allowed` and the environment variables in `app_grafana__environment_allowed` (`TZ`),
it stops before any change if unknown sections, options, variables or secrets are set.
This prevents unexpected behavior by accident, e.g. by a typo or an option that has to be passed as secret.
`grafana_environment` has no default, without it the quadlet unit has no environment and nothing is checked.
The check of the environment uses the environment of the container after merging `grafana_container`.

The allowed sections and options are generated from `conf/defaults.ini` of Grafana v13.3.1 without the section `paths`, it is set by the image,
and without the secrets. New versions of Grafana may add options, the lists in `defaults/main.yml` are generated again from
`https://raw.githubusercontent.com/grafana/grafana/<version>/conf/defaults.ini`.
The options of Grafana are not set with `GF_<SECTION>_<KEY>` in the environment, the role reports such variables with their option.

### Container

Ports, volumes, additional hosts (`etc_hosts`) and dependencies are changed with `grafana_container`, it is merged over the default of the container.
The merge is not recursive, `publish` and `volumes` replace the values of the default completely,
`grafana_container.environment` replaces the environment including `grafana_environment`.
For a reverse proxy, e.g. Traefik, the labels are set with `grafana_labels`.

The dependencies of the quadlet unit are lists of units in `grafana_container`: `requires`, `wants`, `after`, `part_of` and `binds_to`
are written as `Requires=`, `Wants=`, `After=`, `PartOf=` and `BindsTo=` to `[Unit]`.

```yaml
grafana_container:
  requires: [ 'postgresql.service' ]
  after: [ 'postgresql.service' ]
```

### Validation

The role checks before any change:

- `grafana_keys` is a dictionary of the family `plugin` with lists of valid and unique keys
- `grafana_secrets` is a list of entries with `name`, `data` and `target` and unique names, every target is a known secret and set once, no secret contains a line break
- `grafana_config` contains known sections and options or valid free keys, strings, numbers, booleans, `null` or lists of them without line breaks and `"""`,
  no secret and not the section `paths`
- `grafana_environment`, if set, contains no option of Grafana (`GF_*`) and no line breaks, only allowed environment variables are set in the container

If `grafana_container` or `grafana_config` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter. Grafana checks the values of the options at the start.

### Restart and updates

Grafana is restarted if it was running and `grafana.ini`, a secret or the quadlet unit changed, otherwise it is started and enabled.
If the start fails, the role shows the journal of the service.
Afterwards the role waits until `/api/health` answers and shows the journal otherwise.
Updates of the image are done by `container_update` with `grafana_autoupdate_enabled: true` and `grafana_autoupdate_schedule`,
without `grafana_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

The former version of the role configured Grafana with `GF_<SECTION>_<KEY>` in `grafana_environment`, it is `grafana_config` now:
the variable `GF_<SECTION>_<KEY>` is the key `<key>` in the section `<section>` (lower case),
`GF_DEFAULT_<KEY>` is a key without section, e.g. `GF_DEFAULT_INSTANCE_NAME` is `instance_name`,
`GF_SERVER_ROOT_URL` is `root_url` in `server`, `GF_AUTH_ANONYMOUS_ENABLED` is `enabled` in `auth.anonymous`.
Values are no strings anymore, e.g. `true` instead of `'true'`.
The role rejects `GF_*` in `grafana_environment` and names the option of every variable.

| Former variable | Replacement |
|---|---|
| `grafana_environment` with `GF_<SECTION>_<KEY>` | `grafana_config` |
| target `GF_<SECTION>_<KEY>` of `grafana_secrets` | target `<section>.<key>`, e.g. `GF_SECURITY_ADMIN_PASSWORD` is `security.admin_password`, `GF_DATABASE_PASSWORD` is `database.password` |
| none | `grafana_keys` for the sections `plugin.<id>` |

Changed behavior:

- the role generates `<grafana_home>/grafana.ini` again and mounts it read-only, it contains the references to the secrets, not the secrets
- the secrets are read by Grafana with `$__file{}`, the image does not set `<target>__FILE` anymore
- sections with free keys and the sections of plugins can be set, they were not possible with the environment
- `/etc/localtime` and `/etc/timezone` are no longer mounted, the time zone is set with `grafana_timezone`, the quadlet unit changes once and Grafana restarts
- Grafana is restarted if `grafana.ini` changed, the role waits until Grafana answers and shows the journal if it fails

Older versions of the role generated `grafana.ini` from a template with single variables:

- `grafana_app_mode` is `app_mode`
- `grafana_protocol`, `grafana_http_addr`, `grafana_http_port`, `grafana_domain` and `grafana_static_root_path` are
  `protocol`, `http_addr`, `http_port`, `domain` and `static_root_path` in `server`
- `grafana_db_type`, `grafana_db_name` and `grafana_db_user` are `type`, `name` and `user` in `database`,
  `grafana_db_host` and `grafana_db_port` are `host` as `<host>:<port>`, `grafana_db_pass` is a secret with the target `database.password`
- `grafana_auth_anonymous`, `grafana_auth_anonymous_org_name` and `grafana_auth_anonymous_org_role` are
  `enabled`, `org_name` and `org_role` in `auth.anonymous`
- `grafana_auth_basic` is `enabled` in `auth.basic`, Grafana enables it by default
- `<grafana_home>/etc` is not used, move provisioning files to an own volume
- the image `grafana/grafana-oss` is not updated anymore since Grafana 12.4, the role uses `grafana/grafana`
- `podman___update_mode` is not evaluated anymore, updates are done by `container_update`

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-grafana-default` | Only the mandatory variables, the admin `admin` with the password `admin` |
| `molecule-grafana` | IPv6, labels, `instance_name`, `level` in `log`, a custom response header, the section of a plugin with `grafana_keys` and the admin `molecule` with the password from a secret with the target `security.admin_password` |

`prepare` creates the podman network and pulls the image.
`side_effect` runs the role with `grafana_container` and `grafana_config` not a dictionary, a secret without target, an unknown section, option and plugin section,
the admin password, a dictionary and a line break in `grafana_config`, options of Grafana in `grafana_environment`, an unknown environment variable in `grafana_container`
and an unknown secret and checks that it fails with the expected message and the quadlet unit and `grafana.ini` are unchanged (tasks marked `expect ERROR`),
then it enables the anonymous access in `auth.anonymous` on `molecule-grafana`, `grafana.ini` changes and Grafana has to restart.
`verify` checks the quadlet unit without mounts of the time zone, options and passwords, `grafana.ini` with the reference to the secret, the service,
owner and mode of `data` and `log`, the addresses and the environment of the container without the password,
waits until `/api/health` reports the database `ok`, requests `/api/org` without credentials and as admin with the password from the secret
and checks the custom response header.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd app_grafana
MOLECULE_TART_IMAGE='debian' molecule test
```
