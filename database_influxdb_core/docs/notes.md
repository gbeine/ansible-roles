InfluxDB 3 Core runs in the official container image [influxdb](https://hub.docker.com/_/influxdb) (`3-core` by default, `influxdb_core_version` sets the tag) as podman quadlet.
The image runs `influxdb3 serve` as the user `influxdb3` (uid 1500), the HTTP API listens on port 8181.
Below `influxdb_core_home` the role creates `data` (mounted to `/var/lib/influxdb3/data`, the catalog, the WAL and the Parquet files of the object store `file`)
and `plugins` (mounted to `/var/lib/influxdb3/plugins`, the plugins of the processing engine), both owned by the user `influxdb3`.
The role `backup_influxdb_core` stops the service `influxdb-core` and backs up `influxdb_core_home/data`.

### Configuration

InfluxDB 3 is configured completely with environment variables in `influxdb_core_environment`, merged over the default of the role.
Every option of `influxdb3 serve` has an environment variable, see `influxdb3 serve --help` or the
[configuration options](https://docs.influxdata.com/influxdb3/core/reference/config-options/), e.g. `INFLUXDB3_GEN1_DURATION`,
`INFLUXDB3_WAL_FLUSH_INTERVAL`, `INFLUXDB3_MAX_HTTP_REQUEST_SIZE`, `LOG_FILTER` or `INFLUXDB3_DISABLE_AUTHZ`. Values are strings.

The default of the role sets the options of the former command:

| Variable | Default | Description |
|---|---|---|
| `TZ` | `influxdb_core_timezone` | Timezone of the container |
| `INFLUXDB3_NODE_ID` | `node0` | Name of the node, the prefix of the files in the object store |
| `INFLUXDB3_OBJECT_STORE` | `file` | Object store: `file`, `memory`, `s3`, `google` or `azure` |
| `INFLUXDB3_DATA_DIR` | `/var/lib/influxdb3/data` | Directory of the object store `file` |
| `INFLUXDB3_PLUGIN_DIR` | `/var/lib/influxdb3/plugins` | Directory of the plugins of the processing engine |

`INFLUXDB3_NODE_ID` and `INFLUXDB3_OBJECT_STORE` are required, they must not be empty.
The other object stores are configured with `INFLUXDB3_BUCKET` and the variables of the provider, e.g. `AWS_ACCESS_KEY_ID`, `AWS_DEFAULT_REGION` and `AWS_ENDPOINT`,
the secret keys are passed with `influxdb_core_secrets`.

```yaml
influxdb_core_environment:
  INFLUXDB3_OBJECT_STORE: 's3'
  INFLUXDB3_BUCKET: 'influxdb'
  AWS_ACCESS_KEY_ID: 'influxdb'
  AWS_DEFAULT_REGION: 'eu-central-1'
  AWS_ENDPOINT: 'https://s3.example.org'
  LOG_FILTER: 'info'
```

The authentication is enabled, every request needs a token, also `/health` and `/ping`.

### Secrets

`influxdb_core_secrets` is a list of podman secrets with `name`, `data` and `target`. No secret is required.

| Target | Passed as |
|---|---|
| `INFLUXDB3_ADMIN_TOKEN`, the offline admin token | file `/run/secrets/<name>` for the user of the image, the role sets `INFLUXDB3_ADMIN_TOKEN_FILE` |
| `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`, `AZURE_STORAGE_ACCESS_KEY` | environment variable |

The data of `INFLUXDB3_ADMIN_TOKEN` is the JSON of the token file of InfluxDB 3 with `token`, `name` and the optional `expiry_millis`,
the token starts with `apiv3_`. At every start InfluxDB 3 creates the admin token of the file, if no token with the name exists.
A token is created with `influxdb3 create token --admin --offline --output-file <file>` or is any string starting with `apiv3_`.
The role checks the JSON before any change, InfluxDB 3 does not start with an invalid file.

```yaml
influxdb_core_secrets:
  - name: 'influxdb_core_admin_token'
    data: "{{ {'token': vault_influxdb_core_admin_token, 'name': 'admin'} | to_json }}"
    target: 'INFLUXDB3_ADMIN_TOKEN'
  - name: 'influxdb_core_s3_secret_access_key'
    data: "{{ vault_influxdb_core_s3_secret_access_key }}"
    target: 'AWS_SECRET_ACCESS_KEY'
```

`influxdb3 serve` reads the credentials of the object stores only from environment variables and has no file variables for them,
so they are passed with `type=env`, podman sets them when the container starts, they are not part of the quadlet unit.
The targets are the keys of `database_influxdb_core__secret_files` and `database_influxdb_core__secrets_env`.
Neither a target nor `INFLUXDB3_ADMIN_TOKEN_FILE` may be set in `influxdb_core_environment`.

### Allowed variables

The role only allows the environment variables in `database_influxdb_core__environment_allowed` and the secrets with the targets listed in Secrets,
it stops before any change if unknown variables or secrets are set.
This prevents unexpected behavior by accident, e.g. by a typo or a variable that has to be passed as secret.
The check uses the environment and the secrets of the container after merging `influxdb_core_container`,
so variables set with `influxdb_core_container.environment` are checked as well.

The allowed environment variables are the options of `influxdb3 serve` of [InfluxDB 3 Core](https://github.com/influxdata/influxdb) v3.12.2,
generated from `influxdb3/src/commands/serve.rs`, `influxdb3_clap_blocks`, `core/trogging` and `core/trace_exporters`,
without the secrets and without the internal `INFLUXDB3_SERVE_INVOCATION_METHOD` and `VIRTUAL_ENV`,
`INFLUXDB3_UNSET_VARS` of the entrypoint of the image, `INFLUXDB3_ADMIN_TOKEN_FILE` set by the role and `TZ`.
New versions of InfluxDB 3 may add options, the list is generated again from the sources.

### Container

Ports, volumes, additional hosts (`etc_hosts`) and dependencies (`requires`) are changed with `influxdb_core_container`, it is merged over the default of the container.
The merge is not recursive, `influxdb_core_container.volumes` replaces the data and the plugins,
`influxdb_core_container.environment` replaces the environment including `influxdb_core_environment`, use `influxdb_core_environment` instead.
The container uses the command of the image, `influxdb3 serve`.
For a reverse proxy, e.g. Traefik, the labels are set with `influxdb_core_labels`, the HTTP API listens on port 8181.
After the start the role waits until the port is open, so roles depending on InfluxDB 3 can use it.

### Validation

The role checks before any change:

- `influxdb_core_secrets` is a list of entries with `name`, `data` and `target` and unique names
- `INFLUXDB3_NODE_ID` and `INFLUXDB3_OBJECT_STORE` are set and not empty
- the data of the secret `INFLUXDB3_ADMIN_TOKEN` is JSON with `token` starting with `apiv3_` and `name`
- neither a secret nor `INFLUXDB3_ADMIN_TOKEN_FILE` is set in `influxdb_core_environment`
- only allowed environment variables and secrets are set in the container

If `influxdb_core_container` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Restart and updates

InfluxDB 3 is restarted if it was running and a secret or the quadlet unit changed, e.g. after changing `influxdb_core_environment`, otherwise it is started and enabled.
Updates of the image are done by `container_update` with `influxdb_core_autoupdate_enabled: true` and `influxdb_core_autoupdate_schedule`,
without `influxdb_core_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

- `influxdb_core_publish` is `influxdb_core_container.publish`
- the former command with `--node-id=node0`, `--object-store=file`, `--data-dir` and `--plugin-dir` is replaced by the default of `influxdb_core_environment`
  with the same values, the container uses the command of the image
- the admin token is new, it is set with a secret with the target `INFLUXDB3_ADMIN_TOKEN`, an existing token with the same name is kept

`/etc/localtime` and `/etc/timezone` are not mounted anymore, the timezone is set with `TZ` and the timezone of the container.
The directory `influxdb_core_home/backup` was created but never used, it is not created anymore, the role does not remove it.
The data and the plugins keep their directories, the name of the container `influxdb-core` stays for `backup_influxdb_core`.
`influxdb_core_labels` has no default anymore, without it the container has no labels.
`podman___update_mode` is not evaluated anymore, the role neither stops the container nor pulls the image or recreates the container.
The tag `database_influxdb_core` stays, the tag `database` is added.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-influxdb-core-default` | Only the mandatory variables, the authentication without a token |
| `molecule-influxdb-core` | IPv6, labels, `LOG_FILTER` and the admin token from a secret with the target `INFLUXDB3_ADMIN_TOKEN` |

`prepare` creates the podman network and pulls the image.
`side_effect` runs the role with `influxdb_core_container` not a dictionary, a secret without `target`, an empty `INFLUXDB3_NODE_ID`,
`INFLUXDB3_ADMIN_TOKEN_FILE` and `AWS_SECRET_ACCESS_KEY` in the environment, an admin token without `apiv3_` and an admin token that is no JSON,
an unknown environment variable in `influxdb_core_environment` and in `influxdb_core_container.environment` and an unknown secret
and checks that it fails with the expected message and the quadlet unit is unchanged (tasks marked `expect ERROR`),
then it waits until InfluxDB 3 answers on `molecule-influxdb-core`, shows the log of the service otherwise, and changes `LOG_FILTER`,
the quadlet unit changes and InfluxDB 3 has to restart.
`verify` checks the quadlet unit with the volumes and the mounted secret, the service, the addresses and the environment of the container
and the directories owned by the user of the image. Without a token `/health` has to answer 401, with the admin token of the secret 200,
then it writes a point with the admin token and reads it with SQL.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd database_influxdb_core
MOLECULE_TART_IMAGE='debian' molecule test
```
