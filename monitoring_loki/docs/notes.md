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

Loki runs with `-config.file=/etc/loki/config.yaml -config.expand-env=true`, the flags are changed with `loki_container.command`.

### Secrets

Loki reads its secrets (e.g. `secret_access_key` of S3 or the password of the Alertmanager) only from its configuration, there are no file variables.
So the secrets are passed in the environment with `type=env,target=<target>` and referenced in `loki_config` with `${TARGET}` or `${TARGET:-default}`,
Loki expands them with `-config.expand-env=true`. `config.yaml` only contains the references, not the secrets.

`loki_secrets` is a list of podman secrets with `name`, `data` and `target`:

- the targets have to match `^LOKI_[A-Z0-9_]+$`, they are distinct from `TZ` and the variables of the image
- every target has to be referenced in `loki_config`
- no target may be set in `loki_environment`

The fields `secret_access_key`, `password`, `basic_auth_password`, `client_secret`, `account_key`, `sas_token`, `session_token`, `secret_key`
and `service_account` have to reference a secret anywhere in `loki_config`, a password in plain text is rejected.

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
        secret_access_key: '${LOKI_S3_SECRET_ACCESS_KEY}'
loki_secrets:
  - name: 'loki_s3_secret_access_key'
    data: "{{ vault_loki_s3_secret_access_key }}"
    target: 'LOKI_S3_SECRET_ACCESS_KEY'
```

### Allowed variables

Loki reads no environment variables besides those referenced by the configuration, the role only allows `TZ` in `loki_environment`
and the secrets of `loki_secrets`. This prevents unexpected behavior by accident, e.g. by a variable meant for another image.
The check uses the environment of the container after merging `loki_container`.

### Container

The flags (`command`), ports, volumes, additional hosts (`etc_hosts`) and dependencies (`requires`) are changed with `loki_container`,
it is merged over the default of the container. The merge is not recursive, `loki_container.volumes` replaces the configuration and the data.
For a reverse proxy, e.g. Traefik, the labels are set with `loki_labels`.
`<loki_home>` and `config.yaml` belong to root (`0755`, `0644`), the data directory belongs to `loki` (10001) with the mode `0750`.

### Validation

The role checks before any change:

- `loki_secrets` is a list of entries with `name`, `data` and `target`, unique names and targets matching `^LOKI_[A-Z0-9_]+$`
- every secret is referenced in `loki_config`, no field carrying a secret contains a value in plain text
- no secret is set in `loki_environment`, values and secrets contain no line breaks
- only `TZ` is set in the environment of the container
- Loki accepts the configuration: the role writes `config.yaml` only after `loki -verify-config` of the image succeeded in a throwaway container without network,
  Loki rejects e.g. unknown fields. The secrets are replaced by placeholders there, they are never part of a command line.

If `loki_config` or `loki_container` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Restart and updates

Loki is restarted if it was running and a secret, `config.yaml` or the quadlet unit changed, otherwise it is started and enabled.
If the start fails, the role shows the journal of the service.
Afterwards the role waits up to 120 seconds until `/ready` answers, the ingester reports ready some seconds after the start, and shows the journal if Loki does not answer.
Updates of the image are done by `container_update` with `loki_autoupdate_enabled: true` and `loki_autoupdate_schedule`,
without `loki_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

The role is new, there are no former variables.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root. The VMs need access to Docker Hub.

| Platform | Test case |
|---|---|
| `molecule-loki-default` | Only the mandatory variables |
| `molecule-loki` | IPv6, labels, limits and the password of the Alertmanager of the ruler as secret |

`prepare` creates the podman network, installs `curl` and pulls the image.
`side_effect` runs the role with `loki_container` and `loki_config` not a dictionary, a secret without `target`, a target against the pattern,
a secret not referenced in the configuration, a password in plain text, a secret in the environment, an unknown variable, a line break in a value
and an unknown field rejected by `loki -verify-config`
and checks that it fails with the expected message and the quadlet unit and `config.yaml` are unchanged (tasks marked `expect ERROR`),
then it pushes a log line and changes the limits on `molecule-loki`, `config.yaml` changes and Loki has to restart.
`verify` checks the quadlet unit with the flags and the secret without its value, the service, the addresses, the environment,
the files and that `config.yaml` references the secret, `/ready`, the version and the running configuration of `/config`
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
