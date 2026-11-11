Collabora Online Development Edition (CODE) runs in the container image [collabora/code](https://hub.docker.com/r/collabora/code) (`latest` by default) as podman quadlet.
The start script of the image runs `coolwsd` with `--use-env-vars`, Collabora is configured with environment variables and listens on port 9980.

### Environment and secrets

The environment is set with `collabora_environment`, which is merged over the defaults of the role
(`TZ`, `username: 'admin'` and `extra_params`).
Variables carrying secrets are passed as podman secrets with `collabora_secrets` and must not be set in `collabora_environment`.
Every secret is created with `podman secret create` and passed into the container as environment variable `target`.

The role requires the following variables and checks them before it changes anything:

- `username` in `collabora_environment`, the user of the admin console, `admin` by default
- `password` as secret in `collabora_secrets`, the password of the admin console

```yaml
collabora_secrets:
  - name: 'collabora_password'
    data: 'secret'
    target: 'password'
```

#### Allowed variables

The role only allows the environment variables in `app_collabora__environment_allowed` and the secrets in `app_collabora__secrets_allowed`,
it stops before any change if unknown variables or secrets are set.
This prevents unexpected behavior by accident, e.g. by a typo or a variable that has to be passed as secret.
The check uses the environment and the secrets of the container after merging `collabora_container`,
so variables set with `collabora_container.environment` and secrets set with `collabora_container.secrets` are checked as well.

Allowed environment variables:

- `TZ`
- `username`
- `extra_params`
- `domain`
- `server_name`
- `dictionaries`
- `DONT_GEN_SSL_CERT`
- `cert_domain`
- `aliasgroup1`
- `aliasgroup2`
- `aliasgroup3`
- `aliasgroup4`
- `aliasgroup5`
- `aliasgroup6`
- `aliasgroup7`
- `aliasgroup8`
- `aliasgroup9`

Allowed secrets, the targets of the secrets:

- `password`

### TLS

By default Collabora serves HTTP, the role sets `extra_params` to `--o:ssl.enable=false --o:ssl.termination=true`,
TLS is terminated by a reverse proxy, e.g. Traefik.
`aliasgroup1` defines the WOPI host allowed to open documents, e.g. Nextcloud.

```yaml
collabora_environment:
  aliasgroup1: 'https://cloud.example.org:443'
collabora_labels:
  traefik.enable: 'true'
  traefik.http.routers.collabora.rule: 'Host(`office.example.org`)'
  traefik.http.services.collabora.loadbalancer.server.port: 9980
```

With `extra_params: ''` in `collabora_environment` Collabora serves HTTPS on port 9980 with a self-signed certificate created by the image at every start.

### Admin console

The admin console `/browser/dist/admin/admin.html` uses `username` of the environment and the secret with target `password`.
The password is passed as podman secret, so it is not part of the quadlet unit.

### Container

Collabora creates jails for its document processes and needs the capabilities `SYS_CHROOT`, `SYS_ADMIN`, `FOWNER`, `CHOWN` and `MKNOD`,
they are always added. The health check of the image is disabled.
Ports and volumes are changed with `collabora_container`, it is merged over the default of the container.
The merge is not recursive, `publish` and `volumes` replace the values of the default completely,
`collabora_container.environment` replaces the environment including `collabora_environment`, use `collabora_environment` instead.

### Validation

The role checks before any change that only allowed environment variables and secrets are set in the container, that the required environment variables are set and not empty,
every secret has `name`, `data` and `target`, the required secrets exist and no secret target is set in `collabora_environment`.
If `collabora_container` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Restart and updates

Collabora is restarted if it was running and a secret or the quadlet unit changed, otherwise it is started and enabled.
Updates of the image are done by `container_update` with `collabora_autoupdate_enabled: true` and `collabora_autoupdate_schedule`,
without `collabora_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

- `collabora_username` is replaced by `username` in `collabora_environment`.
- `collabora_password` is replaced by a secret in `collabora_secrets` with target `password`.
  The former secret `collabora_password` can be kept as name of the secret.
- The environment in `collabora_container.environment` is replaced by `collabora_environment`, the defaults have not to be repeated anymore.
- Former versions of the role served HTTPS with the self-signed certificate of the image and did not set `username`, the admin console was not usable.
  Set `extra_params: ''` in `collabora_environment` to keep HTTPS.
- `podman___update_mode` is not evaluated anymore, the role neither stops the container nor pulls the image or recreates the container.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-collabora-default` | Only the mandatory variables and the secret of the password, HTTP with TLS termination and the user `admin` |
| `molecule-collabora` | IPv6, `collabora_environment` with an own user, `aliasgroup1` and an empty `extra_params`, HTTPS with the self-signed certificate |

`prepare` creates the podman network and pulls the image.
`side_effect` runs the role with `collabora_container` not a dictionary, an empty username, without the secret of the password and with the password in the environment, an unknown environment variable in `collabora_environment` and in `collabora_container.environment` and an unknown secret and checks that it fails with the expected message
and the quadlet unit is unchanged (tasks marked `expect ERROR`),
then it changes the data of the secret on `molecule-collabora`, Collabora has to restart.
`verify` checks the quadlet unit with the secrets, the capabilities and the disabled health check, the service, the secrets, the addresses and the environment of the container,
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
