[Thanos Receive](https://thanos.io/tip/components/receive.md/) runs in the container image [thanosio/thanos](https://hub.docker.com/r/thanosio/thanos) as podman quadlet `thanos-receive`.
It stores the samples Prometheus sends with remote write.
The image has no tag `latest`, `thanos_receive_version` is mandatory, e.g. `v0.42.5`.
Receive serves the StoreAPI on port `10901`, its HTTP endpoints (`/-/ready`, `/metrics`) on port `10902`
and remote write on port `19291` with the path `/api/v1/receive`.

### Configuration

`thanos_receive_home` is the directory on the host, the TSDB is stored in `<home>/data`, mounted to `/var/thanos/receive`,
the role creates it owned by user `nobody` (65534), receive runs as this user.
Without a hashring receive runs as single node and stores all samples itself.
Receive refuses to start without external labels, the default command sets `receive_replica` to `thanos_receive_hostname`.
Other labels and flags like `--tsdb.retention` (`15d` by default) are set with `thanos_receive_container.command`.

```yaml
prometheus_config:
  global:
    scrape_interval: '15s'
    evaluation_interval: '15s'
    external_labels:
      cluster: 'home'
  remote_write:
    - url: 'http://thanos-receive:19291/api/v1/receive'

thanos_receive_version: 'v0.42.5'
thanos_receive_home: '/srv/container/thanos-receive'
thanos_receive_ip: '192.168.99.42'
thanos_receive_network: 'podman99'
thanos_receive_hostname: 'thanos-receive'
thanos_receive_timezone: 'Europe/Berlin'
```

### Secrets

`thanos_receive_objstore` is the content of [bucket.yml](https://thanos.io/tip/thanos/storage.md/) as dictionary, it needs `type`.
Thanos reads the credentials of the object storage only from this file, it has no file variables and no references to the environment,
so the whole file is the secret instead of entries of a list of secrets.
The role stores it as podman secret `<container name>-objstore` (`thanos-receive-objstore` by default) and mounts it to `/etc/thanos/bucket.yml`,
so the credentials are neither a file on the host nor part of the quadlet unit, the command gets `--objstore.config-file`.
Without `thanos_receive_objstore` the secret is removed and receive uploads no blocks, it only keeps the samples in its TSDB.

```yaml
thanos_receive_objstore:
  type: 'S3'
  config:
    bucket: 'thanos'
    endpoint: 's3.example.org'
    access_key: 'thanos'
    secret_key: "{{ vault_thanos_secret_key }}"
```

### Allowed variables

Thanos reads no environment variables, the role only allows `TZ` in `thanos_receive_environment`, it is set to `thanos_receive_timezone`.
This prevents unexpected behavior by accident, e.g. by a variable meant for another image.
The check uses the environment of the container after merging `thanos_receive_container`.

### Container

Ports, volumes, flags and dependencies (`requires`) are changed with `thanos_receive_container`, it is merged over the default of the container.
The merge is not recursive, `publish`, `volumes` and `command` replace the values of the default completely.
The default mounts `<home>/data` to `/var/thanos/receive`, the command has `--tsdb.path` and `--label`.
Further flags (see the [flags of receive](https://thanos.io/tip/components/receive.md/#flags)) or volumes need the complete list.
The command is written space separated into the quadlet unit, an argument containing `"`, e.g. a label, has to be enclosed in `'`, otherwise the `"` are lost.
For a reverse proxy, e.g. Traefik, the labels are set with `thanos_receive_labels`.

```yaml
thanos_receive_container:
  publish: [ '19291:19291' ]
  command:
    - 'receive'
    - '--tsdb.path=/var/thanos/receive'
    - '''--label=receive_replica="thanos-receive"'''
    - '--tsdb.retention=30d'
```

### Validation

The role checks before any change:

- `thanos_receive_objstore` is a dictionary with `type`
- the values of `thanos_receive_environment` contain no line breaks
- only `TZ` is set in the environment of the container

If `thanos_receive_container` or `thanos_receive_environment` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Restart and updates

Receive is restarted if it was running and the secret of the object storage or the quadlet unit changed, otherwise it is started and enabled.
If the start fails, the role shows the journal of the service.
Afterwards the role waits up to 120 seconds until `/-/ready` answers and shows the journal if receive is not ready.
Updates of the image are done by `container_update` with `thanos_receive_autoupdate_enabled: true` and `thanos_receive_autoupdate_schedule`,
without `thanos_receive_autoupdate_schedule` the schedule of `container_update` is used.
The image has no tag `latest`, an update needs a new `thanos_receive_version`.

### Migration

The role replaces the component `receive` of `monitoring_thanos`, `thanos_component` is removed.

| Former variable | Replacement |
|---|---|
| `thanos_component: 'receive'` | Removed, the role `monitoring_thanos_receive` |
| `thanos_version`, `thanos_home`, `thanos_ip`, `thanos_ipv6`, `thanos_network`, `thanos_hostname`, `thanos_timezone`, `thanos_labels` | `thanos_receive_version`, `thanos_receive_home`, `thanos_receive_ip`, `thanos_receive_ipv6`, `thanos_receive_network`, `thanos_receive_hostname`, `thanos_receive_timezone`, `thanos_receive_labels` |
| `thanos_objstore` | `thanos_receive_objstore` |
| `thanos_container` | `thanos_receive_container` |
| `thanos_autoupdate_enabled`, `thanos_autoupdate_schedule` | `thanos_receive_autoupdate_enabled`, `thanos_receive_autoupdate_schedule` |
| `thanos_instances`, `tasks/loop.yml` | Removed, the role runs once per host |

Changed behavior:

- `/etc/localtime` and `/etc/timezone` are no longer mounted, the time zone is set with `thanos_receive_timezone` and `TZ`,
  the quadlet unit changes once and receive restarts, volumes in `thanos_receive_container` should no longer contain them
- `thanos_receive_environment` sets the environment, it is checked against the allowed variables
- the role waits until receive is ready and shows the journal if the start fails
- the container, the secret and the data directory keep their names `thanos-receive`, `thanos-receive-objstore` and `<home>/data`

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root. The VMs need access to Docker Hub.

| Platform | Test case |
|---|---|
| `molecule-thanos-receive-default` | Only the mandatory variables, receive keeps the samples without object storage |
| `molecule-thanos-receive` | IPv6, labels and the upload to the object storage `FILESYSTEM`, the volume of the bucket is added with `thanos_receive_container.volumes` |

`prepare` creates the podman network, pulls the images, creates the directory of the bucket
and runs Prometheus with `monitoring_prometheus`, it sends its samples with remote write to receive.
`side_effect` runs the role with `thanos_receive_container` not a dictionary, an object storage without `type` and not a dictionary,
a line break in the environment and an unknown environment variable
and checks that it fails with the expected message and the quadlet unit is unchanged (tasks marked `expect ERROR`),
then it changes the object storage on `molecule-thanos-receive`, the secret changes and receive has to restart.
`verify` checks the quadlet unit without the mounts of the time zone, the service, the environment, the secret,
the external label in the command of the container, the data directory owned by `nobody`, that receive is ready
and that the TSDB of the tenant `default-tenant` received samples of Prometheus.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd monitoring_thanos_receive
MOLECULE_TART_IMAGE='debian' molecule test
```
