The [Thanos Sidecar](https://thanos.io/tip/components/sidecar.md/) runs in the container image [thanosio/thanos](https://hub.docker.com/r/thanosio/thanos) as podman quadlet `thanos-sidecar` next to Prometheus.
The image has no tag `latest`, `thanos_sidecar_version` is mandatory, e.g. `v0.42.5`.
The sidecar serves the StoreAPI on port `10901` and its HTTP endpoints (`/-/ready`, `/metrics`) on port `10902`.

### Configuration

`thanos_sidecar_prometheus_url` is the URL of Prometheus, `http://prometheus:9090` by default,
`thanos_sidecar_prometheus_data` is the directory of the TSDB of Prometheus on the host, it is mounted to `/prometheus`.
The sidecar runs as user `nobody` (65534) like Prometheus, the owner of the TSDB, because it writes `thanos.shipper.json` there.

Prometheus needs `external_labels` that identify it uniquely in the Thanos system, the sidecar is not ready without them.
To upload blocks to the object storage, the local compaction of Prometheus has to be disabled with equal block durations,
with [monitoring_prometheus](https://ansible-roles.org/roles/monitoring-prometheus):

```yaml
prometheus_config:
  global:
    scrape_interval: '15s'
    evaluation_interval: '15s'
    external_labels:
      cluster: 'home'
      replica: 'prometheus1'
prometheus_container:
  command:
    - '--config.file=/etc/prometheus/prometheus.yml'
    - '--storage.tsdb.path=/prometheus'
    - '--storage.tsdb.min-block-duration=2h'
    - '--storage.tsdb.max-block-duration=2h'

thanos_sidecar_version: 'v0.42.5'
thanos_sidecar_ip: '192.168.99.41'
thanos_sidecar_network: 'podman99'
thanos_sidecar_hostname: 'thanos-sidecar'
thanos_sidecar_timezone: 'Europe/Berlin'
thanos_sidecar_prometheus_url: 'http://prometheus:9090'
thanos_sidecar_prometheus_data: '/srv/container/prometheus/data'
```

### Object storage

`thanos_sidecar_objstore` is the content of [bucket.yml](https://thanos.io/tip/thanos/storage.md/) as dictionary, with it the sidecar uploads the blocks of Prometheus.
The name stays `objstore` instead of `config`, it is the configuration of the object storage, not of the sidecar, the flags are part of the command.
With object storage `thanos_sidecar_home` is mandatory, the role writes bucket.yml to `<home>/bucket.yml` and mounts the file read-only to `/etc/thanos/bucket.yml`, the command gets `--objstore.config-file`.
Without `thanos_sidecar_objstore` the role removes `<home>/bucket.yml` if `thanos_sidecar_home` is set, the sidecar uploads no blocks and only serves the TSDB of Prometheus with the StoreAPI.
The keys of the first level are `type`, `config` and `prefix`, `type` is one of the providers of github.com/thanos-io/objstore
(`FILESYSTEM`, `GCS`, `S3`, `AZURE`, `SWIFT`, `COS`, `ALIYUNOSS`, `BOS`, `OCI`, `OBS`),
the allow lists are generated from `client/factory.go` and `objstore.go` of the version of Thanos v0.42.5 and prevent unexpected behavior by accident.

```yaml
thanos_sidecar_home: '/srv/container/thanos-sidecar'
thanos_sidecar_objstore:
  type: 'S3'
  config:
    bucket: 'thanos'
    endpoint: 's3.example.org'
    access_key: 'thanos'
thanos_sidecar_secrets:
  - name: 'thanos_sidecar_s3_secret_key'
    data: "{{ vault_thanos_secret_key }}"
    target: 'config.secret_key'
```

### Secrets

The providers read their credentials (e.g. `secret_key` of S3) only from bucket.yml, they cannot read them from files,
but Thanos replaces `$(VARIABLE)` in bucket.yml with the environment (`extflag.WithEnvSubstitution` of `--objstore.config-file`).
The secrets are entries of `thanos_sidecar_secrets` with `name`, `data` and `target`, the role creates them with `podman secret`
and passes them with `type=env` as `THANOS_SECRET_<TARGET>` (the target in upper case, dots replaced by `_`).
The target is the path of the option in `thanos_sidecar_objstore`, the role writes the reference `"$(THANOS_SECRET_CONFIG_SECRET_KEY)"` there,
so bucket.yml and the quadlet unit contain no credentials.

- The last key of a target is one of the options carrying secrets (`monitoring_thanos_sidecar__objstore_secret_keys`, e.g. `secret_key`, `session_token`,
  `service_account`, `storage_account_key`, `password`), these options must not be set in `thanos_sidecar_objstore`, `null` or an empty string are allowed.
- A target must not be set in `thanos_sidecar_objstore`, its path leads through dictionaries and every target is set once, secrets need an object storage.
- The data of a secret is a string without line breaks, `"` and `\`, the reference is double-quoted in bucket.yml,
  a key or service account file has to be a single line (e.g. the JSON of `service_account`).

A changed secret restarts the running sidecar.

### Allowed variables

Thanos reads no environment variables besides the references in bucket.yml, the role only allows `TZ` in `thanos_sidecar_environment`.
`thanos_sidecar_environment` has no default, without it the container has no environment, the time zone is set by podman with `thanos_sidecar_timezone`.
This prevents unexpected behavior by accident, e.g. by a variable meant for another image, the secrets are set with `thanos_sidecar_secrets`.
The check uses the environment of the container after merging `thanos_sidecar_container`.

### Container

Ports, volumes, flags and dependencies (`requires`, `wants`, `after`, `part_of`, `binds_to`, `requires_mounts_for`) are changed with `thanos_sidecar_container`, it is merged over the default of the container.
The merge is not recursive, `publish`, `volumes` and `command` replace the values of the default completely.
The default mounts the TSDB of Prometheus to `/prometheus` and with object storage `<home>/bucket.yml` to `/etc/thanos/bucket.yml`,
the command has `--tsdb.path`, `--prometheus.url` and with object storage `--objstore.config-file`.
Further flags (see the [flags of the sidecar](https://thanos.io/tip/components/sidecar.md/#flags)) or volumes need the complete list.
The command is written space separated into the quadlet unit, an argument containing `"` has to be enclosed in `'`, otherwise the `"` are lost.
For a reverse proxy, e.g. Traefik, the labels are set with `thanos_sidecar_labels`.

```yaml
thanos_sidecar_container:
  publish: [ '10901:10901' ]
  command:
    - 'sidecar'
    - '--tsdb.path=/prometheus'
    - '--prometheus.url=http://prometheus:9090'
    - '--objstore.config-file=/etc/thanos/bucket.yml'
    - '--shipper.upload-compacted'
```

### Validation

The role checks before any change, the messages name only the failing checks:

- `Render the configuration` evaluates the variables once, a missing `thanos_sidecar_prometheus_data`, `thanos_sidecar_container` that is no dictionary
  or a failing template (e.g. an unknown filter) stop the role there
- `thanos_sidecar_secrets` is a list of entries with `name`, `data` and `target` with unique names
- `thanos_sidecar_objstore` is a dictionary, if it is set with the allowed keys, a known `type`, `config` is a dictionary, the options carrying secrets are not set
  and `thanos_sidecar_home` is an absolute path
- the targets of the secrets are known, unique, not set in `thanos_sidecar_objstore` and lead through dictionaries, the data are valid,
  secrets need an object storage
- `thanos_sidecar_environment` is a dictionary without line breaks, only `TZ` is set in the environment of the container

### Check mode

The role runs with `--check`, also on a host where it never ran, and reports the changes of bucket.yml and the quadlet unit,
the sidecar is neither started nor restarted.

### Restart and updates

The sidecar is restarted if it was running and bucket.yml (written or removed), a secret or the quadlet unit changed, otherwise it is started and enabled.
If the start fails, the role shows the journal of the service.
Afterwards the role waits up to 120 seconds until `/-/ready` answers and shows the journal if the sidecar is not ready, e.g. without the external labels of Prometheus.
Updates of the image are done by `container_update` with `thanos_sidecar_autoupdate_enabled: true` and `thanos_sidecar_autoupdate_schedule`,
without `thanos_sidecar_autoupdate_schedule` the schedule of `container_update` is used.
The image has no tag `latest`, an update needs a new `thanos_sidecar_version`.

### Migration

The role replaces the component `sidecar` of `monitoring_thanos`, `thanos_component` is removed.

| Former variable | Replacement |
|---|---|
| `thanos_component: 'sidecar'` | Removed, the role `monitoring_thanos_sidecar` |
| `thanos_version`, `thanos_ip`, `thanos_ipv6`, `thanos_network`, `thanos_hostname`, `thanos_timezone`, `thanos_labels` | `thanos_sidecar_version`, `thanos_sidecar_ip`, `thanos_sidecar_ipv6`, `thanos_sidecar_network`, `thanos_sidecar_hostname`, `thanos_sidecar_timezone`, `thanos_sidecar_labels` |
| `thanos_prometheus_url`, `thanos_prometheus_data` | `thanos_sidecar_prometheus_url`, `thanos_sidecar_prometheus_data` |
| `thanos_objstore` | `thanos_sidecar_objstore` without the credentials, they are entries of `thanos_sidecar_secrets` with the path of the option as `target` |
| `thanos_container` | `thanos_sidecar_container` |
| `thanos_autoupdate_enabled`, `thanos_autoupdate_schedule` | `thanos_sidecar_autoupdate_enabled`, `thanos_sidecar_autoupdate_schedule` |
| `thanos_instances`, `tasks/loop.yml` | Removed, the role runs once per host |
| `thanos_home` | `thanos_sidecar_home`, only needed with object storage for bucket.yml, the sidecar keeps no data of its own |

Changed behavior:

- bucket.yml is no longer the podman secret `thanos-sidecar-objstore` but the file `<home>/bucket.yml` without credentials,
  with object storage `thanos_sidecar_home` is mandatory, the credentials are `thanos_sidecar_secrets` passed in the environment,
  the former secret is removed with `podman secret rm thanos-sidecar-objstore`
- `/etc/localtime` and `/etc/timezone` are no longer mounted and `TZ` has no default, the time zone is set by podman with `thanos_sidecar_timezone`,
  the quadlet unit changes once and the sidecar restarts, volumes in `thanos_sidecar_container` should no longer contain them
- `thanos_sidecar_environment` has no default and is checked against the allowed variables, unknown keys, types and plain credentials of the object storage stop the role
- the quadlet unit has the dependencies `Wants`, `After`, `PartOf`, `BindsTo` and `RequiresMountsFor` of `thanos_sidecar_container` besides `Requires`
- the role waits until the sidecar is ready and shows the journal if the start fails
- the container keeps its name `thanos-sidecar`

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root. The VMs need access to Docker Hub.

| Platform | Test case |
|---|---|
| `molecule-thanos-sidecar-default` | Only the mandatory variables, the sidecar serves the StoreAPI without object storage |
| `molecule-thanos-sidecar` | IPv6, labels, `thanos_sidecar_home` and the object storage `S3` on an S3 server of rclone, the secret key is an entry of `thanos_sidecar_secrets` |

`prepare` creates the podman network, pulls the images, starts the S3 server (`rclone serve s3`) with the bucket `thanos`
and runs Prometheus with `monitoring_prometheus` with external labels and equal block durations.
`check` runs `converge` with `--check` on the new VMs.
`side_effect` runs the role with invalid variables (tasks marked `expect ERROR`, the quadlet unit and bucket.yml stay unchanged):
`thanos_sidecar_container` and `thanos_sidecar_objstore` no dictionaries, an unknown type and key of the object storage, a secret key in the object storage,
a secret without target, an unknown target, a target set in the object storage, a quote in a secret, secrets without object storage,
an object storage without absolute home, `thanos_sidecar_environment` no dictionary, a line break in the environment of the container and an unknown environment variable.
Afterwards it changes the prefix of the object storage on `molecule-thanos-sidecar`, bucket.yml changes and the sidecar has to restart,
and runs the role again on `molecule-thanos-sidecar-default`, the sidecar must not restart.
`verify` checks the quadlet unit (secrets, time zone, no `TZ`, volume and flag of bucket.yml only with object storage), the service without automatic restarts,
bucket.yml with the reference of the secret and without the secret key or no bucket.yml without object storage
and with the HTTP endpoints that the sidecar is ready, connected to Prometheus and uploads only with an object storage.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd monitoring_thanos_sidecar
MOLECULE_TART_IMAGE='debian' molecule test
```
