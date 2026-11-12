The Nextcloud Whiteboard collaboration server runs in the container image [nextcloud-releases/whiteboard](https://github.com/nextcloud/whiteboard) (`stable` by default) as podman quadlet.
It synchronizes the whiteboards of the Nextcloud app Whiteboard in real time, the app connects the browsers to the server with a token signed with `JWT_SECRET_KEY`.
The server runs as the user `nobody` of the image and listens on port 3002 (`PORT`), it keeps no data, the rooms are kept in memory or in Redis.

### Configuration

All variables are set with `whiteboard_environment`, which is merged over the defaults of the role (`TZ`).
`NEXTCLOUD_URL` is mandatory, it is the URL of Nextcloud, the server only allows requests from its origin.
Booleans may be written as YAML booleans, the role passes them as `true` and `false`, the server only reads `true` as true.

```yaml
whiteboard_environment:
  NEXTCLOUD_URL: 'https://cloud.example.org'
  STORAGE_STRATEGY: 'redis'
whiteboard_secrets:
  - name: 'whiteboard_jwt_secret'
    data: "{{ vault_whiteboard_jwt_secret }}"
    target: 'JWT_SECRET_KEY'
  - name: 'whiteboard_redis_url'
    data: "redis://:{{ vault_redis_password }}@redis:6379"
    target: 'REDIS_URL'
```

The app Whiteboard of Nextcloud needs the URL of the server and the same `JWT_SECRET_KEY`,
e.g. `occ config:app:set whiteboard collabBackendUrl --value='https://whiteboard.example.org'` and `occ config:app:set whiteboard jwt_secret_key --value='…'`.

### Secrets

Variables carrying secrets are passed as podman secrets with `whiteboard_secrets` and must not be set in `whiteboard_environment`.
Every secret has a `name`, the `data` and the `target`, the name of the variable. `JWT_SECRET_KEY` is mandatory,
`METRICS_TOKEN` enables `/metrics` and `REDIS_URL` may contain the password of Redis.

The server reads its configuration only from the environment (`websocket_server/Utilities/ConfigUtility.js`), it reads no files for the secrets.
So the secrets are passed with `type=env,target=<target>`, they are not part of the quadlet unit, but part of the environment of the process in the container.

### Allowed variables

The role only allows the environment variables in `app_nextcloud_whiteboard__environment_allowed` and the secrets in `app_nextcloud_whiteboard__secrets_allowed`,
it stops before any change if unknown variables or secrets are set.
This prevents unexpected behavior by accident, e.g. by a typo or a variable that has to be passed as secret.
The variables are generated from `process.env` of `websocket_server` of whiteboard v2.1.2 and its Dockerfile without the secrets,
`HOSTNAME` and `USERNAME` are only fallbacks of the server and not allowed. New versions of the server may add variables, the lists are generated again.
The check uses the environment and the targets of the secrets of the container after merging `whiteboard_container`,
so variables set with `whiteboard_container.environment` and secrets set with `whiteboard_container.secrets` are checked as well.

### Container

Ports, volumes, additional hosts (`etc_hosts`) and dependencies (`requires`) are changed with `whiteboard_container`, it is merged over the default of the container.
The merge is not recursive, `whiteboard_container.environment` replaces the environment including `whiteboard_environment`,
`whiteboard_container.secrets` replaces the secrets of `whiteboard_secrets`.
The role waits until the server answers on its port, it shows the log of the service otherwise.

### Validation

The role checks before any change:

- `whiteboard_secrets` is a list of entries with `name`, `data` and `target` with unique names, `JWT_SECRET_KEY` is set
- `NEXTCLOUD_URL` is set and starts with `http://` or `https://`, `STORAGE_STRATEGY` is `lru` or `redis`
- no secret is set in `whiteboard_environment`, the booleans are `true` or `false`, values and secrets have no line breaks
- only allowed environment variables and secrets are set in the container

If `whiteboard_container` is no dictionary, merging it with the default fails before anything changes.

### Restart and updates

The server is restarted if it was running and a secret or the quadlet unit changed, otherwise it is started and enabled.
Updates of the image are done by `container_update` with `whiteboard_autoupdate_enabled: true` and `whiteboard_autoupdate_schedule`,
without `whiteboard_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

The single variables are replaced by `whiteboard_environment` and `whiteboard_secrets`:

| Former variable | Now |
|---|---|
| `whiteboard_nextcloud_url` | `NEXTCLOUD_URL` in `whiteboard_environment` |
| `whiteboard_secret` | `whiteboard_secrets` with the target `JWT_SECRET_KEY`, use the name `whiteboard_jwt_secret` to keep the existing secret |
| `whiteboard_ip`, `whiteboard_ipv6`, `whiteboard_network`, `whiteboard_hostname`, `whiteboard_timezone`, `whiteboard_labels`, `whiteboard_version`, `whiteboard_container`, `whiteboard_autoupdate_enabled` | stay |

- The secret `whiteboard_jwt_secret` was created with a fixed name, the names are set with `whiteboard_secrets` now.
- The volumes `/etc/localtime` and `/etc/timezone` are removed, the timezone is set by podman and `TZ`.
- The service is not stopped on every run anymore, `podman___update_mode` is removed, `whiteboard_autoupdate_schedule` is new.
- The tag `app_nextcloud_whiteboard` stays, the tag `app` is added.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-whiteboard-default` | Only the mandatory variables, `NEXTCLOUD_URL` and the secret `JWT_SECRET_KEY` |
| `molecule-whiteboard` | IPv6, labels, `NEXTCLOUD_URL` with a path, `COMPRESSION_ENABLED`, `MAX_UPLOAD_FILE_SIZE` and the secret `METRICS_TOKEN` |

`prepare` creates the podman network and pulls the image.
`side_effect` runs the role with `whiteboard_container` not a dictionary, a secret without `target`, no `JWT_SECRET_KEY`, an unknown secret,
`JWT_SECRET_KEY` in the environment, no `NEXTCLOUD_URL`, an invalid `NEXTCLOUD_URL`, an invalid `STORAGE_STRATEGY`, an invalid boolean,
a line break in a value and an unknown environment variable
and checks that it fails with the expected message and the quadlet unit is unchanged (tasks marked `expect ERROR`),
then it changes `METRICS_TOKEN` on `molecule-whiteboard`, the secret changes and the server has to restart.
`verify` checks the quadlet unit with the secrets as `type=env` and without their values, the service, the addresses and the environment of the container,
the home page of the server, the allowed origin of Nextcloud in `/status` and `/metrics` with the changed token and the refused former token.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd app_nextcloud_whiteboard
MOLECULE_TART_IMAGE='debian' molecule test
```
