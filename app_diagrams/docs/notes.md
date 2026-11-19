draw.io runs in the container image [jgraph/drawio](https://hub.docker.com/r/jgraph/drawio) (`latest` by default) as podman quadlet.
The image runs Tomcat, the entrypoint configures the editor with the `DRAWIO_*` environment variables at every start.

### Configuration

draw.io is configured completely with environment variables in `diagrams_environment`, it is merged over the defaults of the role (`LETS_ENCRYPT_ENABLED: 'false'`).
The entrypoint of the image writes the variables into `js/PreConfig.js` and the files of the storage integrations at every start,
the servlets of draw.io read further variables, e.g. `ENABLE_DRAWIO_PROXY`. draw.io keeps no data,
the role has no home directory and creates no files on the host, so the environment is kept.
`DRAWIO_CONFIG_FILE` names a JSON file in the container, it has to be mounted with `diagrams_container.volumes`.
The time zone is set by podman with `diagrams_timezone` (`/etc/localtime` of the container), `TZ` is not needed.

The role requires `DRAWIO_BASE_URL` in `diagrams_environment`, the public URL of draw.io, and checks it before it changes anything.
A path in `DRAWIO_BASE_URL` or `DRAWIO_SERVER_URL` sets the context path of Tomcat, e.g. `https://example.org/drawio` serves draw.io below `/drawio/`.
Only the last segment of the path is used.

```yaml
diagrams_environment:
  DRAWIO_BASE_URL: 'https://diagrams.example.org'
  DRAWIO_LANG: 'de'
```

`DRAWIO_CONFIG` (JSON configuration of the editor), `DRAWIO_LANG` (default language), `DRAWIO_CSP_HEADER`,
`DRAWIO_GOOGLE_*`, `DRAWIO_MSGRAPH_*` and `DRAWIO_GITLAB_*` for the storage integrations are described in the [README of the image](https://github.com/jgraph/docker-drawio).

#### Ports and TLS

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

### Secrets

`diagrams_secrets` is a list of podman secrets with `name`, `data` and `target`, the usual name of the variable, e.g. `DRAWIO_GITLAB_SECRET`.
No secret is required. Every secret is created with `podman secret create` and passed with `type=env,target=<target>`,
because the entrypoint of the image reads the secrets only from the environment and has no file variables for them.
The secrets are not part of the quadlet unit, podman sets them when the container starts.
The targets must not be set in `diagrams_environment`.

```yaml
diagrams_secrets:
  - name: 'diagrams_gitlab_secret'
    data: "{{ vault_diagrams_gitlab_secret }}"
    target: 'DRAWIO_GITLAB_SECRET'
```

Allowed secrets, the targets of the secrets:

- `KEYSTORE_PASS`
- `KEY_PASS`
- `DRAWIO_GOOGLE_CLIENT_SECRET`
- `DRAWIO_GOOGLE_VIEWER_CLIENT_SECRET`
- `DRAWIO_MSGRAPH_CLIENT_SECRET`
- `DRAWIO_GITLAB_SECRET`

### Allowed variables

The role only allows the environment variables in `app_diagrams__environment_allowed` and the secrets in `app_diagrams__secrets_allowed`,
it stops before any change if unknown variables or secrets are set.
This prevents unexpected behavior by accident, e.g. by a typo or a variable that has to be passed as secret.
The check uses the environment and the secrets of the container after merging `diagrams_container`,
so variables set with `diagrams_container.environment` and secrets set with `diagrams_container.secrets` are checked as well.

Allowed environment variables, generated from `/docker-entrypoint.sh` of `jgraph/drawio` 32.7.4 and the servlets of draw.io (`src/main/server/java`),
new versions of the image may add variables:

- `TZ`, the time zone is set by podman, `TZ` is not needed
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
- `DRAWIO_USE_HTTP`, `DRAWIO_MEMCACHED_ENDPOINT`, `ENABLE_DRAWIO_PROXY`, `DRAWIO_PROXY_ALLOWED_PORTS`, `ALLOW_INTERNAL_10_NET` and `EXPORT_URL`, read by the servlets of draw.io

Allowed secrets, the targets of the secrets:

- `KEYSTORE_PASS`
- `KEY_PASS`
- `DRAWIO_GOOGLE_CLIENT_SECRET`
- `DRAWIO_GOOGLE_VIEWER_CLIENT_SECRET`
- `DRAWIO_MSGRAPH_CLIENT_SECRET`
- `DRAWIO_GITLAB_SECRET`

### Container

Ports, volumes and additional hosts (`etc_hosts`) are changed with `diagrams_container`, it is merged over the default of the container, the default has no volumes.
The dependencies of the quadlet unit are lists in `diagrams_container`: `requires`, `wants`, `after`, `part_of` and `binds_to` are units,
`requires_mounts_for` are paths. They are written to `[Unit]` as `Requires=`, `Wants=`, `After=`, `PartOf=`, `BindsTo=` and `RequiresMountsFor=`.

```yaml
diagrams_container:
  wants: [ 'network-online.target' ]
  after: [ 'network-online.target' ]
```

The merge is not recursive, `publish` and `volumes` replace the values of the default completely,
`diagrams_container.environment` replaces the environment including `diagrams_environment`, use `diagrams_environment` instead.

### Validation

The role checks before any change:

- `diagrams_secrets` is a list of entries with `name`, `data` and `target` and unique names
- `DRAWIO_BASE_URL` is set and not empty
- no secret target is set in `diagrams_environment`
- only allowed environment variables and secrets are set in the container, the values contain no line breaks

If `diagrams_container` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Check mode

The role runs with `--check` without failing, also on a host where it never ran before.
It reports the changes of the secrets and the quadlet unit, the service is neither started nor restarted.

### Restart and updates

draw.io is restarted if it was running and a secret or the quadlet unit changed, otherwise it is started and enabled.
If the start fails, the role stops with the last lines of the journal of the service.
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
- `TZ` is no longer set in the environment and `/etc/localtime` and `/etc/timezone` of the host are no longer mounted,
  the time zone is set by podman with `diagrams_timezone`. The host no longer needs `/etc/timezone`.
- `DRAWIO_USE_HTTP`, `DRAWIO_MEMCACHED_ENDPOINT`, `ENABLE_DRAWIO_PROXY`, `DRAWIO_PROXY_ALLOWED_PORTS`, `ALLOW_INTERNAL_10_NET` and `EXPORT_URL` are allowed now.
- `wants`, `after`, `part_of`, `binds_to` and `requires_mounts_for` of `diagrams_container` are new, `requires` was supported before.
- Line breaks in the environment are rejected.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-diagrams-default` | Only the mandatory variables, draw.io in the root context |
| `molecule-diagrams` | IPv6, labels, `diagrams_container.etc_hosts`, dependencies and a base URL with a path setting the context |

`check` runs `converge` with `--check` on the new VMs.
`prepare` creates the podman network and pulls the image.
`side_effect` runs the role with `diagrams_container` not a dictionary, a secret without target, an empty `DRAWIO_BASE_URL`, a secret with target `DRAWIO_GITLAB_SECRET` set in the environment, a line break in the environment, an unknown environment variable in `diagrams_environment` and in `diagrams_container.environment` and an unknown secret and checks that it fails with the expected message
and the quadlet unit is unchanged (tasks marked `expect ERROR`),
then it changes `DRAWIO_BASE_URL` on `molecule-diagrams`, the quadlet unit changes and draw.io has to restart,
`molecule-diagrams-default` runs again without a change and must not restart.
`verify` checks the quadlet unit with the dependencies and without `TZ` and the files of the host, the service, the addresses,
the environment without `TZ` and the time zone of the container,
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
