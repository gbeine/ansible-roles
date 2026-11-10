evcc runs in the container image [evcc/evcc](https://hub.docker.com/r/evcc/evcc) (`latest` by default) as podman quadlet.
The container runs as root, `evcc_home` is mounted to `/root/.evcc` and contains the database `evcc.db`.

### Configuration

Without a configuration file evcc is configured in the UI, the configuration is stored in `evcc.db`.
The password of the admin is set at the first call of the UI.
A configuration file `evcc.yaml` is mounted with `evcc_container.volumes`, evcc reads it from `/etc/evcc.yaml`.
`evcc_container.volumes` replaces the volumes of the default completely, so they have to be repeated:

```yaml
evcc_container:
  volumes:
    - '/etc/timezone:/etc/timezone:ro'
    - '/etc/localtime:/etc/localtime:ro'
    - '/opt/evcc:/root/.evcc'
    - '/opt/evcc-config/evcc.yaml:/etc/evcc.yaml:ro'
```

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

Ports, volumes, additional hosts (`etc_hosts`) and the environment are changed with `evcc_container`, it is merged over the default of the container.
The merge is not recursive, `publish`, `volumes` and `environment` replace the values of the default completely.
The health check of the image is kept.

### Validation

The role checks before any change that `evcc_home` is an absolute path.
If `evcc_container` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Restart and updates

evcc is restarted if it was running and the quadlet unit changed, otherwise it is started and enabled.
Updates of the image are done by `container_update` with `evcc_autoupdate_enabled: true` and `evcc_autoupdate_schedule`,
without `evcc_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

`podman___update_mode` is not evaluated anymore, the role neither stops the container nor pulls the image or recreates the container.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-evcc-default` | Only the mandatory variables, the ports 7070 and 8887 are published |
| `molecule-evcc` | IPv6, labels and an own port published with `evcc_container.publish` |

`prepare` creates the podman network and pulls the image.
`side_effect` runs the role with `evcc_container` not a dictionary, an empty and a relative `evcc_home` and checks that it fails with the expected message
and the quadlet unit is unchanged (tasks marked `expect ERROR`),
then it changes `evcc_home` on `molecule-evcc`, the quadlet unit changes and evcc has to restart.
`verify` checks the quadlet unit, the service, the data directory and the addresses of the container,
waits until the API answers on port 7070, requests it on the published port and checks that the database is created in the data directory.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd app_evcc
MOLECULE_TART_IMAGE='debian' molecule test
```
