Diun runs in the official container image [crazymax/diun](https://crazymax.dev/diun/) as podman quadlet.
It is configured with `diun_config`, the role writes it to `<diun_home>/diun.yml` and mounts it read-only to `/etc/diun/diun.yml`,
the file Diun reads by default. The data (`diun.db`) is in `<diun_home>/data`.

### Configuration

`diun_config` contains the options of the [configuration](https://crazymax.dev/diun/config/) as in `diun.yml`,
it is merged recursively over the default of the role, lists (e.g. `regopts` or `notifyOn`) replace the lists of the default.
`null` removes an option of the default.

```yaml
diun_config:
  watch:
    schedule: '0 */12 * * *'
  notif:
    mail:
      host: 'mail.example.org'
      port: 465
      ssl: true
      from: 'diun@example.org'
      to: [ 'admin@example.org' ]
  regopts:
    - name: 'ghcr'
      selector: 'image'
      timeout: '20s'
  defaults:
    metadata:
      team: 'operations'
```

The default of the role:

```yaml
watch:
  workers: 10
  schedule: '0 */6 * * *'
  jitter: '30s'
  firstCheckNotif: false
  runOnStartup: true
  compareDigest: false
defaults:
  watchRepo: false
  notifyOn: [ 'new', 'update' ]
  maxTags: 10
  sortTags: 'reverse'
```

The image sets the path of the database with `DIUN_DB_PATH=/data/diun.db`.

### Secrets

`diun_secrets` is a list of podman secrets with `name`, `data` and `target`, the target is the path of the option in `diun.yml`,
e.g. `notif.mail.password`. The role creates the secret, mounts it to `/run/secrets/<name>` and writes the file option of the target
(e.g. `passwordFile: /run/secrets/<name>`) to `diun.yml`, Diun reads the file at the start.
Passwords are neither part of `diun.yml`, nor of the quadlet unit or the environment of the container.

The targets are the keys of `monitoring_diun__secrets_allowed`, every option with a file option in diun v4.33.1, e.g. `notif.mail.username`,
`notif.mail.password`, `notif.telegram.token`, `notif.telegram.chatIDs`, `metrics.token`, `watch.healthchecks.uuid` and `providers.kubernetes.token`.
The credentials of a registry are `regopts.<name>.username` and `regopts.<name>.password`, the entry with this name has to be part of `diun_config.regopts`.
Neither a target nor its file option may be set in `diun_config`, every target is set once.

```yaml
diun_secrets:
  - name: 'diun_mail_password'
    data: "{{ vault_diun_mail_password }}"
    target: 'notif.mail.password'
  - name: 'diun_ghcr_password'
    data: "{{ vault_diun_ghcr_password }}"
    target: 'regopts.ghcr.password'
```

`providers.nomad.secretID` has no file option in Diun, it is set in `diun_config` like before in the environment.

### Containers of the host

With `diun_provider_podman: true` (default) Diun watches the containers of the host with the docker provider through the podman socket:
the role mounts `/run/podman/podman.sock` read-only as `/var/run/docker.sock` and adds `providers.docker` with `endpoint: unix:///var/run/docker.sock`,
`watchByDefault: false` and `watchStopped: false` to the default.
The podman socket must be enabled, e.g. with `podman_socket_enabled: true` of `container_podman`.
Containers are watched if they have the label `diun.enable=true`, set `providers.docker.watchByDefault: true` in `diun_config` to watch all containers.

With `diun_provider_podman: false` the role sets no provider, configure e.g. the file provider with `diun_config` and the volumes with `diun_container.volumes`.

### Allowed variables

The role only allows the options of `monitoring_diun__config_schema`, the secrets with a target in `monitoring_diun__secrets_allowed`
and the environment variables in `monitoring_diun__environment_allowed`, it stops before any change if unknown options, secrets or variables are set.
This prevents unexpected behavior by accident, e.g. by a typo or an option that has to be passed as secret.
The schema is generated from `internal/config/config.go` and `internal/model` of diun v4.33.1 with the types of the options:
booleans, numbers, strings (also durations), lists, maps with free keys (`defaults.metadata`, `notif.webhook.headers`, `notif.signalrest.headers`)
and the entries of `regopts`.

`diun_environment` has no default and only takes the variables of the command line and the image (`TZ`, `LOG_LEVEL`, `LOG_JSON`, `LOG_CALLER`,
`LOG_NOCOLOR`, `PROFILER`, `PROFILER_PATH`, `GRPC_AUTHORITY`), without it the quadlet unit has no environment and nothing is checked.
The options of Diun are not set with `DIUN_*`, the role reports such variables with their option.
The check of the environment uses the environment of the container after merging `diun_container`.

### Container

Ports, volumes, additional hosts (`etc_hosts`) and dependencies are changed with `diun_container`, it is merged over the default of the container.
The merge is not recursive, `publish` and `volumes` replace the values of the default completely,
`diun_container.environment` replaces the environment including `diun_environment`.
The dependencies of the quadlet unit are lists of units in `diun_container`: `requires`, `wants`, `after`, `part_of` and `binds_to`
are written as `Requires=`, `Wants=`, `After=`, `PartOf=` and `BindsTo=` to `[Unit]`.

```yaml
diun_container:
  wants: [ 'mail.service' ]
  after: [ 'mail.service' ]
```

### Validation

The role checks before any change:

- `diun_secrets` is a list of entries with `name`, `data` and `target` and unique names, every target is a known secret and set once,
  the secrets of a registry have their entry in `regopts`, no secret contains a line break
- `diun_config` contains known options with the types of the schema, the entries of `regopts` have a unique `name`,
  no secret or file option of a secret, no line breaks
- `diun_environment`, if set, contains no option of Diun (`DIUN_*`) and no line breaks, only allowed environment variables are set in the container
- `diun_keys` is not set anymore

If `diun_container` or `diun_config` is no dictionary, merging it with the default fails before anything changes. Diun checks the values of the options at the start.

### Restart and updates

Diun is restarted if it was running and `diun.yml`, a secret or the quadlet unit changed, otherwise it is started and enabled.
If the start fails, the role shows the journal of the service.
Afterwards the role waits until Diun reports the loaded `diun.yml` and shows the journal otherwise.
Updates of the image are done by `container_update` with `diun_autoupdate_enabled: true` and `diun_autoupdate_schedule`, without `diun_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

The former version of the role configured Diun with `DIUN_<PATH>` in `diun_environment`, it is `diun_config` now:
the variable `DIUN_<PATH>` is the option `<path>` in `diun.yml`, e.g. `DIUN_WATCH_SCHEDULE` is `watch.schedule`,
`DIUN_NOTIF_MAIL_HOST` is `host` in `notif.mail`. Values are no strings anymore, e.g. `ssl: false` and `port: 1025`,
comma separated lists are lists, e.g. `notifyOn: [ 'new', 'update' ]`. The role rejects `DIUN_*` in `diun_environment` and names the option of every variable.

| Former variable | Replacement |
|---|---|
| `diun_environment` with `DIUN_<PATH>` | `diun_config` |
| `diun_keys` and `DIUN_REGOPTS_<KEY>_<OPTION>` | entries of `diun_config.regopts` with `name` |
| `diun_keys` and `DIUN_DEFAULTS_METADATA_<KEY>`, `DIUN_NOTIF_WEBHOOK_HEADERS_<KEY>`, `DIUN_NOTIF_SIGNALREST_HEADERS_<KEY>` | the maps `defaults.metadata`, `notif.webhook.headers`, `notif.signalrest.headers` |
| `diun_keys` and `DIUN_NOTIF_SIGNALREST_RECIPIENTS_<KEY>` | the list `notif.signalrest.recipients` |
| target `DIUN_<PATH>` of `diun_secrets`, e.g. `DIUN_NOTIF_MAIL_PASSWORD` | target `<path>`, e.g. `notif.mail.password` |
| target `DIUN_REGOPTS_<KEY>_USERNAME`, `DIUN_REGOPTS_<KEY>_PASSWORD` | target `regopts.<name>.username`, `regopts.<name>.password` |

Changed behavior:

- the role generates `<diun_home>/diun.yml` again and mounts it read-only, it contains the files of the secrets, not the secrets
- the file of the earliest versions, `<diun_home>/etc/diun.yml`, is still removed
- the quadlet unit has no environment without `diun_environment`, the defaults of the role are part of `diun.yml`
- Diun is restarted if `diun.yml` changed, the role waits until Diun reports the loaded `diun.yml` and shows the journal if it fails

Earlier versions of the role used single variables:

| Before | Now |
|---|---|
| `diun_net` | `diun_network` |
| `diun_workers`, `diun_schedule`, `diun_jitter`, `diun_first_check_notif`, `diun_run_on_startup`, `diun_compare_digest` | `workers`, `schedule`, `jitter`, `firstCheckNotif`, `runOnStartup`, `compareDigest` in `watch` |
| `diun_healthchecks` | `watch.healthchecks.baseURL`, secret with target `watch.healthchecks.uuid` |
| `diun_watch_repo`, `diun_notify_on`, `diun_max_tags`, `diun_sort_tags`, `diun_include_tags`, `diun_exclude_tags`, `diun_metadata` | `watchRepo`, `notifyOn`, `maxTags`, `sortTags`, `includeTags`, `excludeTags`, `metadata` in `defaults` |
| `diun_notify_mail` and `diun_mail_*` | `notif.mail`, secrets with the targets `notif.mail.username` and `notif.mail.password` |
| `diun_provider_docker` and `diun_docker_*` | `diun_provider_podman` or `providers.docker` |
| `podman___update_mode` | `diun_autoupdate_enabled` |
| `diun_publish`, `diun_volumes` | `diun_container.publish`, `diun_container.volumes`, the volumes of the default have to be repeated |

### Tests

The molecule scenario `default` uses tart with one VM `molecule-diun`.
`prepare` enables the podman socket, starts [mailpit](https://mailpit.axllent.org) and a container with the label `diun.enable=true`.
`side_effect` runs the role with `diun_container` and `diun_config` not a dictionary, a secret without target, unknown options and an option of the wrong type,
the password and its file option in `diun_config`, options of Diun in `diun_environment`, `diun_keys`, an unknown environment variable in `diun_container.environment`,
an unknown secret and the secret of a registry without entry in `regopts`
and checks that it fails with the expected message and the quadlet unit and `diun.yml` are unchanged (tasks marked `expect ERROR`),
then it changes `watch.workers`, `diun.yml` changes and Diun has to restart.
`verify` checks the quadlet unit with the mounted secrets and `diun.yml` without environment and passwords, `diun.yml` with the files of the secrets,
that the files contain the secrets, Diun loaded `diun.yml` and no option is set in the environment,
that the docker provider found the labeled container through the podman socket, the database in `data`,
and sends a test notification with `diun notif test`, which must arrive at mailpit.

```shell
cd monitoring_diun
MOLECULE_TART_IMAGE='debian' molecule test
```
