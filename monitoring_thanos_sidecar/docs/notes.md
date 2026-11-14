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

### Secrets

`thanos_sidecar_objstore` is the content of [bucket.yml](https://thanos.io/tip/thanos/storage.md/) as dictionary, it needs `type`.
Thanos reads the credentials of the object storage only from this file, it has no file variables and no references to the environment,
so the whole file is the secret instead of entries of a list of secrets.
The role stores it as podman secret `<container name>-objstore` (`thanos-sidecar-objstore` by default) and mounts it to `/etc/thanos/bucket.yml`,
so the credentials are neither a file on the host nor part of the quadlet unit, the command gets `--objstore.config-file`.
Without `thanos_sidecar_objstore` the secret is removed and the sidecar uploads nothing, it only serves the StoreAPI.

```yaml
thanos_sidecar_objstore:
  type: 'S3'
  config:
    bucket: 'thanos'
    endpoint: 's3.example.org'
    access_key: 'thanos'
    secret_key: "{{ vault_thanos_secret_key }}"
```

### Allowed variables

Thanos reads no environment variables, the role only allows `TZ` in `thanos_sidecar_environment`, it is set to `thanos_sidecar_timezone`.
This prevents unexpected behavior by accident, e.g. by a variable meant for another image.
The check uses the environment of the container after merging `thanos_sidecar_container`.

### Container

Ports, volumes, flags and dependencies (`requires`) are changed with `thanos_sidecar_container`, it is merged over the default of the container.
The merge is not recursive, `publish`, `volumes` and `command` replace the values of the default completely.
The default mounts the TSDB of Prometheus to `/prometheus`, the command has `--tsdb.path` and `--prometheus.url`.
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

The role checks before any change:

- `thanos_sidecar_objstore` is a dictionary with `type`
- the values of `thanos_sidecar_environment` contain no line breaks
- only `TZ` is set in the environment of the container

If `thanos_sidecar_container` or `thanos_sidecar_environment` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Restart and updates

The sidecar is restarted if it was running and the secret of the object storage or the quadlet unit changed, otherwise it is started and enabled.
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
| `thanos_objstore` | `thanos_sidecar_objstore` |
| `thanos_container` | `thanos_sidecar_container` |
| `thanos_autoupdate_enabled`, `thanos_autoupdate_schedule` | `thanos_sidecar_autoupdate_enabled`, `thanos_sidecar_autoupdate_schedule` |
| `thanos_instances`, `tasks/loop.yml` | Removed, the role runs once per host |
| `thanos_home` | Removed, the sidecar keeps no data of its own |

Changed behavior:

- `/etc/localtime` and `/etc/timezone` are no longer mounted, the time zone is set with `thanos_sidecar_timezone` and `TZ`,
  the quadlet unit changes once and the sidecar restarts, volumes in `thanos_sidecar_container` should no longer contain them
- `thanos_sidecar_environment` sets the environment, it is checked against the allowed variables
- the role waits until the sidecar is ready and shows the journal if the start fails
- the container and the secret keep their names `thanos-sidecar` and `thanos-sidecar-objstore`

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root. The VMs need access to Docker Hub.

| Platform | Test case |
|---|---|
| `molecule-thanos-sidecar-default` | Only the mandatory variables, the sidecar serves the StoreAPI without object storage |
| `molecule-thanos-sidecar` | IPv6, labels and the upload to the object storage `FILESYSTEM`, the volume of the bucket is added with `thanos_sidecar_container.volumes` |

`prepare` creates the podman network, pulls the images, creates the directory of the bucket
and runs Prometheus with `monitoring_prometheus` with external labels and equal block durations.
`side_effect` runs the role with `thanos_sidecar_container` not a dictionary, an object storage without `type` and not a dictionary,
a line break in the environment and an unknown environment variable
and checks that it fails with the expected message and the quadlet unit is unchanged (tasks marked `expect ERROR`),
then it changes the object storage on `molecule-thanos-sidecar`, the secret changes and the sidecar has to restart.
`verify` checks the quadlet unit without the mounts of the time zone, the service, the environment, the secret
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
