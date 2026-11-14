[Thanos Store](https://thanos.io/tip/components/store.md/) runs in the container image [thanosio/thanos](https://hub.docker.com/r/thanosio/thanos) as podman quadlet `thanos-store`.
It serves the blocks of the object storage with the StoreAPI on port `10901`, its HTTP endpoints (`/-/ready`, `/metrics`) are on port `10902`.
The image has no tag `latest`, `thanos_store_version` is mandatory, e.g. `v0.42.5`.

### Configuration

`thanos_store_home` is the directory on the host, `<home>/data` is mounted to `/var/thanos/store`,
the role creates it owned by user `nobody` (65534), store runs as this user.
The directory is a cache of the index of the blocks, it is rebuilt if removed.
Store is ready after it synchronized the blocks of the bucket.

```yaml
thanos_store_version: 'v0.42.5'
thanos_store_home: '/srv/container/thanos-store'
thanos_store_ip: '192.168.99.44'
thanos_store_network: 'podman99'
thanos_store_hostname: 'thanos-store'
thanos_store_timezone: 'Europe/Berlin'
thanos_store_objstore:
  type: 'S3'
  config:
    bucket: 'thanos'
    endpoint: 's3.example.org'
    access_key: 'thanos'
    secret_key: "{{ vault_thanos_secret_key }}"
```

### Secrets

`thanos_store_objstore` is mandatory, it is the content of [bucket.yml](https://thanos.io/tip/thanos/storage.md/) as dictionary and needs `type`.
Thanos reads the credentials of the object storage only from this file, it has no file variables and no references to the environment,
so the whole file is the secret instead of entries of a list of secrets.
The role stores it as podman secret `<container name>-objstore` (`thanos-store-objstore` by default) and mounts it to `/etc/thanos/bucket.yml`,
so the credentials are neither a file on the host nor part of the quadlet unit, the command gets `--objstore.config-file`.

### Allowed variables

Thanos reads no environment variables, the role only allows `TZ` in `thanos_store_environment`, it is set to `thanos_store_timezone`.
This prevents unexpected behavior by accident, e.g. by a variable meant for another image.
The check uses the environment of the container after merging `thanos_store_container`.

### Container

Ports, volumes, flags and dependencies (`requires`) are changed with `thanos_store_container`, it is merged over the default of the container.
The merge is not recursive, `publish`, `volumes` and `command` replace the values of the default completely.
The default mounts `<home>/data` to `/var/thanos/store`, the command has `--data-dir` and `--objstore.config-file`.
Further flags (see the [flags of store](https://thanos.io/tip/components/store.md/#flags)) or volumes need the complete list.
The command is written space separated into the quadlet unit, an argument containing `"` has to be enclosed in `'`, otherwise the `"` are lost.
For a reverse proxy, e.g. Traefik, the labels are set with `thanos_store_labels`.

```yaml
thanos_store_container:
  publish: [ '10901:10901' ]
  command:
    - 'store'
    - '--data-dir=/var/thanos/store'
    - '--objstore.config-file=/etc/thanos/bucket.yml'
    - '--min-time=-30d'
```

### Validation

The role checks before any change:

- `thanos_store_objstore` is a dictionary with `type` and is set
- the values of `thanos_store_environment` contain no line breaks
- only `TZ` is set in the environment of the container

If `thanos_store_container` or `thanos_store_environment` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Restart and updates

Store is restarted if it was running and the secret of the object storage or the quadlet unit changed, otherwise it is started and enabled.
If the start fails, the role shows the journal of the service.
Afterwards the role waits up to 120 seconds until `/-/ready` answers and shows the journal if store is not ready.
Updates of the image are done by `container_update` with `thanos_store_autoupdate_enabled: true` and `thanos_store_autoupdate_schedule`,
without `thanos_store_autoupdate_schedule` the schedule of `container_update` is used.
The image has no tag `latest`, an update needs a new `thanos_store_version`.

### Migration

The role replaces the component `store` of `monitoring_thanos`, `thanos_component` is removed.

| Former variable | Replacement |
|---|---|
| `thanos_component: 'store'` | Removed, the role `monitoring_thanos_store` |
| `thanos_version`, `thanos_home`, `thanos_ip`, `thanos_ipv6`, `thanos_network`, `thanos_hostname`, `thanos_timezone`, `thanos_labels` | `thanos_store_version`, `thanos_store_home`, `thanos_store_ip`, `thanos_store_ipv6`, `thanos_store_network`, `thanos_store_hostname`, `thanos_store_timezone`, `thanos_store_labels` |
| `thanos_objstore` | `thanos_store_objstore` |
| `thanos_container` | `thanos_store_container` |
| `thanos_autoupdate_enabled`, `thanos_autoupdate_schedule` | `thanos_store_autoupdate_enabled`, `thanos_store_autoupdate_schedule` |
| `thanos_instances`, `tasks/loop.yml` | Removed, the role runs once per host |

Changed behavior:

- `/etc/localtime` and `/etc/timezone` are no longer mounted, the time zone is set with `thanos_store_timezone` and `TZ`,
  the quadlet unit changes once and store restarts, volumes in `thanos_store_container` should no longer contain them
- `thanos_store_environment` sets the environment, it is checked against the allowed variables
- the role waits until store is ready and shows the journal if the start fails
- the container, the secret and the data directory keep their names `thanos-store`, `thanos-store-objstore` and `<home>/data`

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root. The VMs need access to Docker Hub.

| Platform | Test case |
|---|---|
| `molecule-thanos-store-default` | Only the mandatory variables with the object storage `FILESYSTEM`, the volume of the bucket is added with `thanos_store_container.volumes` |
| `molecule-thanos-store` | IPv6 and labels |

`prepare` creates the podman network, pulls the image and creates the directories of the bucket.
`side_effect` runs the role with `thanos_store_container` not a dictionary, an object storage without `type`, missing and not a dictionary,
a line break in the environment and an unknown environment variable
and checks that it fails with the expected message and the quadlet unit is unchanged (tasks marked `expect ERROR`),
then it changes the object storage on `molecule-thanos-store`, the secret changes and store has to restart.
`verify` checks the quadlet unit without the mounts of the time zone, the service, the environment, the secret,
the data directory owned by `nobody`, that store is ready and that it listed the empty bucket and serves no blocks.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd monitoring_thanos_store
MOLECULE_TART_IMAGE='debian' molecule test
```
