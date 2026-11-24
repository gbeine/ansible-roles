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
thanos_compact_secrets:
  - name: 'thanos_compact_s3_secret_key'
    data: "{{ vault_thanos_secret_key }}"
    target: 'config.secret_key'
```

`thanos_compact_objstore` is mandatory, it is the content of [bucket.yml](https://thanos.io/tip/thanos/storage.md/) as dictionary.
The name stays `objstore` instead of `config`, it is the configuration of the object storage, not of compact, the flags are part of the command.
The role writes it to `<home>/bucket.yml` and mounts the file read-only to `/etc/thanos/bucket.yml`, the command has `--objstore.config-file`.
The keys of the first level are `type`, `config` and `prefix`, `type` is one of the providers of github.com/thanos-io/objstore
(`FILESYSTEM`, `GCS`, `S3`, `AZURE`, `SWIFT`, `COS`, `ALIYUNOSS`, `BOS`, `OCI`, `OBS`),
the allow lists are generated from `client/factory.go` and `objstore.go` of the version of Thanos v0.42.5 and prevent unexpected behavior by accident.

### Secrets

The providers read their credentials (e.g. `secret_key` of S3) only from bucket.yml, they cannot read them from files,
but Thanos replaces `$(VARIABLE)` in bucket.yml with the environment (`extflag.WithEnvSubstitution` of `--objstore.config-file`).
The secrets are entries of `thanos_compact_secrets` with `name`, `data` and `target`, the role creates them with `podman secret`
and passes them with `type=env` as `THANOS_SECRET_<TARGET>` (the target in upper case, dots replaced by `_`).
The target is the path of the option in `thanos_compact_objstore`, the role writes the reference `"$(THANOS_SECRET_CONFIG_SECRET_KEY)"` there,
so bucket.yml and the quadlet unit contain no credentials.

- The last key of a target is one of the options carrying secrets (`monitoring_thanos_compact__objstore_secret_keys`, e.g. `secret_key`, `session_token`,
  `service_account`, `storage_account_key`, `password`), these options must not be set in `thanos_compact_objstore`, `null` or an empty string are allowed.
- A target must not be set in `thanos_compact_objstore`, its path leads through dictionaries and every target is set once.
- The data of a secret is a string without line breaks, `"` and `\`, the reference is double-quoted in bucket.yml,
  a key or service account file has to be a single line (e.g. the JSON of `service_account`).

A changed secret restarts the running compact.

### Allowed variables

Thanos reads no environment variables besides the references in bucket.yml, the role only allows `TZ` in `thanos_compact_environment`.
`thanos_compact_environment` has no default, without it the container has no environment, the time zone is set by podman with `thanos_compact_timezone`.
This prevents unexpected behavior by accident, e.g. by a variable meant for another image, the secrets are set with `thanos_compact_secrets`.
The check uses the environment of the container after merging `thanos_compact_container`.

### Container

Ports, volumes, flags and dependencies (`requires`, `wants`, `after`, `part_of`, `binds_to`, `requires_mounts_for`) are changed with `thanos_compact_container`, it is merged over the default of the container.
The merge is not recursive, `publish`, `volumes` and `command` replace the values of the default completely.
The default mounts `<home>/data` to `/var/thanos/compact` and `<home>/bucket.yml` to `/etc/thanos/bucket.yml`, the command has `--wait`, `--data-dir` and `--objstore.config-file`.
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

The role checks before any change, the messages name only the failing checks:

- `Render the configuration` evaluates the variables once, a missing `thanos_compact_objstore`, `thanos_compact_container` that is no dictionary
  or a failing template (e.g. an unknown filter) stop the role there
- `thanos_compact_secrets` is a list of entries with `name`, `data` and `target` with unique names
- `thanos_compact_objstore` is a dictionary with the allowed keys, a known `type`, `config` is a dictionary, the options carrying secrets are not set
- the targets of the secrets are known, unique, not set in `thanos_compact_objstore` and lead through dictionaries, the data are valid
- `thanos_compact_environment` is a dictionary without line breaks, only `TZ` is set in the environment of the container

