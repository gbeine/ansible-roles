Dozzle runs in the container image [amir20/dozzle](https://hub.docker.com/r/amir20/dozzle) (`latest` by default, `dozzle_version` sets the tag) as podman quadlet.
It shows the logs of the containers of the host in the browser, it reads them with the Docker API of podman,
the socket `/run/podman/podman.sock` is mounted as `/var/run/docker.sock`. The socket is enabled by `container_podman` (`podman_socket_enabled`).
Dozzle listens on port 8080 and keeps its users (`users.yml`), the key of its sessions and the settings of its setup wizard in `<dozzle_home>/data`, mounted as `/data`.
The image is built from `scratch`, it contains no shell and runs as root.

### Configuration

Dozzle is configured with environment variables in `dozzle_environment`, merged over the default of the role.
Booleans may be given as YAML booleans, the role passes them as `true` or `false`.
The variables are described in the [documentation of Dozzle](https://dozzle.dev/guide/supported-env-vars).

The default sets `TZ` to `dozzle_timezone`, `DOZZLE_AUTH_PROVIDER` to `simple`, `DOZZLE_NO_ANALYTICS` to `true`,
`DOZZLE_ENABLE_ACTIONS` and `DOZZLE_ENABLE_SHELL` to `false` and `DOZZLE_AUTO_UPDATE` and `DOZZLE_AUTO_CLEANUP` to `off`.
Settings set by a variable are locked, the file `dozzle.yml` written by the setup wizard cannot change them,
so nobody can enable the actions, the shell or the updates of the containers in the web interface.
The image of Dozzle is updated by `container_update`, not by Dozzle itself.

The role sets `DOZZLE_DISABLE_SETUP_WIZARD` to `true`, `DOZZLE_MODE` to `server` and `DOZZLE_ADDR` to `:8080`, they must not be set in `dozzle_environment`.
Without login anybody may create an account with the setup wizard of a new installation,
swarm and k8s do not exist with podman and the port is changed with `dozzle_container.publish`.

```yaml
dozzle_environment:
  DOZZLE_HOSTNAME: 'server.example.org'
  DOZZLE_ENABLE_ACTIONS: true
  DOZZLE_FILTER: 'label=com.example.logs'
```

The login is mandatory, `DOZZLE_AUTH_PROVIDER` has to be one of:

- `simple`, the users are set with `dozzle_users`, Dozzle keeps them in `users.yml`
- `oidc`, the identity provider knows the users, it needs `DOZZLE_AUTH_OIDC_ISSUER`, `DOZZLE_AUTH_OIDC_CLIENT_ID` and the secret `DOZZLE_AUTH_OIDC_CLIENT_SECRET`
- `forward-proxy`, a proxy like Authelia authenticates the users and passes them in headers,
  Dozzle trusts these headers, so it must only be reachable through the proxy and must not be published

`none`, `github` and `google` are not allowed, the login with GitHub uses `simple` with `DOZZLE_AUTH_GITHUB_CLIENT_ID`,
the secret `DOZZLE_AUTH_GITHUB_CLIENT_SECRET` and users with `github` in `dozzle_users`.

### Users

`dozzle_users` is a dictionary of the users by the names they log in with, each user has these keys:

| Key | Description |
|---|---|
| `name` | The name shown by Dozzle |
| `email` | The email, used for the avatar |
| `password` | The password, 8 to 72 characters, bcrypt only uses 72 bytes |
| `github` | The login at GitHub, a user with it needs no password |
| `filter` | The filter of the containers the user may see, e.g. `label=com.example.app` |
| `roles` | A list of `shell`, `actions`, `update`, `download`, `notifications`, `cloud`, `all` and `none`, `^` excludes a role, all roles if empty |

```yaml
dozzle_users:
  admin:
    name: 'Admin'
    email: 'admin@example.org'
    password: "{{ vault_dozzle_admin_password }}"
  guest:
    name: 'Guest'
    password: "{{ vault_dozzle_guest_password }}"
    filter: 'label=com.example.app'
    roles: [ 'none' ]
```

The module `monitoring_dozzle_users` writes `users.yml` with all users of `dozzle_users`, users missing there are removed.
It keeps the bcrypt hash of a password if it matches the password and hashes new passwords with the cost of Dozzle (11),
so the file only changes if a user or a password changes. The passwords are an option with `no_log`.
The file is written as JSON, which is valid YAML, it belongs to root with the mode `0600`.
Dozzle reads the file again when it changes, a changed user needs no restart.
The role installs `python3-bcrypt` for the module. Without `dozzle_users` and with another provider than `simple` the role writes no `users.yml`.

### Secrets

`dozzle_secrets` is a list of podman secrets with `name`, `data` and `target`, the usual name of the variable.

- `DOZZLE_AUTH_OIDC_CLIENT_SECRET` and `DOZZLE_AUTH_GITHUB_CLIENT_SECRET` are mounted as `/run/secrets/<name>`,
  the role sets their file variables `DOZZLE_AUTH_OIDC_CLIENT_SECRET_FILE` and `DOZZLE_AUTH_GITHUB_CLIENT_SECRET_FILE`.
- `DOZZLE_MCP_TOKEN`, the token of the MCP endpoint (`DOZZLE_ENABLE_MCP`), is passed in the environment with `type=env,target=DOZZLE_MCP_TOKEN`.
  Dozzle only reads the secrets of the logins from files (`fileBackedEnvNames` in `internal/cli/secrets.go`), not the token of MCP.
  The token needs at least 32 characters without whitespace.

No target and no file variable may be set in `dozzle_environment`.

```yaml
dozzle_secrets:
  - name: 'dozzle_oidc_client_secret'
    data: "{{ vault_dozzle_oidc_client_secret }}"
    target: 'DOZZLE_AUTH_OIDC_CLIENT_SECRET'
```

### Allowed variables

The role only allows the environment variables in `monitoring_dozzle__environment_allowed` and the secrets listed above,
it stops before any change if unknown variables or secrets are set.
This prevents unexpected behavior by accident, e.g. by a typo or a variable that has to be passed as secret, Dozzle itself only warns about unknown variables.
The check uses the environment and the secrets of the container after merging `dozzle_container`.
The list is generated from the `env` tags of `internal/cli/args.go` of Dozzle v11.4.3 without the secrets,
`DOZZLE_NAMESPACE` of k8s and `DOZZLE_CERT` and `DOZZLE_KEY` of the agents, new versions of the image may add variables.

### Container

Ports, volumes, additional hosts (`etc_hosts`) and dependencies (`requires`) are changed with `dozzle_container`, it is merged over the default of the container.
The merge is not recursive, `dozzle_container.environment` replaces the environment including `dozzle_environment`, use `dozzle_environment` instead,
`dozzle_container.volumes` replaces the data directory and the socket.
For a reverse proxy, e.g. Traefik, the labels are set with `dozzle_labels`.
The directories belong to root with the mode `0750`.

### Validation

The role checks before any change:

- `dozzle_secrets` is a list of entries with `name`, `data` and `target` and unique names
- `DOZZLE_AUTH_PROVIDER` is `simple`, `oidc` or `forward-proxy`, `simple` has users, `oidc` has its variables and its secret
- no secret, no file variable of a secret and no variable set by the role is set in `dozzle_environment`
- the token of MCP has at least 32 characters without whitespace
- values contain no line breaks, booleans are `true` or `false`
- the users have valid names, known keys, passwords of 8 to 72 characters or a login at GitHub, valid emails, known roles and no line breaks
- only allowed environment variables and secrets are set in the container

If `dozzle_container` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Restart and updates

Dozzle is restarted if it was running and a secret or the quadlet unit changed, e.g. after changing `dozzle_environment`,
otherwise it is started and enabled. Changed users need no restart. If the start fails, the role shows the journal of the service.
Afterwards the role waits up to 120 seconds for `/healthcheck` and shows the journal if Dozzle does not answer.
Updates of the image are done by `container_update` with `dozzle_autoupdate_enabled: true` and `dozzle_autoupdate_schedule`,
without `dozzle_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

The role is new, there are no former variables.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root. The VMs need access to Docker Hub.

| Platform | Test case |
|---|---|
| `molecule-dozzle-default` | Only the mandatory variables and one user |
| `molecule-dozzle` | IPv6, labels, `DOZZLE_HOSTNAME`, `DOZZLE_LEVEL`, MCP with its token as secret and a guest with a filter |

`prepare` creates the podman network with the socket, installs `curl` and `python3-bcrypt`, pulls the images
and starts the container `molecule-logger`, which writes a line every two seconds.
`side_effect` runs the role with `dozzle_container` not a dictionary, a secret without `target`, without login, the provider `simple` without users,
OIDC without issuer, the token of MCP in the environment, `DOZZLE_MODE` in the environment, a short token of MCP, an unknown variable, an unknown secret,
an invalid boolean, a line break in a value, a short password and an unknown role of a user
and checks that it fails with the expected message and the quadlet unit and `users.yml` are unchanged (tasks marked `expect ERROR`),
then it changes `DOZZLE_LEVEL` and the password of the administrator on `molecule-dozzle`, the quadlet unit and `users.yml` change and Dozzle has to restart.
`verify` checks the quadlet unit with the socket and the secret without its value, the service, the addresses and the environment,
`users.yml` with its mode, the bcrypt hashes matching the passwords and no password in plain text, the health check,
the login with the passwords (200), a wrong one and the former one (401), the version with and without session (401)
and that the stream of the events of the administrator contains `molecule-logger`, the guest with its filter does not see it.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd monitoring_dozzle
MOLECULE_TART_IMAGE='debian' molecule test
```
