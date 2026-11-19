evcc runs in the container image [evcc/evcc](https://hub.docker.com/r/evcc/evcc) (`latest` by default) as podman quadlet.
The container runs as root, `evcc_home` is mounted to `/root/.evcc` and contains the database `evcc.db`.

### Configuration

Without a configuration file evcc runs in the database-only mode, it is configured in the UI and the configuration is stored in `evcc.db`.
The password of the admin is set at the first call of the UI.

`evcc_config` is the content of `evcc.yaml`, evcc reads it from `/etc/evcc.yaml`, it has no default.
The keys of the file are the keys of `globalconfig.All` of evcc, e.g. `log`, `interval`, `network`, `mqtt`, `influx`, `meters`, `chargers`, `vehicles`, `loadpoints` or `site`.
The role checks these keys, evcc checks the keys below them itself and does not start with an unknown key.
Devices configured in `evcc.yaml` cannot be changed in the UI.

```yaml
evcc_config:
  log: 'info'
  interval: '30s'
  mqtt:
    broker: 'mqtt.example.org:1883'
    user: 'evcc'
    topic: 'evcc'
evcc_secrets:
  - name: 'evcc_mqtt_password'
    data: "{{ vault_evcc_mqtt_password }}"
    target: 'mqtt.password'
```

Without `evcc_config` and `evcc_secrets` the role writes no `evcc.yaml`, a former `evcc.yaml` is removed.

### Secrets

`evcc.yaml` cannot read files and evcc reads no file variables (`*_FILE`), only the environment variables `EVCC_*`, which would carry the passwords in plain text.
So the whole `evcc.yaml` with the passwords is the podman secret `evcc-config`, it is mounted with `type=mount,target=/etc/evcc.yaml,mode=0400`,
the file never exists on the host.

`evcc_secrets` is a list of entries with `name`, `data` and `target`, the target is the path of the option in `evcc.yaml`:
`sponsortoken`, `mqtt.password`, `mqtt.clientkey`, `influx.password` and `influx.token`. The role merges the secrets into `evcc_config`,
a target must not be set in `evcc_config`. The name of an entry only names the secret in the inventory, the role creates no podman secret per entry.
Credentials of devices, e.g. the password of a charger in `chargers`, are part of `evcc_config`, take them from the vault, `evcc.yaml` is a secret anyway.

A changed `evcc.yaml` changes the secret and restarts the running service.

### Allowed variables

The role only allows the keys in `app_evcc__config_allowed` in `evcc_config`, the targets in `app_evcc__secrets_allowed`
and the environment variables in `app_evcc__environment_allowed`, it stops before any change if unknown keys, secrets or variables are set.
This prevents unexpected behavior by accident, e.g. by a typo or an option that has to be set in `evcc_config`.
The check of the environment uses the environment of the container after merging `evcc_container`.

The keys are generated from `api/globalconfig/types.go` of evcc 0.319.1.
The environment only takes `TZ` and the variables of the customization of the UI, which evcc reads with `os.Getenv` in `cmd/root.go`:
`EVCC_CUSTOM_CSS`, `EVCC_CUSTOM_LOGO_LIGHT`, `EVCC_CUSTOM_LOGO_DARK`, `EVCC_CUSTOM_ICON`, `EVCC_CUSTOM_BRAND`, `EVCC_CUSTOM_WEBSITE`,
`EVCC_CUSTOM_EMAIL`, `EVCC_CUSTOM_PHONE` and `EVCC_CUSTOM_THEME`. New versions of evcc may add keys and variables.

### Time zone

The image sets `TZ=Europe/Berlin` and evcc prefers `TZ` to `/etc/localtime`, so the role sets `TZ` from `evcc_timezone`.
podman sets `/etc/localtime` of the container with `evcc_timezone` as well, the files of the host are not mounted.

### Ports

The UI and the API (port 7070) and OCPP (port 8887) are published by default.
Further ports are published with `evcc_container.publish`, it replaces the ports of the default completely:

```yaml
evcc_container:
  publish:
    - '7070:7070'
    - '8887:8887'
    - '4712:4712'       # EEBus
    - '7090:7090/udp'   # KEBA
    - '9522:9522/udp'   # SMA Energy Manager
```

The container runs in a bridge network, the discovery of devices by mDNS and UDP broadcasts does not work.
For a reverse proxy, e.g. Traefik, the labels are set with `evcc_labels`:

```yaml
evcc_labels:
  traefik.enable: 'true'
  traefik.http.routers.evcc.rule: 'Host(`evcc.example.org`)'
  traefik.http.services.evcc.loadbalancer.server.port: 7070
```

### Container

Ports, volumes, additional hosts (`etc_hosts`) and the dependencies are changed with `evcc_container`, it is merged over the default of the container.
The dependencies of the quadlet unit are lists: `requires`, `wants`, `after`, `part_of` and `binds_to` are units,
`requires_mounts_for` are paths. They are written to `[Unit]` as `Requires=`, `Wants=`, `After=`, `PartOf=`, `BindsTo=` and `RequiresMountsFor=`.

```yaml
evcc_container:
  wants: [ 'network-online.target' ]
  after: [ 'network-online.target' ]
```

The merge is not recursive, `publish` and `volumes` replace the values of the default completely,
`evcc_container.secrets` replaces the secret of `evcc.yaml`, `evcc_container.environment` replaces the environment including `TZ`, use `evcc_environment` instead.
The health check of the image is kept.

### Validation

The role checks before any change:

- `evcc_secrets` is a list of entries with `name`, `data` and `target` and unique names, only allowed targets are used
- `evcc_config` is a dictionary of known keys without the targets of the secrets
- `evcc_home` is an absolute path
- only allowed environment variables are set in the container, the values contain no line breaks

If `evcc_container` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Check mode

The role runs with `--check` without failing, also on a host where it never ran before.
It reports the changes of the secret of `evcc.yaml` and the quadlet unit, the service is neither started nor restarted.

### Restart and updates

evcc is restarted if it was running and `evcc.yaml` or the quadlet unit changed, otherwise it is started and enabled.
If the start fails, the role stops with the last lines of the journal of the service.
Updates of the image are done by `container_update` with `evcc_autoupdate_enabled: true` and `evcc_autoupdate_schedule`,
without `evcc_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

- The environment in `evcc_container.environment` is replaced by `evcc_environment`.
- `podman___update_mode` is not evaluated anymore, the role neither stops the container nor pulls the image or recreates the container.
- The options of evcc are no longer set in the environment, they are keys of `evcc_config`:
  `EVCC_LOG` is `log`, `EVCC_INTERVAL` is `interval`, `EVCC_PLANT` is `plant`, `EVCC_TELEMETRY` is `telemetry`, `EVCC_METRICS` is `metrics`, `EVCC_PROFILE` is `profile`,
  `EVCC_NETWORK_SCHEMA`, `EVCC_NETWORK_HOST` and `EVCC_NETWORK_PORT` are `network.schema`, `network.host` and `network.port`,
  `EVCC_DATABASE_DSN` is `database.dsn`, `EVCC_MQTT_BROKER`, `EVCC_MQTT_TOPIC` and `EVCC_MQTT_USER` are `mqtt.broker`, `mqtt.topic` and `mqtt.user`.
- The secrets have the paths of the options as targets: `EVCC_SPONSORTOKEN` is `sponsortoken`, `EVCC_MQTT_PASSWORD` is `mqtt.password`.
  They are part of the secret `evcc-config`, the former secrets passed with `type=env` are not removed by the role, remove them with `podman secret rm <name>`.
- A configuration file mounted with `evcc_container.volumes` is replaced by `evcc_config`.
- `TZ` is set from `evcc_timezone`, before the container used `TZ=Europe/Berlin` of the image.
  `/etc/localtime` and `/etc/timezone` of the host are no longer mounted, the host no longer needs `/etc/timezone`.
- `wants`, `after`, `part_of`, `binds_to` and `requires_mounts_for` of `evcc_container` are new, `requires` was supported before.
- Line breaks in the environment are rejected.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-evcc-default` | Only the mandatory variables, database-only mode without `evcc.yaml`, the ports 7070 and 8887 are published |
| `molecule-evcc` | IPv6, labels, dependencies, `EVCC_CUSTOM_BRAND`, `evcc_config` with `log` and `interval`, a secret with target `mqtt.password` and an own port published with `evcc_container.publish` |

`check` runs `converge` with `--check` on the new VMs.
`prepare` creates the podman network and pulls the image.
`side_effect` runs the role with `evcc_container` and `evcc_config` not a dictionary, a secret without target, an empty and a relative `evcc_home`,
an unknown key and the password of MQTT in `evcc_config`, a former variable as target of a secret, an option of evcc and a line break in the environment
and an unknown environment variable in `evcc_container.environment` and checks that it fails with the expected message
and the quadlet unit is unchanged (tasks marked `expect ERROR`),
then it changes `interval` on `molecule-evcc`, `evcc.yaml` changes and evcc has to restart, `molecule-evcc-default` runs again without a change and must not restart.
`verify` checks the quadlet unit with the secret of `evcc.yaml`, the dependencies, `TZ` and without the files of the host, the service without automatic restarts,
`evcc.yaml` in the container with the password from the secret, the data directory, the addresses, the environment and the time zone of the container,
waits until the API answers on port 7070, requests it on the published port, checks the interval of `evcc.yaml` in `/api/state` and that the database is created in the data directory.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd app_evcc
MOLECULE_TART_IMAGE='debian' molecule test
```
