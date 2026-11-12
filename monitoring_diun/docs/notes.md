Diun runs in the official container image [crazymax/diun](https://crazymax.dev/diun/) as podman quadlet.
It is configured with environment variables only, every option of the [configuration](https://crazymax.dev/diun/config/) is available as `DIUN_<PATH>`,
e.g. `watch.schedule` as `DIUN_WATCH_SCHEDULE` or `notif.mail.host` as `DIUN_NOTIF_MAIL_HOST`.
The data (`diun.db`) is in `<diun_home>/data`.

### Environment and secrets

All variables are set with `diun_environment`, which is merged over the defaults of the role.
Options carrying secrets are passed as podman secrets with `diun_secrets` with `name`, `data` and `target`, the usual name of the option, e.g. `DIUN_NOTIF_MAIL_PASSWORD`.
The role creates the secret with `podman secret create`, mounts it to `/run/secrets/<name>` and sets the file option of diun, e.g. `DIUN_NOTIF_MAIL_PASSWORDFILE`,
so the secret is neither part of the quadlet unit nor of the environment of the container.
Every option of diun with a file variant (`passwordFile`, `tokenFile`, `webhookURLFile`, `usernameFile`, …) can be a secret, see `monitoring_diun__secret_files`,
the passwords and usernames of the registries as well, e.g. `DIUN_REGOPTS_GHCR_PASSWORD` with `DIUN_REGOPTS_GHCR_PASSWORDFILE` (see Options with keys).
Passwords, tokens and webhook URLs must be secrets, usernames, recipients and chat IDs can be set in `diun_environment` as well.
diun uses the file as it is, `data` must not end with a line break.
Options without file variant, e.g. `DIUN_NOTIF_WEBHOOK_HEADERS_<KEY>` or `DIUN_PROVIDERS_NOMAD_SECRETID`, can only be set in `diun_environment`.

```yaml
diun_environment:
  DIUN_WATCH_SCHEDULE: '0 */6 * * *'
  DIUN_NOTIF_MAIL_HOST: 'smtp.example.org'
  DIUN_NOTIF_MAIL_PORT: '587'
  DIUN_NOTIF_MAIL_USERNAME: 'diun'
  DIUN_NOTIF_MAIL_FROM: 'diun@example.org'
  DIUN_NOTIF_MAIL_TO: 'admin@example.org'
  DIUN_NOTIF_GOTIFY_ENDPOINT: 'https://gotify.example.org'
diun_secrets:
  - name: 'diun_mail_password'
    data: "{{ vault_diun_mail_password }}"
    target: 'DIUN_NOTIF_MAIL_PASSWORD'
  - name: 'diun_gotify_token'
    data: "{{ vault_diun_gotify_token }}"
    target: 'DIUN_NOTIF_GOTIFY_TOKEN'
```

The role sets these defaults, they keep the behaviour of earlier versions of the role:

| Variable | Default of the role |
|---|---|
| `TZ` | `diun_timezone` |
| `DIUN_DB_PATH` | `/data/diun.db` |
| `DIUN_WATCH_WORKERS` | `10` |
| `DIUN_WATCH_SCHEDULE` | `0 */6 * * *` |
| `DIUN_WATCH_JITTER` | `30s` |
| `DIUN_WATCH_FIRSTCHECKNOTIF` | `false` |
| `DIUN_WATCH_RUNONSTARTUP` | `true` |
| `DIUN_WATCH_COMPAREDIGEST` | `false` |
| `DIUN_DEFAULTS_WATCHREPO` | `false` |
| `DIUN_DEFAULTS_NOTIFYON` | `new,update` |
| `DIUN_DEFAULTS_MAXTAGS` | `10` |
| `DIUN_DEFAULTS_SORTTAGS` | `reverse` |

### Options with keys

Some options of diun contain a key in their name, e.g. the registry `GHCR` in `DIUN_REGOPTS_GHCR_NAME` or the metadata `TEAM` in `DIUN_DEFAULTS_METADATA_TEAM`.
The keys are declared in `diun_keys`, the role generates the exact names of the options from them:

| Entry of `diun_keys` | Generated options |
|---|---|
| `regopts` | `DIUN_REGOPTS_<KEY>_NAME`, `_SELECTOR`, `_USERNAME`, `_TIMEOUT`, `_INSECURETLS`, the secrets `DIUN_REGOPTS_<KEY>_USERNAME` and `DIUN_REGOPTS_<KEY>_PASSWORD` with the file variables `_USERNAMEFILE` and `_PASSWORDFILE` |
| `notif_webhook_headers` | `DIUN_NOTIF_WEBHOOK_HEADERS_<KEY>` |
| `notif_signalrest_recipients` | `DIUN_NOTIF_SIGNALREST_RECIPIENTS_<KEY>` |
| `notif_signalrest_headers` | `DIUN_NOTIF_SIGNALREST_HEADERS_<KEY>` |
| `defaults_metadata` | `DIUN_DEFAULTS_METADATA_<KEY>` |

Keys consist of uppercase letters, digits and `_`, the keys of `regopts` of uppercase letters and digits.
Options with a key that is not declared in `diun_keys` are unknown and stop the role.

```yaml
diun_keys:
  regopts: [ 'GHCR' ]
  notif_webhook_headers: [ 'AUTHORIZATION' ]
diun_environment:
  DIUN_REGOPTS_GHCR_NAME: 'ghcr.io'
  DIUN_NOTIF_WEBHOOK_ENDPOINT: 'https://hooks.example.org/diun'
  DIUN_NOTIF_WEBHOOK_HEADERS_AUTHORIZATION: 'Bearer token'
diun_secrets:
  - name: 'diun_ghcr_password'
    data: "{{ vault_diun_ghcr_password }}"
    target: 'DIUN_REGOPTS_GHCR_PASSWORD'
```

### Containers of the host

With `diun_provider_podman: true` (default) Diun watches the containers of the host with the docker provider through the podman socket:
the role mounts `/run/podman/podman.sock` read-only as `/var/run/docker.sock` and sets `DIUN_PROVIDERS_DOCKER=true`,
`DIUN_PROVIDERS_DOCKER_ENDPOINT=unix:///var/run/docker.sock`, `DIUN_PROVIDERS_DOCKER_WATCHBYDEFAULT=false` and `DIUN_PROVIDERS_DOCKER_WATCHSTOPPED=false`.
The podman socket must be enabled, e.g. with `podman_socket_enabled: true` of `container_podman`.
Containers are watched if they have the label `diun.enable=true`, set `DIUN_PROVIDERS_DOCKER_WATCHBYDEFAULT: 'true'` in `diun_environment` to watch all containers.

With `diun_provider_podman: false` the role sets no provider, configure e.g. the file provider with `diun_environment` and the volumes with `diun_container.volumes`.

### Allowed variables

The role only allows the environment variables in `monitoring_diun__environment_allowed` and the secrets with a target in `monitoring_diun__secret_files`,
it stops before any change if unknown variables or secrets are set.
This prevents unexpected behavior by accident, e.g. by a typo or a variable that has to be passed as secret.
The check uses the environment and the secrets of the container after merging `diun_container`,
so variables set with `diun_container.environment` are checked as well.
The allowed variables are the options of diun v4.33.1 from its documentation without the passwords, tokens and webhook URLs,
and the file variables of the secrets. The role sets the file variables from `diun_secrets`, they must not be set in `diun_environment`.
All names are exact, the options with keys are generated from `diun_keys` (see Options with keys).

### Container

Ports, volumes and additional hosts (`etc_hosts`) are changed with `diun_container`, it is merged over the default of the container.
The merge is not recursive, `publish` and `volumes` replace the values of the default completely,
`diun_container.environment` replaces the environment including `diun_environment`, use `diun_environment` instead.

### Validation

The role checks before any change that `diun_keys` is a dictionary with the entries of the table above, each a list of valid and unique keys,
that `diun_secrets` is a list of entries with `name`, `data` and `target` and unique names,
that neither a secret nor its file variable is set in `diun_environment` and that only allowed variables and secrets are used.
If `diun_container` is no dictionary, merging it with the default fails before anything changes.

### Restart and updates

Diun is restarted if it was running and a secret or the quadlet unit changed, e.g. by a changed environment variable.
Updates of the image are done by `container_update` with `diun_autoupdate_enabled: true` and `diun_autoupdate_schedule`, without `diun_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

Earlier versions of the role generated `<diun_home>/etc/diun.yml`, the role removes this file, `<diun_home>/etc` is not mounted anymore.

| Before | Now |
|---|---|
| `diun_net` | `diun_network` |
| `diun_workers`, `diun_schedule`, `diun_jitter`, `diun_first_check_notif`, `diun_run_on_startup`, `diun_compare_digest` | `DIUN_WATCH_WORKERS`, `DIUN_WATCH_SCHEDULE`, `DIUN_WATCH_JITTER`, `DIUN_WATCH_FIRSTCHECKNOTIF`, `DIUN_WATCH_RUNONSTARTUP`, `DIUN_WATCH_COMPAREDIGEST` |
| `diun_healthchecks` | `DIUN_WATCH_HEALTHCHECKS_BASEURL`, `DIUN_WATCH_HEALTHCHECKS_UUID` |
| `diun_watch_repo`, `diun_notify_on`, `diun_max_tags`, `diun_sort_tags`, `diun_include_tags`, `diun_exclude_tags`, `diun_metadata` | `DIUN_DEFAULTS_WATCHREPO`, `DIUN_DEFAULTS_NOTIFYON` (comma separated), `DIUN_DEFAULTS_MAXTAGS`, `DIUN_DEFAULTS_SORTTAGS`, `DIUN_DEFAULTS_INCLUDETAGS`, `DIUN_DEFAULTS_EXCLUDETAGS`, `DIUN_DEFAULTS_METADATA_<KEY>` |
| `diun_notify_mail` and `diun_mail_host`, `diun_mail_port`, `diun_mail_ssl`, `diun_mail_insecure_skip_verify`, `diun_mail_local_name`, `diun_mail_username`, `diun_mail_from`, `diun_mail_to`, `diun_mail_template_title`, `diun_mail_template_body` | `DIUN_NOTIF_MAIL_HOST`, `DIUN_NOTIF_MAIL_PORT`, `DIUN_NOTIF_MAIL_SSL`, `DIUN_NOTIF_MAIL_INSECURESKIPVERIFY`, `DIUN_NOTIF_MAIL_LOCALNAME`, `DIUN_NOTIF_MAIL_USERNAME`, `DIUN_NOTIF_MAIL_FROM`, `DIUN_NOTIF_MAIL_TO`, `DIUN_NOTIF_MAIL_TEMPLATETITLE`, `DIUN_NOTIF_MAIL_TEMPLATEBODY` |
| `diun_mail_password`, `diun_mail_password_file` | `diun_secrets` with target `DIUN_NOTIF_MAIL_PASSWORD` |
| `diun_provider_docker` and `diun_docker_*` | `diun_provider_podman` or `DIUN_PROVIDERS_DOCKER_*` |
| `podman___update_mode` | `diun_autoupdate_enabled` |
| `diun_publish`, `diun_volumes` | `diun_container.publish`, `diun_container.volumes`, the volumes of the default have to be repeated |
| secrets as environment variable `target` | secrets mounted as file and the file option, `diun_secrets` stays the same |
| `diun_environment` checked for `PASSWORD`, `TOKEN`, `SECRET` and `WEBHOOKURL` | allowed variables |
| options with keys, e.g. `DIUN_REGOPTS_<KEY>_NAME`, accepted for any key | the keys are declared in `diun_keys` |
| tag `monitoring_diun` | tags `monitoring` and `monitoring_diun` |

### Tests

The molecule scenario `default` uses tart with one VM `molecule-diun`.
`prepare` enables the podman socket, starts [mailpit](https://mailpit.axllent.org) and a container with the label `diun.enable=true`.
`side_effect` runs the role with `diun_container` not a dictionary, a secret without target, the password and its file variable in the environment,
an unknown environment variable in `diun_environment` and in `diun_container.environment`, an unknown secret,
a registry option without its key in `diun_keys`, the registry password in the environment, an invalid key and an unknown entry in `diun_keys`
and checks that it fails with the expected message and the quadlet unit is unchanged (tasks marked `expect ERROR`),
then it changes `DIUN_WATCH_WORKERS` and checks that Diun was restarted.
`verify` checks the quadlet unit with the mounted secrets, `DIUN_NOTIF_MAIL_PASSWORDFILE` and the options of the registry key `MOLECULE` of `diun_keys`
with `DIUN_REGOPTS_MOLECULE_USERNAMEFILE` and `DIUN_REGOPTS_MOLECULE_PASSWORDFILE`, that the files contain the secrets and no password is set in the environment, that the docker provider found the labeled container through the podman socket,
and sends a test notification with `diun notif test`, which must arrive at mailpit.

```
cd monitoring_diun
MOLECULE_TART_IMAGE='debian' molecule test
```
