draw.io runs in the container image [jgraph/drawio](https://hub.docker.com/r/jgraph/drawio) (`latest` by default) as podman quadlet.
The image runs Tomcat, the entrypoint configures the editor with the `DRAWIO_*` environment variables at every start.

### Ports and TLS

draw.io serves HTTP on port 8080, TLS is terminated by a reverse proxy, e.g. Traefik.
The image creates a self-signed certificate at every start and serves HTTPS on port 8443 as well,
`LETS_ENCRYPT_ENABLED` is always `false`, a container behind a reverse proxy cannot get a certificate from Let's Encrypt.

```yaml
diagrams_environment:
  DRAWIO_BASE_URL: 'https://diagrams.example.org'
diagrams_labels:
  traefik.enable: 'true'
  traefik.http.routers.diagrams.rule: 'Host(`diagrams.example.org`)'
  traefik.http.services.diagrams.loadbalancer.server.port: 8080
```

### Environment and secrets

The environment is set with `diagrams_environment`, which is merged over the defaults of the role (`TZ` and `LETS_ENCRYPT_ENABLED`).
Variables carrying secrets, e.g. `DRAWIO_GOOGLE_CLIENT_SECRET`, are passed as podman secrets with `diagrams_secrets`
and must not be set in `diagrams_environment`.
Every secret needs `name`, `data` and `target`, it is created with `podman secret create` and passed into the container as environment variable `target`.

The role requires the following variable and checks it before it changes anything:

- `DRAWIO_BASE_URL` in `diagrams_environment`, the public URL of draw.io

A path in `DRAWIO_BASE_URL` sets the context path of Tomcat, e.g. `https://example.org/drawio` serves draw.io below `/drawio/`.
Only the last segment of the path is used.

#### Allowed variables

The role only allows the environment variables in `app_diagrams__environment_allowed` and the secrets in `app_diagrams__secrets_allowed`,
it stops before any change if unknown variables or secrets are set.
This prevents unexpected behavior by accident, e.g. by a typo or a variable that has to be passed as secret.
The check uses the environment and the secrets of the container after merging `diagrams_container`,
so variables set with `diagrams_container.environment` and secrets set with `diagrams_container.secrets` are checked as well.

Allowed environment variables:

- `TZ`
- `LETS_ENCRYPT_ENABLED`
- `PUBLIC_DNS`
- `ORGANISATION_UNIT`
- `ORGANISATION`
- `CITY`
- `STATE`
- `COUNTRY_CODE`
- `DRAWIO_CSP_HEADER`
- `DRAWIO_SERVER_URL`
- `DRAWIO_BASE_URL`
- `DRAWIO_VIEWER_URL`
- `DRAWIO_LIGHTBOX_URL`
- `DRAWIO_CONFIG`
- `DRAWIO_CONFIG_FILE`
- `DRAWIO_LANG`
- `DRAWIO_GOOGLE_CLIENT_ID`
- `DRAWIO_GOOGLE_APP_ID`
- `DRAWIO_GOOGLE_VIEWER_CLIENT_ID`
- `DRAWIO_GOOGLE_VIEWER_APP_ID`
- `DRAWIO_MSGRAPH_CLIENT_ID`
- `DRAWIO_MSGRAPH_TENANT_ID`
- `DRAWIO_GITLAB_ID`
- `DRAWIO_GITLAB_URL`

Allowed secrets, the targets of the secrets:

- `KEYSTORE_PASS`
- `KEY_PASS`
- `DRAWIO_GOOGLE_CLIENT_SECRET`
- `DRAWIO_GOOGLE_VIEWER_CLIENT_SECRET`
- `DRAWIO_MSGRAPH_CLIENT_SECRET`
- `DRAWIO_GITLAB_SECRET`

### Configuration

The editor is configured with further environment variables in `diagrams_environment`, e.g.
`DRAWIO_CONFIG` (JSON configuration of the editor), `DRAWIO_LANG` (default language), `DRAWIO_CSP_HEADER`,
`DRAWIO_GOOGLE_*`, `DRAWIO_MSGRAPH_*` and `DRAWIO_GITLAB_*` for the storage integrations,
see the [README of the image](https://github.com/jgraph/docker-drawio).

```yaml
diagrams_environment:
  DRAWIO_BASE_URL: 'https://diagrams.example.org'
  DRAWIO_LANG: 'de'
```

### Container

Ports, volumes and additional hosts (`etc_hosts`) are changed with `diagrams_container`, it is merged over the default of the container.
The merge is not recursive, `publish` and `volumes` replace the values of the default completely,
`diagrams_container.environment` replaces the environment including `diagrams_environment`, use `diagrams_environment` instead.

### Validation

The role checks before any change that only allowed environment variables and secrets are set in the container, that `DRAWIO_BASE_URL` is set and not empty,
every secret has `name`, `data` and `target` and no secret target is set in `diagrams_environment`.
If `diagrams_container` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Restart and updates

draw.io is restarted if it was running and a secret or the quadlet unit changed, otherwise it is started and enabled.
Updates of the image are done by `container_update` with `diagrams_autoupdate_enabled: true` and `diagrams_autoupdate_schedule`,
without `diagrams_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

Former versions of the role created the container with `restart_policy: always` instead of a quadlet unit.
Remove the old container before the first run with `podman rm -f diagrams`.

- `diagrams_base_url` is replaced by `DRAWIO_BASE_URL` in `diagrams_environment`.
- The environment in `diagrams_container.environment` is replaced by `diagrams_environment`, the defaults have not to be repeated anymore.
- `diagrams_hosts` is replaced by `diagrams_container.etc_hosts`.
- The version was read from `keycloak_version`, it is `diagrams_version` now.
- With `diagrams_ipv6` the role did not create the container at all, now the address is set.
- `podman___update_mode` is not evaluated anymore, the role neither pulls the image nor recreates the container.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-diagrams-default` | Only the mandatory variables, draw.io in the root context |
| `molecule-diagrams` | IPv6, labels, `diagrams_container.etc_hosts` and a base URL with a path setting the context |

`prepare` creates the podman network and pulls the image.
`side_effect` runs the role with `diagrams_container` not a dictionary, an empty `DRAWIO_BASE_URL` and a secret with target `TZ` set in the environment, an unknown environment variable in `diagrams_environment` and in `diagrams_container.environment` and an unknown secret and checks that it fails with the expected message
and the quadlet unit is unchanged (tasks marked `expect ERROR`),
then it changes `DRAWIO_BASE_URL` on `molecule-diagrams`, the quadlet unit changes and draw.io has to restart.
`verify` checks the quadlet unit, the service, the addresses and the environment of the container,
waits until draw.io answers on port 8080 in the expected context, reads the base URL from `js/PreConfig.js` and requests HTTPS on port 8443.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd app_diagrams
MOLECULE_TART_IMAGE='debian' molecule test
```
