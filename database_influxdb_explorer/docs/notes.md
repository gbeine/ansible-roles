InfluxDB 3 Explorer runs in the container image [influxdata/influxdb3-ui](https://hub.docker.com/r/influxdata/influxdb3-ui) (`latest` by default, `influxdb_explorer_version` sets the tag) as podman quadlet.
The image runs nginx and Explorer as the user 1500, the web interface listens on port 8080 (HTTP) and 8443 (HTTPS with certificates).
Below `influxdb_explorer_home` the role creates `db`, owned by the user 1500 and mounted to `/db`, it holds the SQLite database of Explorer
with the connections and the settings created in the web interface.
InfluxDB 3 is not part of the role.

### Configuration

The default connection of Explorer is set with `influxdb_explorer_config`, a dictionary with the keys of `config.json`,
merged over the default of the role, which is empty. The values are strings, `null` or `false` removes a key.
The token of the connection is a secret with the target `DEFAULT_API_TOKEN` (see Secrets).

| Key | Description |
|---|---|
| `DEFAULT_INFLUX_SERVER` | URL of InfluxDB 3, e.g. `http://influxdb3:8181` |
| `DEFAULT_INFLUX_DATABASE` | Database selected by default |
| `DEFAULT_SERVER_NAME` | Name of the connection shown by Explorer |

```yaml
influxdb_explorer_config:
  DEFAULT_INFLUX_SERVER: 'http://influxdb3:8181'
  DEFAULT_INFLUX_DATABASE: 'telegraf'
  DEFAULT_SERVER_NAME: 'InfluxDB 3'
```

The role writes `config.json` from the configuration and the token as podman secret `influxdb-explorer-config`
and mounts it to `/app-root/config/config.json` for the user of the image, so the token is neither stored on the host nor part of the quadlet unit.
Without configuration and token there is no `config.json`, connections are created in the web interface then.

The environment of the image is set with `influxdb_explorer_environment`, merged over the default of the role, which sets `TZ` to `influxdb_explorer_timezone`,
e.g. `LOG_LEVEL`, `DATABASE_URL`, `SSL_CERT_PATH`, `SSL_KEY_PATH` or `NODE_EXTRA_CA_CERTS`, see the [documentation of Explorer](https://docs.influxdata.com/influxdb3/explorer/install/docker/).

### Secrets

`influxdb_explorer_secrets` is a list of secrets with `name`, `data` and `target`. The secret `SESSION_SECRET_KEY` is required.

| Target | Passed as |
|---|---|
| `SESSION_SECRET_KEY`, the key of the sessions | podman secret, environment variable `SESSION_SECRET_KEY` |
| `DEFAULT_API_TOKEN`, the token of the default connection | key of `config.json`, part of the podman secret of `config.json` |

The image has no file variables, so `SESSION_SECRET_KEY` is passed with `type=env`, podman sets it when the container starts.
Without it the image creates a random key at every start and all sessions end with a restart.
`DEFAULT_API_TOKEN` is no podman secret of its own, the name of the entry is not used.
A token of a database is enough to query and write, the management of databases and tokens needs an admin token.

```yaml
influxdb_explorer_secrets:
  - name: 'influxdb_explorer_session_secret_key'
    data: "{{ vault_influxdb_explorer_session_secret_key }}"
    target: 'SESSION_SECRET_KEY'
  - name: 'influxdb_explorer_api_token'
    data: "{{ vault_influxdb3_token }}"
    target: 'DEFAULT_API_TOKEN'
```

Neither target may be set in `influxdb_explorer_environment`, the token must not be set in `influxdb_explorer_config`.

### Allowed variables

The role only allows the environment variables in `database_influxdb_explorer__environment_allowed`, the keys in `database_influxdb_explorer__config_allowed`
and the secrets with the targets listed in Secrets, it stops before any change if unknown variables, keys or secrets are set.
This prevents unexpected behavior by accident, e.g. by a typo or a variable that has to be passed as secret.
The check uses the environment of the container after merging `influxdb_explorer_container`,
so variables set with `influxdb_explorer_container.environment` are checked as well.

Allowed environment variables are `DATABASE_URL`, `SSL_CERT_PATH`, `SSL_KEY_PATH`, `NODE_EXTRA_CA_CERTS`, `CA_CERT_PATH`, `LOG_LEVEL` and `TZ`.
The source of the image is not public, the list follows the [documentation](https://docs.influxdata.com/influxdb3/explorer/install/docker/)
and the [release notes](https://docs.influxdata.com/influxdb3/explorer/release-notes/) of Explorer v1.11.2, new versions of the image may add variables.

### Container

Explorer runs in the admin mode (`--mode=admin`), it manages databases and tokens of InfluxDB 3.
The read only query mode is set with `influxdb_explorer_container.command: [ '--mode=query' ]`.
Ports, volumes, e.g. the certificates in `/etc/nginx/ssl` or the CA certificates in `/ca-certs`, additional hosts (`etc_hosts`) and dependencies (`requires`)
are changed with `influxdb_explorer_container`, it is merged over the default of the container.
The merge is not recursive, `influxdb_explorer_container.volumes` replaces the data directory,
`influxdb_explorer_container.environment` replaces the environment including `influxdb_explorer_environment`, use `influxdb_explorer_environment` instead.
For a reverse proxy, e.g. Traefik, the labels are set with `influxdb_explorer_labels`, the web interface listens on port 8080.

### Validation

The role checks before any change:

- `influxdb_explorer_secrets` is a list of entries with `name`, `data` and `target` and unique names, the secret `SESSION_SECRET_KEY` exists
- `influxdb_explorer_config` is a dictionary, it only contains the allowed keys and no token, the values are strings without line breaks, `null` or `false`
- no secret is set in `influxdb_explorer_environment`
- only allowed environment variables and secrets are set in the container

If `influxdb_explorer_container` is no dictionary, merging it with the default fails before anything changes.
The default of `influxdb_explorer_config` is empty, merging it does not fail on every version of Ansible, so the role checks it itself.
A failing template in the variables, e.g. an unknown filter, stops the role before anything changes as well.

### Restart and updates

Explorer is restarted if it was running and a secret, `config.json` or the quadlet unit changed, e.g. after changing `influxdb_explorer_config`,
otherwise it is started and enabled.
Updates of the image are done by `container_update` with `influxdb_explorer_autoupdate_enabled: true` and `influxdb_explorer_autoupdate_schedule`,
without `influxdb_explorer_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

The single variables of former versions are replaced by `influxdb_explorer_config` and `influxdb_explorer_secrets`:

- `influxdb_explorer_default_server` is `DEFAULT_INFLUX_SERVER`
- `influxdb_explorer_default_database` is `DEFAULT_INFLUX_DATABASE`
- `influxdb_explorer_default_name` is `DEFAULT_SERVER_NAME`
- `influxdb_explorer_default_token` is a secret with the target `DEFAULT_API_TOKEN`
- `influxdb_explorer_session_secret` is a secret with the target `SESSION_SECRET_KEY`

The default connection was mandatory, now it is optional. `config.json` with the token was written to `influxdb_explorer_home/config`,
now it is a podman secret, the role does not remove the former directory, remove it with `rm -r <influxdb_explorer_home>/config`.
The fixed name of the secret `influxdb_explorer_session_secret` is gone, the name is free. The former secret is not removed by the role,
remove it with `podman secret rm influxdb_explorer_session_secret`.
`/etc/localtime` and `/etc/timezone` are not mounted anymore, the timezone is set with `TZ` and the timezone of the container.
The data directory is `0700` now, as required by the image.
`influxdb_explorer_labels` has no default anymore, without it the container has no labels.
`podman___update_mode` is not evaluated anymore, the role neither stops the container nor pulls the image or recreates the container.
The tag `database_influxdb_explorer` stays, the tag `database` is added.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-influxdb-explorer-default` | Only the mandatory variables and the secret `SESSION_SECRET_KEY` |
| `molecule-influxdb-explorer` | IPv6, labels, `LOG_LEVEL`, the default connection in `influxdb_explorer_config` and the token from a secret with the target `DEFAULT_API_TOKEN` |

`prepare` creates the podman network and pulls the image, Explorer does not connect to InfluxDB at the start, the tests need no InfluxDB.
`side_effect` runs the role with `influxdb_explorer_container` and `influxdb_explorer_config` not a dictionary, a secret without `target`, without the secret `SESSION_SECRET_KEY`,
`SESSION_SECRET_KEY` in the environment, an unknown key, the token and a line break in `influxdb_explorer_config`,
an unknown environment variable in `influxdb_explorer_environment` and in `influxdb_explorer_container.environment` and an unknown secret
and checks that it fails with the expected message and the quadlet unit is unchanged (tasks marked `expect ERROR`),
then it changes `DEFAULT_SERVER_NAME` on `molecule-influxdb-explorer`, only the secret of `config.json` changes, the quadlet unit stays the same and Explorer has to restart.
`verify` checks the quadlet unit with the mode, the volume and the secrets, the service, the addresses and the environment of the container,
`config.json` in the container, the data directory with the SQLite database and the web interface.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd database_influxdb_explorer
MOLECULE_TART_IMAGE='debian' molecule test
```
