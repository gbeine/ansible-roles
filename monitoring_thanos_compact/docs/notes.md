[Thanos Compact](https://thanos.io/tip/components/compact.md/) runs in the container image [thanosio/thanos](https://hub.docker.com/r/thanosio/thanos) as podman quadlet `thanos-compact`.
It compacts and downsamples the blocks of the object storage and applies the retention, only one compact may run per bucket.
Compact serves no StoreAPI, only its HTTP endpoints (`/-/ready`, `/metrics`) on port `10902`.
The image has no tag `latest`, `thanos_compact_version` is mandatory, e.g. `v0.42.5`.

### Configuration

`thanos_compact_home` is the directory on the host, `<home>/data` is mounted to `/var/thanos/compact`,
the role creates it owned by user `nobody` (65534), compact runs as this user.
The directory is the working directory of the compaction.
Compact runs with `--wait`, it starts a run at once and then waits for the next one instead of exiting after one run.
Retention flags like `--retention.resolution-raw` are set with `thanos_compact_container.command`.

```yaml
thanos_compact_version: 'v0.42.5'
thanos_compact_home: '/srv/container/thanos-compact'
thanos_compact_ip: '192.168.99.45'
thanos_compact_network: 'podman99'
thanos_compact_hostname: 'thanos-compact'
thanos_compact_timezone: 'Europe/Berlin'
thanos_compact_objstore:
  type: 'S3'
  config:
    bucket: 'thanos'
    endpoint: 's3.example.org'
    access_key: 'thanos'
    secret_key: "{{ vault_thanos_secret_key }}"
```

### Secrets

`thanos_compact_objstore` is mandatory, it is the content of [bucket.yml](https://thanos.io/tip/thanos/storage.md/) as dictionary and needs `type`.
Thanos reads the credentials of the object storage only from this file, it has no file variables and no references to the environment,
so the whole file is the secret instead of entries of a list of secrets.
The role stores it as podman secret `<container name>-objstore` (`thanos-compact-objstore` by default) and mounts it to `/etc/thanos/bucket.yml`,
so the credentials are neither a file on the host nor part of the quadlet unit, the command gets `--objstore.config-file`.

### Allowed variables

Thanos reads no environment variables, the role only allows `TZ` in `thanos_compact_environment`, it is set to `thanos_compact_timezone`.
This prevents unexpected behavior by accident, e.g. by a variable meant for another image.
The check uses the environment of the container after merging `thanos_compact_container`.

### Container

Ports, volumes, flags and dependencies (`requires`) are changed with `thanos_compact_container`, it is merged over the default of the container.
The merge is not recursive, `publish`, `volumes` and `command` replace the values of the default completely.
The default mounts `<home>/data` to `/var/thanos/compact`, the command has `--wait`, `--data-dir` and `--objstore.config-file`.
Further flags (see the [flags of compact](https://thanos.io/tip/components/compact.md/#flags)) or volumes need the complete list.
The command is written space separated into the quadlet unit, an argument containing `"` has to be enclosed in `'`, otherwise the `"` are lost.
For a reverse proxy, e.g. Traefik, the labels are set with `thanos_compact_labels`.

```yaml
thanos_compact_container:
  command:
    - 'compact'
    - '--wait'
    - '--data-dir=/var/thanos/compact'
    - '--objstore.config-file=/etc/thanos/bucket.yml'
    - '--retention.resolution-raw=30d'
```

### Validation

The role checks before any change:

- `thanos_compact_objstore` is a dictionary with `type` and is set
- the values of `thanos_compact_environment` contain no line breaks
- only `TZ` is set in the environment of the container

If `thanos_compact_container` or `thanos_compact_environment` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Restart and updates

Compact is restarted if it was running and the secret of the object storage or the quadlet unit changed, otherwise it is started and enabled.
If the start fails, the role shows the journal of the service.
Afterwards the role waits up to 120 seconds until `/-/ready` answers and shows the journal if compact is not ready.
Updates of the image are done by `container_update` with `thanos_compact_autoupdate_enabled: true` and `thanos_compact_autoupdate_schedule`,
without `thanos_compact_autoupdate_schedule` the schedule of `container_update` is used.
The image has no tag `latest`, an update needs a new `thanos_compact_version`.

### Migration

The role replaces the component `compact` of `monitoring_thanos`, `thanos_component` is removed.

| Former variable | Replacement |
|---|---|
| `thanos_component: 'compact'` | Removed, the role `monitoring_thanos_compact` |
| `thanos_version`, `thanos_home`, `thanos_ip`, `thanos_ipv6`, `thanos_network`, `thanos_hostname`, `thanos_timezone`, `thanos_labels` | `thanos_compact_version`, `thanos_compact_home`, `thanos_compact_ip`, `thanos_compact_ipv6`, `thanos_compact_network`, `thanos_compact_hostname`, `thanos_compact_timezone`, `thanos_compact_labels` |
| `thanos_objstore` | `thanos_compact_objstore` |
| `thanos_container` | `thanos_compact_container` |
| `thanos_autoupdate_enabled`, `thanos_autoupdate_schedule` | `thanos_compact_autoupdate_enabled`, `thanos_compact_autoupdate_schedule` |
| `thanos_instances`, `tasks/loop.yml` | Removed, the role runs once per host |

Changed behavior:

- `/etc/localtime` and `/etc/timezone` are no longer mounted, the time zone is set with `thanos_compact_timezone` and `TZ`,
  the quadlet unit changes once and store restarts, volumes in `thanos_compact_container` should no longer contain them
- `thanos_compact_environment` sets the environment, it is checked against the allowed variables
- the role waits until compact is ready and shows the journal if the start fails
- the container, the secret and the data directory keep their names `thanos-compact`, `thanos-compact-objstore` and `<home>/data`

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root. The VMs need access to Docker Hub.

| Platform | Test case |
|---|---|
| `molecule-thanos-compact-default` | Only the mandatory variables with the object storage `FILESYSTEM`, the volume of the bucket is added with `thanos_compact_container.volumes` |
| `molecule-thanos-compact` | IPv6 and labels |

`prepare` creates the podman network, pulls the image and creates the directories of the bucket.
`side_effect` runs the role with `thanos_compact_container` not a dictionary, an object storage without `type`, missing and not a dictionary,
a line break in the environment and an unknown environment variable
and checks that it fails with the expected message and the quadlet unit is unchanged (tasks marked `expect ERROR`),
then it changes the object storage on `molecule-thanos-compact`, the secret changes and compact has to restart.
`verify` checks the quadlet unit without the mounts of the time zone, the service, the environment, the secret,
the data directory owned by `nobody`, that compact is ready and that it finished a run over the bucket.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd monitoring_thanos_compact
MOLECULE_TART_IMAGE='debian' molecule test
```
