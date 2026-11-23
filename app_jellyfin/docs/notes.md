Jellyfin runs in the container image [linuxserver/jellyfin](https://docs.linuxserver.io/images/docker-jellyfin/) (`latest` by default) as podman quadlet.
The init of the image runs Jellyfin as user and group 911 (`PUID` and `PGID`).
`jellyfin_home` is mounted to `/config` and contains the configuration, the database and the cache,
`jellyfin_library` is mounted to `/data`, the role does not create it, it may be a mount of a network share.

Jellyfin manages its own configuration (`system.xml`, `network.xml`, …) in `/config`, the role does not write it,
the settings are changed in the web interface of Jellyfin.

### Environment

`jellyfin_environment` is merged over the default of the role, `PUID` and `PGID` (911) and `TZ` from `jellyfin_timezone`,
it only takes the variables of the image: `UMASK`, `JELLYFIN_PublishedServerUrl` and `FFMPEG_PATH`.
The time zone is set by podman with `jellyfin_timezone` (`/etc/localtime` of the container) and as `TZ`, the linuxserver image reads it.

### Ports and reverse proxy

Jellyfin serves HTTP on port 8096, TLS is terminated by a reverse proxy, e.g. Traefik.
`JELLYFIN_PublishedServerUrl` is the public URL announced to the clients, an http or https URL, it is not set by default.

```yaml
jellyfin_environment:
  JELLYFIN_PublishedServerUrl: 'https://jellyfin.example.org'
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
    - '/opt/jellyfin:/config'
    - '/srv/media:/data'
    - '/srv/music:/music:ro'
```

### Hardware transcoding

Hardware transcoding needs the devices of the GPU (e.g. `/dev/dri`) in the container.
The role does not pass devices to the container, mounting `/dev/dri` as volume does not grant the access to the devices.

### Allowed variables

The role only allows the variables of the image in the environment of the container (`app_jellyfin__environment_allowed`):
`PUID`, `PGID`, `TZ`, `UMASK`, `JELLYFIN_PublishedServerUrl` and `FFMPEG_PATH`, generated from `readme-vars.yml` and `svc-jellyfin`
of linuxserver/docker-jellyfin and the common variables of the base image. It stops before any change if unknown variables are set.
This prevents unexpected behavior by accident, e.g. by a typo. The image sets the `JELLYFIN_*_DIR` variables itself.

### Container

Ports, volumes, additional hosts (`etc_hosts`) and the dependencies are changed with `jellyfin_container`, it is merged over the default of the container.
The dependencies of the quadlet unit are lists: `requires`, `wants`, `after`, `part_of` and `binds_to` are units,
`requires_mounts_for` are paths, e.g. a library on a network share. They are written to `[Unit]` as `Requires=`, `Wants=`, `After=`, `PartOf=`, `BindsTo=` and `RequiresMountsFor=`.
The merge is not recursive, `publish` and `volumes` replace the values of the default completely,
`jellyfin_container.environment` replaces the environment including `jellyfin_environment`, use `jellyfin_environment` instead.

```yaml
jellyfin_container:
  requires_mounts_for: [ '/srv/media' ]
```

### Validation

The role checks before any change:

- `jellyfin_home` and `jellyfin_library` are absolute paths
- the environment of the container only contains allowed variables without line breaks and without YAML booleans
- `JELLYFIN_PublishedServerUrl` is an http or https URL

If `jellyfin_container` or `jellyfin_environment` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Check mode

The role runs with `--check`, also on a host where it never ran, and reports the configuration directory and the quadlet unit.
The start and the wait for Jellyfin do not run in check mode.

### Restart and updates

Jellyfin is restarted if it was running and the quadlet unit changed, otherwise it is started and enabled.
If the start fails, the role shows the journal of the service, afterwards it waits until `/health` answers `Healthy` and shows the journal otherwise.
Updates of the image are done by `container_update` with `jellyfin_autoupdate_enabled: true` and `jellyfin_autoupdate_schedule`,
without `jellyfin_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

- `jellyfin_url` is removed, the public URL is `jellyfin_environment.JELLYFIN_PublishedServerUrl`.
- The environment is set with `jellyfin_environment`, merged over the default of the role, instead of `jellyfin_container.environment`.
  Only the variables of the image are allowed.
- `/etc/localtime` and `/etc/timezone` are not mounted anymore, the time zone is set by podman and `TZ` with `jellyfin_timezone`.
- `jellyfin_discovery` was never evaluated and is removed, the ports of discovery and DLNA are changed with `jellyfin_container.publish`.
- `JELLYFIN_PublishedServerUrl` is not set by default, formerly it was empty without `jellyfin_url`.
- `podman___update_mode` is not evaluated anymore, the role neither stops the container nor pulls the image or recreates the container.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-jellyfin-default` | Only the mandatory variables, no public URL |
| `molecule-jellyfin` | IPv6, labels, `UMASK` and a public URL |

`prepare` creates the podman network and the library and pulls the image.
`check` runs `converge` with `--check` on the new VMs.
`side_effect` runs the role with `jellyfin_container` not a dictionary, a relative `jellyfin_home`, an empty `jellyfin_library`, a URL without scheme,
an unknown environment variable, a line break and a YAML boolean in the environment
and checks that it fails with the expected message and the quadlet unit is unchanged (tasks marked `expect ERROR`),
then it changes `JELLYFIN_PublishedServerUrl` on `molecule-jellyfin`, the quadlet unit changes and Jellyfin has to restart,
`molecule-jellyfin-default` runs again without a change and must not restart.
`verify` checks the quadlet unit without `/etc/localtime`, the service without automatic restarts, the configuration directory,
the addresses, the time zone and the environment of the container, waits until `/health` answers `Healthy`
and reads the version and the public URL from `/System/Info/Public`.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd app_jellyfin
MOLECULE_TART_IMAGE='debian' molecule test
```
