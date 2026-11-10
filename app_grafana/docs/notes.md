Grafana runs in the container image [grafana/grafana](https://hub.docker.com/r/grafana/grafana) (`latest` by default) as podman quadlet.
The container runs as user `grafana` (UID 472), the web interface and the API listen on port 3000.
Below `grafana_home` the role creates `etc` (mounted to `/etc/grafana`, contains `grafana.ini`), `data` (`/var/lib/grafana`) and `log` (`/var/log/grafana`).

### Configuration

`grafana.ini` is generated from `grafana_config` with the filter `community.general.to_ini`,
the collection `community.general` 8.2.0 or newer has to be installed on the controller.
`grafana_config` contains the sections of `grafana.ini` with their keys, keys without section (e.g. `instance_name`) are set in the section `DEFAULT`.
Everything not set uses the defaults of Grafana (`conf/defaults.ini` of the image), see the [documentation](https://grafana.com/docs/grafana/latest/setup-grafana/configure-grafana/).
The default of the role only sets `domain` in the section `server` to `grafana_hostname`.
Every section of `grafana_config` replaces the section of the default completely, so `server` has to contain `domain`.
Boolean values are written as `True` and `False`, Grafana accepts both.

```yaml
grafana_config:
  DEFAULT:
    instance_name: 'grafana'
  server:
    domain: 'grafana.example.org'
    root_url: 'https://grafana.example.org/'
  security:
    admin_user: 'admin'
    admin_password: '$__file{/run/secrets/grafana_admin_password}'
  database:
    type: 'postgres'
    host: 'postgresql:5432'
    name: 'grafana'
    user: 'grafana'
    password: '$__file{/run/secrets/grafana_database_password}'
  auth.anonymous:
    enabled: true
    org_role: 'Viewer'
  analytics:
    reporting_enabled: false
```

### Secrets

`grafana_secrets` is a list of podman secrets with `name` and `data`, each one is mounted to `/run/secrets/<name>` in the container.
The configuration reads them with `$__file{/run/secrets/<name>}`, so passwords are not part of `grafana.ini`:

```yaml
grafana_secrets:
  - name: 'grafana_admin_password'
    data: "{{ vault_grafana_admin_password }}"
  - name: 'grafana_database_password'
    data: "{{ vault_grafana_database_password }}"
```

`admin_user` and `admin_password` are only used by the first start of Grafana, while the database is empty.
Later the password of the admin is changed in the web interface or with `grafana cli admin reset-admin-password`.

### Provisioning

`<grafana_home>/etc` is mounted to `/etc/grafana`, data sources, dashboards and alerting are provisioned with files in `<grafana_home>/etc/provisioning`.

### Container

Ports, volumes, additional hosts (`etc_hosts`) and the environment are changed with `grafana_container`, it is merged over the default of the container.
The merge is not recursive, `publish`, `volumes` and `environment` replace the values of the default completely.
For a reverse proxy, e.g. Traefik, the labels are set with `grafana_labels`.

### Validation

The role checks before any change that every section of `grafana_config` is a dictionary
and that the entries of `grafana_secrets` have a `name` of letters, digits, `.`, `_` or `-` and `data`.
If `grafana_config` or `grafana_container` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Restart and updates

Grafana is restarted if it was running and the configuration, a secret or the quadlet unit changed, otherwise it is started and enabled.
Updates of the image are done by `container_update` with `grafana_autoupdate_enabled: true` and `grafana_autoupdate_schedule`,
without `grafana_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

Former versions of the role generated `grafana.ini` from a template with single variables, they are replaced by keys in `grafana_config`:

- `grafana_app_mode` is `DEFAULT.app_mode`
- `grafana_protocol`, `grafana_http_addr`, `grafana_http_port`, `grafana_domain` and `grafana_static_root_path` are `protocol`, `http_addr`, `http_port`, `domain` and `static_root_path` in `server`
- `grafana_db_type`, `grafana_db_name` and `grafana_db_user` are `type`, `name` and `user` in `database`,
  `grafana_db_host` and `grafana_db_port` are `database.host` as `<host>:<port>`, `grafana_db_pass` is `database.password`, preferably from a secret
- `grafana_auth_anonymous`, `grafana_auth_anonymous_org_name` and `grafana_auth_anonymous_org_role` are `enabled`, `org_name` and `org_role` in `auth.anonymous`
- `grafana_auth_basic` is `auth.basic.enabled`, Grafana enables it by default

The template set `enforce_domain = true`, logged to the console and to files and contained the obsolete section `session`,
these settings are gone, Grafana uses its defaults.
The image `grafana/grafana-oss` is not updated anymore since Grafana 12.4, the role uses `grafana/grafana`.
`podman___update_mode` is not evaluated anymore, the role neither stops the container nor pulls the image or recreates the container.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-grafana-default` | Only the mandatory variables, the admin `admin` with the password `admin` |
| `molecule-grafana` | IPv6, labels, `instance_name` in `DEFAULT` and the admin `molecule` with the password from a secret |

`prepare` creates the podman network and pulls the image.
`side_effect` runs the role with `grafana_container` not a dictionary, a section of `grafana_config` not a dictionary and an invalid name of a secret
and checks that it fails with the expected message and the quadlet unit and the configuration are unchanged (tasks marked `expect ERROR`),
then it enables the anonymous access on `molecule-grafana`, the configuration changes and Grafana has to restart.
`verify` checks the quadlet unit, the service, owner, mode and content of `grafana.ini` and the addresses of the container,
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
