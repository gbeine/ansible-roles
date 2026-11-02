Diun runs in the official container image [crazymax/diun](https://crazymax.dev/diun/) as podman quadlet.
It is configured with environment variables only, every option of the [configuration](https://crazymax.dev/diun/config/) is available as `DIUN_<PATH>`,
e.g. `watch.schedule` as `DIUN_WATCH_SCHEDULE` or `notif.mail.host` as `DIUN_NOTIF_MAIL_HOST`.
The data (`diun.db`) is in `<diun_home>/data`.

### Environment and secrets

All variables are set with `diun_environment`, which is merged over the defaults of the role.
Variables carrying secrets are passed as podman secrets with `diun_secrets`, every secret is created with `podman secret create` and passed into the container as environment variable `target`.

The role fails before it changes anything if a variable in `diun_environment` contains `PASSWORD`, `TOKEN`, `SECRET` or `WEBHOOKURL` in its name,
or if the target of a secret is also set in `diun_environment`.

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

### Containers of the host

With `diun_provider_podman: true` (default) Diun watches the containers of the host with the docker provider through the podman socket:
the role mounts `/run/podman/podman.sock` read-only as `/var/run/docker.sock` and sets `DIUN_PROVIDERS_DOCKER=true`,
`DIUN_PROVIDERS_DOCKER_ENDPOINT=unix:///var/run/docker.sock`, `DIUN_PROVIDERS_DOCKER_WATCHBYDEFAULT=false` and `DIUN_PROVIDERS_DOCKER_WATCHSTOPPED=false`.
The podman socket must be enabled, e.g. with `podman_socket_enabled: true` of `container_podman`.
Containers are watched if they have the label `diun.enable=true`, set `DIUN_PROVIDERS_DOCKER_WATCHBYDEFAULT: 'true'` in `diun_environment` to watch all containers.

With `diun_provider_podman: false` the role sets no provider, configure e.g. the file provider with `diun_environment` and `diun_volumes`.

### Restart and updates

Diun is restarted if it was running and a secret or the quadlet unit changed, e.g. by a changed environment variable.
Updates of the image are done by `container_update` with `diun_autoupdate_enabled: true` and `diun_autoupdate_schedule`.

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

### Tests

The molecule scenario `default` uses tart with one VM `molecule-diun`.
`prepare` enables the podman socket, starts [mailpit](https://mailpit.axllent.org) and a container with the label `diun.enable=true`.
`side_effect` changes `DIUN_WATCH_WORKERS` and checks that Diun was restarted.
`verify` checks the quadlet unit, that the secret is passed as environment variable, that the docker provider found the labeled container through the podman socket,
and sends a test notification with `diun notif test`, which must arrive at mailpit.

```
cd monitoring_diun
MOLECULE_TART_IMAGE='debian' molecule test
```
