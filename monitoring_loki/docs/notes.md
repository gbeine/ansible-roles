Loki, the log aggregation of Grafana, runs in the container image [grafana/loki](https://hub.docker.com/r/grafana/loki)
(`latest` by default, `loki_version` sets the tag, e.g. `3.7.10`) as podman quadlet in the monolithic mode, all components in one process.
It listens on port 3100 and serves the API to push and query logs, `/ready`, `/metrics` and `/config`.
The configuration is kept in `<loki_home>/config.yaml`, mounted read-only as `/etc/loki/config.yaml`, the data in `<loki_home>/data`, mounted as `/loki`.
The image is built from `distroless` without a shell and runs Loki as `loki` (10001).

Loki has no authentication. `auth_enabled` only enables the tenants with the header `X-Scope-OrgID`, it does not check anybody.
Loki must only be reachable from the network of its clients (e.g. Alloy, Grafana) or through a reverse proxy with authentication.

### Configuration

`loki_config` is merged over the default of the role, every key replaces the key of the default completely, like `prometheus_config` of `monitoring_prometheus`.
The default is `cmd/loki/loki-docker-config.yaml` of Loki v3.7.10: no tenants, the port 3100, one instance with the storage on the filesystem below `/loki`
and the schema `v13` with `tsdb`. It also sets `analytics.reporting_enabled: false`, Loki does not send reports of its usage to Grafana Labs.
The keys are described in the [configuration of Loki](https://grafana.com/docs/loki/latest/configure/).

```yaml
loki_config:
  limits_config:
    retention_period: '744h'
  compactor:
    working_directory: '/loki/compactor'
    retention_enabled: true
    delete_request_store: 'filesystem'
```

`null` removes a key of the default, e.g. `ruler: ~` removes the ruler of the default with its Alertmanager on `localhost:9093`,
Loki uses its built-in defaults for the removed key then.

Loki runs with `-config.file=/etc/loki/config.yaml -config.expand-env=true`, the flags are changed with `loki_container.command`.

### Secrets

Loki reads its secrets (e.g. `secret_access_key` of S3 or the password of the Alertmanager) only from its configuration,
the configuration cannot read files and there are no file variables. So the secrets are passed in the environment
with `type=env` and referenced in `config.yaml`, Loki expands the references with `-config.expand-env=true`.

`loki_secrets` is a list of podman secrets with `name`, `data` and `target`, the target is the path of the option in `loki_config`,
e.g. `common.storage.s3.secret_access_key`. The last key of the path is one of the fields carrying secrets:
`secret_access_key`, `password`, `basic_auth_password`, `client_secret`, `account_key`, `sas_token`, `session_token`, `secret_key`
and `service_account`. The role passes the secret as `LOKI_SECRET_<PATH>` (the path in upper case, dots replaced by `_`)
and writes the reference `"${LOKI_SECRET_<PATH>}"` to the option in `config.yaml`, `config.yaml` and the quadlet unit never contain the secret.
Loki replaces the references before it parses the YAML, the reference is double-quoted, so the replaced secret stays a string,
e.g. a secret containing `: ` or ` #` neither breaks the YAML nor is cut off.
The data of a secret must not contain line breaks, `"` and `\`, they would end the string or start an escape sequence.

```yaml
loki_config:
  common:
    path_prefix: '/loki'
    replication_factor: 1
    ring:
      kvstore:
        store: 'inmemory'
    storage:
      s3:
        endpoint: 's3.example.org'
        bucketnames: 'loki'
        access_key_id: 'loki'
loki_secrets:
  - name: 'loki_s3_secret_access_key'
    data: "{{ vault_loki_s3_secret_access_key }}"
    target: 'common.storage.s3.secret_access_key'
```

The fields carrying secrets must not be set in `loki_config`, neither a password in plain text nor a reference.
The dictionaries on the path of a target may be missing in `loki_config`, the role creates them, a list or a value on the path is rejected.

### Allowed variables

The role only allows the keys of `monitoring_loki__config_allowed` on the first level of `loki_config`, generated from `Config` in `pkg/loki/loki.go`
of Loki v3.7.10, Loki itself checks the keys below with `-verify-config`. `loki_environment` has no default and only takes `TZ`,
Loki reads no other variables. The secrets of the container have to be the secrets of `loki_secrets`.
This prevents unexpected behavior by accident, e.g. by a typo, a variable meant for another image or a password that has to be passed as secret.
The check of the environment uses the environment of the container after merging `loki_container`.
The time zone of the container is `loki_timezone`, set by podman, the image sets no `TZ`.

### Container

The flags (`command`), ports, volumes, additional hosts (`etc_hosts`) and dependencies are changed with `loki_container`,
it is merged over the default of the container. The merge is not recursive, `loki_container.volumes` replaces the configuration and the data,
`loki_container.command` replaces the flags, the secrets need `-config.expand-env=true`.
The dependencies of the quadlet unit are lists: `requires`, `wants`, `after`, `part_of` and `binds_to` are units,
`requires_mounts_for` are paths. They are written to `[Unit]` as `Requires=`, `Wants=`, `After=`, `PartOf=`, `BindsTo=` and `RequiresMountsFor=`.
For a reverse proxy, e.g. Traefik, the labels are set with `loki_labels`.
`<loki_home>` and `config.yaml` belong to root (`0755`, `0644`), the data directory belongs to `loki` (10001) with the mode `0750`.

```yaml
loki_container:
  requires_mounts_for: [ '/srv/loki' ]
```

### Validation

The role checks before any change:

- `loki_secrets` is a list of entries with `name`, `data` and `target` and unique names, every target is a path ending in a field carrying secrets
  and set once, it is not set in `loki_config` and leads through dictionaries only, the data are strings without line breaks, `"` and `\`,
  podman checks the names of the secrets
- `loki_config` contains only known keys on the first level and no field carrying secrets
- `loki_environment`, if set, is a dictionary without line breaks
- only `TZ` without line breaks and the secrets of `loki_secrets` are set in the container
- Loki accepts the configuration: the role writes `config.yaml` only after `loki -verify-config` of the image succeeded in a throwaway container without network,
  Loki rejects e.g. unknown fields. The secrets are replaced by placeholders there, they are never part of a command line.

If `loki_config` or `loki_container` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Check mode

The role runs with `--check`, also on a host where it never ran, and reports the directories, `config.yaml`, the secrets and the quadlet unit.
`-verify-config`, the start and the wait for Loki do not run in check mode.

### Restart and updates

Loki is restarted if it was running and a secret, `config.yaml` or the quadlet unit changed, otherwise it is started and enabled.
If the start fails, the role shows the error and the journal of the service.
Afterwards the role waits up to 120 seconds until `/ready` answers, the ingester reports ready some seconds after the start, and shows the journal if Loki does not answer.
Updates of the image are done by `container_update` with `loki_autoupdate_enabled: true` and `loki_autoupdate_schedule`,
without `loki_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

- The targets of `loki_secrets` are the paths of the options now, e.g. `ruler.alertmanager_client.basic_auth_password` instead of `LOKI_ALERTMANAGER_PASSWORD`.
  Remove the references `${LOKI_…}` from `loki_config`, the role writes the references itself.
- `TZ` is not set by default anymore, the time zone is set by podman with `loki_timezone`.
- The references of the secrets are double-quoted in `config.yaml`, before a secret containing e.g. `: ` or ` #` broke the YAML or was cut off.
  `config.yaml` changes once and Loki restarts, secrets containing `"` or `\` are rejected.
- Fixed bug: a key of `loki_config` set to `null` was written as `key: null` to `config.yaml`, now it removes the key of the default.
- Unknown keys on the first level of `loki_config` are rejected, `requires_mounts_for`, `wants`, `after`, `part_of` and `binds_to` of `loki_container` are new.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root. The VMs need access to Docker Hub.

| Platform | Test case |
|---|---|
| `molecule-loki-default` | Only the mandatory variables |
| `molecule-loki` | IPv6, labels, limits, `server: ~` removes the key of the default and the password of the Alertmanager of the ruler as secret with its path as target |

`prepare` creates the podman network, installs `curl` and pulls the image.
`check` runs `converge` with `--check` on the new VMs.
`side_effect` runs the role with `loki_container` and `loki_config` not a dictionary, an unknown key, a password in `loki_config`,
a secret without `target`, an unknown secret, a target set twice, a secret in a list, a quote in a secret, `loki_environment` not a dictionary,
an unknown variable, a line break in a value and an unknown field rejected by `loki -verify-config`
and checks that it fails with the expected message and the quadlet unit and `config.yaml` are unchanged (tasks marked `expect ERROR`),
then it pushes a log line and changes the limits on `molecule-loki`, `config.yaml` changes and Loki has to restart,
`molecule-loki-default` runs again without a change and Loki must not restart.
`verify` checks the quadlet unit with the flags and the secret without its value, the service without automatic restarts, the addresses,
the time zone and no `TZ` in the environment,
the files, that `config.yaml` references the secret double-quoted and contains no removed key and no `null`, `/ready`, the version and the running configuration of `/config`
(no reports of the usage, the limits, the expanded password of the Alertmanager),
pushes a log line and finds it with `query_range`, on `molecule-loki` also the line pushed before the restart.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd monitoring_loki
MOLECULE_TART_IMAGE='debian' molecule test
```