### Check mode

The role runs with `--check`, also on a host where it never ran, and reports the changes of bucket.yml and the quadlet unit,
compact is neither started nor restarted.

### Restart and updates

Compact is restarted if it was running and bucket.yml, a secret or the quadlet unit changed, otherwise it is started and enabled.
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
| `thanos_objstore` | `thanos_compact_objstore` without the credentials, they are entries of `thanos_compact_secrets` with the path of the option as `target` |
| `thanos_container` | `thanos_compact_container` |
| `thanos_autoupdate_enabled`, `thanos_autoupdate_schedule` | `thanos_compact_autoupdate_enabled`, `thanos_compact_autoupdate_schedule` |
| `thanos_instances`, `tasks/loop.yml` | Removed, the role runs once per host |

Example of the object storage:

```yaml
# before
thanos_compact_objstore:
  type: 'S3'
  config:
    bucket: 'thanos'
    endpoint: 's3.example.org'
    access_key: 'thanos'
    secret_key: "{{ vault_thanos_secret_key }}"

# now
thanos_compact_objstore:
  type: 'S3'
  config:
    bucket: 'thanos'
    endpoint: 's3.example.org'
    access_key: 'thanos'
thanos_compact_secrets:
  - name: 'thanos_compact_s3_secret_key'
    data: "{{ vault_thanos_secret_key }}"
    target: 'config.secret_key'
```

Changed behavior:

- bucket.yml is no longer the podman secret `thanos-compact-objstore` but the file `<home>/bucket.yml` without credentials,
  the credentials are `thanos_compact_secrets` passed in the environment, the former secret is removed with `podman secret rm thanos-compact-objstore`
- `/etc/localtime` and `/etc/timezone` are no longer mounted and `TZ` has no default, the time zone is set by podman with `thanos_compact_timezone`,
  the quadlet unit changes once and compact restarts, volumes in `thanos_compact_container` should no longer contain them
- `thanos_compact_environment` has no default and is checked against the allowed variables, unknown keys, types and plain credentials of the object storage stop the role
- the quadlet unit has the dependencies `Wants`, `After`, `PartOf`, `BindsTo` and `RequiresMountsFor` of `thanos_compact_container` besides `Requires`
- the role waits until compact is ready and shows the journal if the start fails
- the container and the data directory keep their names `thanos-compact` and `<home>/data`

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root. The VMs need access to Docker Hub.

| Platform | Test case |
|---|---|
| `molecule-thanos-compact-default` | Only the mandatory variables with the object storage `FILESYSTEM`, the volume of the bucket is added with `thanos_compact_container.volumes` |
| `molecule-thanos-compact` | IPv6, labels and the object storage `S3` on an S3 server of rclone, the secret key is an entry of `thanos_compact_secrets` |

`prepare` creates the podman network, pulls the images, creates the directory of the bucket and starts the S3 server (`rclone serve s3`) with the bucket `thanos`.
`check` runs `converge` with `--check` on the new VMs.
`side_effect` runs the role with invalid variables (tasks marked `expect ERROR`, the quadlet unit and bucket.yml stay unchanged):
`thanos_compact_container` and `thanos_compact_objstore` no dictionaries, an unknown type and key of the object storage, a secret key in the object storage,
a secret without target, an unknown target, a target set in the object storage, a quote in a secret, `thanos_compact_environment` no dictionary,
a line break in the environment of the container and an unknown environment variable.
Afterwards it changes the prefix of the object storage on `molecule-thanos-compact`, bucket.yml changes and compact has to restart,
and runs the role again on `molecule-thanos-compact-default`, compact must not restart.
`verify` checks the quadlet unit (secrets, time zone, no `TZ`, no mounts of the time zone), the service without automatic restarts,
bucket.yml with the reference of the secret and without the secret key, the data directory owned by `nobody`,
that compact is ready and that it finished a run over the bucket, on S3 with the secret key of the environment.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd monitoring_thanos_compact
MOLECULE_TART_IMAGE='debian' molecule test
```
