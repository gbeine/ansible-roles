Jellyfin runs in the container image [linuxserver/jellyfin](https://docs.linuxserver.io/images/docker-jellyfin/) (`latest` by default) as podman quadlet.
The init of the image runs Jellyfin as user and group 911 (`PUID` and `PGID`).
`jellyfin_home` is mounted to `/config` and contains the configuration, the database and the cache,
`jellyfin_library` is mounted to `/data`, the role does not create it, it may be a mount of a network share.

### Ports and reverse proxy

Jellyfin serves HTTP on port 8096, TLS is terminated by a reverse proxy, e.g. Traefik.
`jellyfin_url` is the public URL announced to the clients (`JELLYFIN_PublishedServerUrl`), it is not set if empty.

```yaml
jellyfin_url: 'https://jellyfin.example.org'
jellyfin_labels:
  traefik.enable: 'true'
  traefik.http.routers.jellyfin.rule: 'Host(`jellyfin.example.org`)'
  traefik.http.services.jellyfin.loadbalancer.server.port: 8096
```

The ports 7359/udp (client discovery) and 1900/udp (DLNA) are published by default.
The container runs in a bridge network, broadcasts and multicast do not reach it, so discovery and DLNA only work partially.

### Libraries

Further libraries are mounted with `jellyfin_container.volumes`, it replaces the volumes of the default completely, so they have to be repeated:

```yaml
jellyfin_container:
  volumes:
    - '/etc/localtime:/etc/localtime:ro'
    - '/etc/timezone:/etc/timezone:ro'
    - '/opt/jellyfin:/config'
    - '/srv/media:/data'
    - '/srv/music:/music:ro'
```

### Hardware transcoding

Hardware transcoding needs the devices of the GPU (e.g. `/dev/dri`) in the container.
The role does not pass devices to the container, mounting `/dev/dri` as volume does not grant the access to the devices.

### Container

Ports, volumes, additional hosts (`etc_hosts`) and the environment are changed with `jellyfin_container`, it is merged over the default of the container.
The merge is not recursive, `publish`, `volumes` and `environment` replace the values of the default completely,
`environment` has to contain `PUID`, `PGID`, `TZ` and `JELLYFIN_PublishedServerUrl`, if needed.

### Validation

The role checks before any change that `jellyfin_home` and `jellyfin_library` are absolute paths and `jellyfin_url` is empty or an http or https URL.
If `jellyfin_container` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Restart and updates

Jellyfin is restarted if it was running and the quadlet unit changed, otherwise it is started and enabled.
Updates of the image are done by `container_update` with `jellyfin_autoupdate_enabled: true` and `jellyfin_autoupdate_schedule`,
without `jellyfin_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

- `jellyfin_discovery` was never evaluated and is removed, the ports of discovery and DLNA are changed with `jellyfin_container.publish`.
- `JELLYFIN_PublishedServerUrl` is not set anymore without `jellyfin_url`, formerly it was empty.
- `podman___update_mode` is not evaluated anymore, the role neither stops the container nor pulls the image or recreates the container.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-jellyfin-default` | Only the mandatory variables, no public URL |
| `molecule-jellyfin` | IPv6, labels and a public URL |

`prepare` creates the podman network and the library and pulls the image.
`side_effect` runs the role with `jellyfin_container` not a dictionary, a relative `jellyfin_home`, an empty `jellyfin_library` and a URL without scheme
and checks that it fails with the expected message and the quadlet unit is unchanged (tasks marked `expect ERROR`),
then it changes `jellyfin_url` on `molecule-jellyfin`, the quadlet unit changes and Jellyfin has to restart.
`verify` checks the quadlet unit, the service, the configuration directory, the addresses and the environment of the container,
waits until `/health` answers `Healthy` and reads the version and the public URL from `/System/Info/Public`.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd app_jellyfin
MOLECULE_TART_IMAGE='debian' molecule test
```
