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

### Object storage

`thanos_receive_objstore` is the content of [bucket.yml](https://thanos.io/tip/thanos/storage.md/) as dictionary, with it receive uploads its blocks.
The name stays `objstore` instead of `config`, it is the configuration of the object storage, not of receive, the flags are part of the command.
The role writes it to `<home>/bucket.yml` and mounts the file read-only to `/etc/thanos/bucket.yml`, the command gets `--objstore.config-file`.
Without `thanos_receive_objstore` the role removes bucket.yml, receive uploads no blocks and only keeps the samples in its TSDB.
The keys of the first level are `type`, `config` and `prefix`, `type` is one of the providers of github.com/thanos-io/objstore
(`FILESYSTEM`, `GCS`, `S3`, `AZURE`, `SWIFT`, `COS`, `ALIYUNOSS`, `BOS`, `OCI`, `OBS`),
the allow lists are generated from `client/factory.go` and `objstore.go` of the version of Thanos v0.42.5 and prevent unexpected behavior by accident.

```yaml
thanos_receive_objstore:
  type: 'S3'
  config:
    bucket: 'thanos'
    endpoint: 's3.example.org'
    access_key: 'thanos'
thanos_receive_secrets:
  - name: 'thanos_receive_s3_secret_key'
    data: "{{ vault_thanos_secret_key }}"
    target: 'config.secret_key'
```

### Secrets

The providers read their credentials (e.g. `secret_key` of S3) only from bucket.yml, they cannot read them from files,
but Thanos replaces `$(VARIABLE)` in bucket.yml with the environment (`extflag.WithEnvSubstitution` of `--objstore.config-file`).
The secrets are entries of `thanos_receive_secrets` with `name`, `data` and `target`, the role creates them with `podman secret`
and passes them with `type=env` as `THANOS_SECRET_<TARGET>` (the target in upper case, dots replaced by `_`).
The target is the path of the option in `thanos_receive_objstore`, the role writes the reference `"$(THANOS_SECRET_CONFIG_SECRET_KEY)"` there,
so bucket.yml and the quadlet unit contain no credentials.

- The last key of a target is one of the options carrying secrets (`monitoring_thanos_receive__objstore_secret_keys`, e.g. `secret_key`, `session_token`,
  `service_account`, `storage_account_key`, `password`), these options must not be set in `thanos_receive_objstore`, `null` or an empty string are allowed.
- A target must not be set in `thanos_receive_objstore`, its path leads through dictionaries and every target is set once, secrets need an object storage.
- The data of a secret is a string without line breaks, `"` and `\`, the reference is double-quoted in bucket.yml,
  a key or service account file has to be a single line (e.g. the JSON of `service_account`).

A changed secret restarts the running receive.

### Allowed variables

Thanos reads no environment variables besides the references in bucket.yml, the role only allows `TZ` in `thanos_receive_environment`.
`thanos_receive_environment` has no default, without it the container has no environment, the time zone is set by podman with `thanos_receive_timezone`.
This prevents unexpected behavior by accident, e.g. by a variable meant for another image, the secrets are set with `thanos_receive_secrets`.
The check uses the environment of the container after merging `thanos_receive_container`.

### Container

Ports, volumes, flags and dependencies (`requires`, `wants`, `after`, `part_of`, `binds_to`, `requires_mounts_for`) are changed with `thanos_receive_container`, it is merged over the default of the container.
The merge is not recursive, `publish`, `volumes` and `command` replace the values of the default completely.
The default mounts `<home>/data` to `/var/thanos/receive` and with object storage `<home>/bucket.yml` to `/etc/thanos/bucket.yml`,
the command has `--tsdb.path`, `--label` and with object storage `--objstore.config-file`.
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

The role checks before any change, the messages name only the failing checks:

- `Render the configuration` evaluates the variables once, `thanos_receive_container` that is no dictionary or a failing template
  (e.g. an unknown filter) stop the role there
- `thanos_receive_secrets` is a list of entries with `name`, `data` and `target` with unique names
- `thanos_receive_objstore` is a dictionary, if it is set with the allowed keys, a known `type`, `config` is a dictionary, the options carrying secrets are not set
- the targets of the secrets are known, unique, not set in `thanos_receive_objstore` and lead through dictionaries, the data are valid,
  secrets need an object storage
- `thanos_receive_environment` is a dictionary without line breaks, only `TZ` is set in the environment of the container

### Check mode

The role runs with `--check`, also on a host where it never ran, and reports the changes of bucket.yml and the quadlet unit,
receive is neither started nor restarted.

### Restart and updates

Receive is restarted if it was running and bucket.yml (written or removed), a secret or the quadlet unit changed, otherwise it is started and enabled.
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
| `thanos_objstore` | `thanos_receive_objstore` without the credentials, they are entries of `thanos_receive_secrets` with the path of the option as `target` |
| `thanos_container` | `thanos_receive_container` |
| `thanos_autoupdate_enabled`, `thanos_autoupdate_schedule` | `thanos_receive_autoupdate_enabled`, `thanos_receive_autoupdate_schedule` |
| `thanos_instances`, `tasks/loop.yml` | Removed, the role runs once per host |

Changed behavior:

- bucket.yml is no longer the podman secret `thanos-receive-objstore` but the file `<home>/bucket.yml` without credentials,
  the credentials are `thanos_receive_secrets` passed in the environment, the former secret is removed with `podman secret rm thanos-receive-objstore`
- `/etc/localtime` and `/etc/timezone` are no longer mounted and `TZ` has no default, the time zone is set by podman with `thanos_receive_timezone`,
  the quadlet unit changes once and receive restarts, volumes in `thanos_receive_container` should no longer contain them
- `thanos_receive_environment` has no default and is checked against the allowed variables, unknown keys, types and plain credentials of the object storage stop the role
- the quadlet unit has the dependencies `Wants`, `After`, `PartOf`, `BindsTo` and `RequiresMountsFor` of `thanos_receive_container` besides `Requires`
- the role waits until receive is ready and shows the journal if the start fails
- the container and the data directory keep their names `thanos-receive` and `<home>/data`

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root. The VMs need access to Docker Hub.

| Platform | Test case |
|---|---|
| `molecule-thanos-receive-default` | Only the mandatory variables, receive keeps the samples without object storage |
| `molecule-thanos-receive` | IPv6, labels and the object storage `S3` on an S3 server of rclone, the secret key is an entry of `thanos_receive_secrets` |

`prepare` creates the podman network, pulls the images, starts the S3 server (`rclone serve s3`) with the bucket `thanos`
and runs Prometheus with `monitoring_prometheus`, it sends its samples with remote write to receive.
`check` runs `converge` with `--check` on the new VMs.
`side_effect` runs the role with invalid variables (tasks marked `expect ERROR`, the quadlet unit and bucket.yml stay unchanged):
`thanos_receive_container` and `thanos_receive_objstore` no dictionaries, an unknown type and key of the object storage, a secret key in the object storage,
a secret without target, an unknown target, a target set in the object storage, a quote in a secret, secrets without object storage,
`thanos_receive_environment` no dictionary, a line break in the environment of the container and an unknown environment variable.
Afterwards it changes the prefix of the object storage on `molecule-thanos-receive`, bucket.yml changes and receive has to restart,
and runs the role again on `molecule-thanos-receive-default`, receive must not restart.
`verify` checks the quadlet unit (secrets, time zone, no `TZ`, volume and flag of bucket.yml only with object storage), the service without automatic restarts,
bucket.yml with the reference of the secret and without the secret key or no bucket.yml without object storage,
the external label in the command of the container, the data directory owned by `nobody`, that receive is ready
and that the TSDB of the tenant `default-tenant` received samples of Prometheus.
Receive uploads a block only after two hours, the upload with the secret key is tested by `monitoring_thanos_compact`.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd monitoring_thanos_receive
MOLECULE_TART_IMAGE='debian' molecule test
```
