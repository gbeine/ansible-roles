Chronograf runs in the official container image [chronograf](https://hub.docker.com/_/chronograf) (`latest` by default, `chronograf_version` sets the tag) as podman quadlet.
The image runs Chronograf as the user `chronograf` (uid 999), the web interface listens on port 8888.
Below `chronograf_home` the role creates `data`, owned by the user `chronograf` and mounted to `/var/lib/chronograf`,
it holds the BoltDB database `chronograf-v1.db` with the sources, the dashboards, the users and the organizations.
InfluxDB and Kapacitor are not part of the role.

### Configuration

Chronograf is configured completely with environment variables in `chronograf_environment`, merged over the default of the role.
The default sets `TZ` to `chronograf_timezone`, the passwords, tokens and client secrets are passed with `chronograf_secrets` (see Secrets).
Every option of Chronograf has an environment variable, see `chronograf --help` or the
[configuration options](https://docs.influxdata.com/chronograf/v1/administration/config-options/), e.g. `INFLUXDB_URL`, `KAPACITOR_URL`,
`BASE_PATH`, `LOG_LEVEL` or the OAuth 2.0 providers `GH_*`, `GOOGLE_*` and `GENERIC_*`. Values are strings, e.g. `'true'`.

With `INFLUXDB_URL` Chronograf creates the source of InfluxDB at the start, with `KAPACITOR_URL` the Kapacitor of this source.

```yaml
chronograf_environment:
  INFLUXDB_URL: 'http://influxdb:8086'
  INFLUXDB_USERNAME: 'chronograf'
  KAPACITOR_URL: 'http://kapacitor:9092'
  BASE_PATH: '/chronograf'
```

### Secrets

`chronograf_secrets` is a list of podman secrets with `name`, `data` and `target`, the name of the environment variable, e.g. `INFLUXDB_PASSWORD`.
No secret is required.
Chronograf reads its options only from environment variables and has no file variables, so the secrets are passed with `type=env`,
podman sets them when the container starts, they are not part of the quadlet unit.

The allowed targets are the options carrying passwords, tokens and client secrets in `database_chronograf__secrets_allowed`:
`AUTH0_CLIENT_SECRET`, `ETCD_PASSWORD`, `GENERIC_CLIENT_SECRET`, `GH_CLIENT_SECRET`, `GOOGLE_CLIENT_SECRET`, `HEROKU_SECRET`,
`INFLUXDB_MGMT_TOKEN`, `INFLUXDB_PASSWORD`, `INFLUXDB_TOKEN`, `KAPACITOR_PASSWORD` and `TOKEN_SECRET`.
They must not be set in `chronograf_environment`.
`TOKEN_SECRET` signs the tokens of the OAuth 2.0 authentication. Chronograf does not start with `TOKEN_SECRET` without an OAuth 2.0 provider,
and a provider is only used with all of its options, the role checks both before any change:

| Provider | Started by | Needs |
|---|---|---|
| GitHub | `GH_CLIENT_ID`, `GH_CLIENT_SECRET` | `GH_CLIENT_ID`, `GH_CLIENT_SECRET`, `TOKEN_SECRET` |
| Google | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `PUBLIC_URL`, `TOKEN_SECRET` |
| Heroku | `HEROKU_CLIENT_ID`, `HEROKU_SECRET` | `HEROKU_CLIENT_ID`, `HEROKU_SECRET`, `TOKEN_SECRET` |
| Generic | `GENERIC_CLIENT_ID`, `GENERIC_CLIENT_SECRET`, `GENERIC_AUTH_URL`, `GENERIC_TOKEN_URL` | all of them and `TOKEN_SECRET` |
| Auth0 | `AUTH0_CLIENT_ID`, `AUTH0_CLIENT_SECRET` | `AUTH0_CLIENT_ID`, `AUTH0_CLIENT_SECRET` |

The client secrets and `TOKEN_SECRET` are secrets, the other options are set in `chronograf_environment`.

```yaml
chronograf_secrets:
  - name: 'chronograf_influxdb_password'
    data: "{{ vault_chronograf_influxdb_password }}"
    target: 'INFLUXDB_PASSWORD'
```

### Allowed variables

The role only allows the environment variables in `database_chronograf__environment_allowed` and the secrets in `database_chronograf__secrets_allowed`,
it stops before any change if unknown variables or secrets are set.
This prevents unexpected behavior by accident, e.g. by a typo or a variable that has to be passed as secret.
The check uses the environment and the secrets of the container after merging `chronograf_container`,
so variables set with `chronograf_container.environment` are checked as well.

The allowed environment variables are the options of `server/server.go` of [Chronograf](https://github.com/influxdata/chronograf) 1.11.7
without the options carrying secrets, and `TZ`. New versions of Chronograf may add options, the lists are generated again from `server/server.go`.

### Container

Ports, volumes, additional hosts (`etc_hosts`) and dependencies (`requires`) are changed with `chronograf_container`, it is merged over the default of the container.
The merge is not recursive, `chronograf_container.volumes` replaces the data directory,
`chronograf_container.environment` replaces the environment including `chronograf_environment`, use `chronograf_environment` instead.
For a reverse proxy, e.g. Traefik, the labels are set with `chronograf_labels`, the web interface listens on port 8888.

### Validation

The role checks before any change:

- `chronograf_secrets` is a list of entries with `name`, `data` and `target` and unique names
- no secret is set in `chronograf_environment`
- `TOKEN_SECRET` is only set with an OAuth 2.0 provider, a started provider has all of its options
- only allowed environment variables and secrets are set in the container

If `chronograf_container` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Restart and updates

Chronograf is restarted if it was running and a secret or the quadlet unit changed, e.g. after changing `chronograf_environment`, otherwise it is started and enabled.
Updates of the image are done by `container_update` with `chronograf_autoupdate_enabled: true` and `chronograf_autoupdate_schedule`,
without `chronograf_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

The role is new, there is nothing to migrate.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-chronograf-default` | Only the mandatory variables, Chronograf without a source |
| `molecule-chronograf` | IPv6, labels, `LOG_LEVEL`, InfluxDB as source with `INFLUXDB_URL`, `INFLUXDB_USERNAME` and the password from a secret |

`prepare` creates the podman network, pulls the images and starts InfluxDB 1.8 with authentication.
`side_effect` runs the role with `chronograf_container` not a dictionary, a secret without `target`, `INFLUXDB_PASSWORD` in the environment,
`TOKEN_SECRET` without an OAuth 2.0 provider, an incomplete OAuth 2.0 provider,
an unknown environment variable in `chronograf_environment` and in `chronograf_container.environment` and an unknown secret
and checks that it fails with the expected message and the quadlet unit is unchanged (tasks marked `expect ERROR`),
then it waits until Chronograf answers on `molecule-chronograf`, shows the log of the service otherwise, and changes `LOG_LEVEL`, the quadlet unit changes and Chronograf has to restart.
`verify` checks the quadlet unit with the volume and the secrets, the service, the addresses and the environment of the container,
the data directory owned by the user `chronograf` of the image with the database, the sources of Chronograf
and the health of the source of InfluxDB, which connects with the password of the secret.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd database_chronograf
MOLECULE_TART_IMAGE='debian' molecule test
```
