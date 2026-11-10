Collabora Online Development Edition (CODE) runs in the container image [collabora/code](https://hub.docker.com/r/collabora/code) (`latest` by default) as podman quadlet.
The start script of the image runs `coolwsd` with `--use-env-vars`, Collabora is configured with environment variables and listens on port 9980.

### TLS

By default Collabora serves HTTP, the role sets `extra_params` to `--o:ssl.enable=false --o:ssl.termination=true`,
TLS is terminated by a reverse proxy, e.g. Traefik.
`aliasgroup1` defines the WOPI host allowed to open documents, e.g. Nextcloud.
`collabora_container.environment` replaces the environment of the default completely,
so `TZ`, `username` and `extra_params` have to be repeated:

```yaml
collabora_container:
  environment:
    TZ: 'Europe/Berlin'
    username: 'admin'
    extra_params: '--o:ssl.enable=false --o:ssl.termination=true'
    aliasgroup1: 'https://cloud.example.org:443'
collabora_labels:
  traefik.enable: 'true'
  traefik.http.routers.collabora.rule: 'Host(`office.example.org`)'
  traefik.http.services.collabora.loadbalancer.server.port: 9980
```

Without `extra_params` Collabora serves HTTPS on port 9980 with a self-signed certificate created by the image at every start.

### Admin console

The admin console `/browser/dist/admin/admin.html` uses `collabora_username` (`admin` by default) and `collabora_password`.
The password is created as podman secret `collabora_password` and passed into the container as environment variable `password`,
so it is not part of the quadlet unit.
The username is set in the environment of the container, if `collabora_container.environment` is set it has to contain `username`.

### Container

Collabora creates jails for its document processes and needs the capabilities `SYS_CHROOT`, `SYS_ADMIN`, `FOWNER`, `CHOWN` and `MKNOD`,
they are always added. The health check of the image is disabled.
Ports, volumes and the environment are changed with `collabora_container`, it is merged over the default of the container.
The merge is not recursive, `publish`, `volumes` and `environment` replace the values of the default completely.

### Validation

The role checks before any change that `collabora_username` and `collabora_password` are non-empty strings.
If `collabora_container` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Restart and updates

Collabora is restarted if it was running and the password or the quadlet unit changed, otherwise it is started and enabled.
Updates of the image are done by `container_update` with `collabora_autoupdate_enabled: true` and `collabora_autoupdate_schedule`,
without `collabora_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

Former versions of the role served HTTPS with the self-signed certificate of the image and did not set `username`, the admin console was not usable.
Set `collabora_container.environment` without `extra_params` to keep HTTPS, see above.
`podman___update_mode` is not evaluated anymore, the role neither stops the container nor pulls the image or recreates the container.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-collabora-default` | Only the mandatory variables, HTTP with TLS termination and the user `admin` |
| `molecule-collabora` | IPv6, an own user and `collabora_container.environment` with `aliasgroup1` and without `extra_params`, HTTPS with the self-signed certificate |

`prepare` creates the podman network and pulls the image.
`side_effect` runs the role with `collabora_container` not a dictionary, an empty password and an empty username and checks that it fails with the expected message
and the quadlet unit is unchanged (tasks marked `expect ERROR`),
then it changes the password on `molecule-collabora`, Collabora has to restart.
`verify` checks the quadlet unit with the secret, the capabilities and the disabled health check, the service, the secret, the addresses and the environment of the container,
waits until Collabora answers `OK`, reads the WOPI discovery and requests the admin console without and with the credentials.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd app_collabora
MOLECULE_TART_IMAGE='debian' molecule test
```
