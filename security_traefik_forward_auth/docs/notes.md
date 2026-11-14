[Traefik Forward Auth](https://github.com/thomseddon/traefik-forward-auth) runs in the container image [thomseddon/traefik-forward-auth](https://hub.docker.com/r/thomseddon/traefik-forward-auth) as podman quadlet `traefik-forward-auth`.
It is the target of a `forwardAuth` middleware of Traefik and logs users in with Google, OpenID Connect or a generic OAuth2 provider, it listens on port `4181`.

### Image

The image on Docker Hub is Traefik Forward Auth v2.2.0, `forward_auth_version` is `2` by default.
The image is not multi-arch, the tag without suffix is amd64 only, the role appends `-arm64` on aarch64 and `-arm` on armv7l.
The image is built `FROM scratch`, it contains no time zone data, the time of the log is UTC even with `TZ`.

### Configuration

```yaml
forward_auth_home: '/srv/container/forward-auth'
forward_auth_ip: '192.168.99.60'
forward_auth_network: 'podman99'
forward_auth_hostname: 'forward-auth'
forward_auth_timezone: 'Europe/Berlin'
forward_auth_environment:
  DEFAULT_PROVIDER: 'oidc'
  PROVIDERS_OIDC_ISSUER_URL: 'https://sso.example.org/application/o/forward-auth/'
  PROVIDERS_OIDC_CLIENT_ID: 'forward-auth'
  COOKIE_DOMAIN: 'example.org'
  AUTH_HOST: 'auth.example.org'
forward_auth_secrets:
  - name: 'forward_auth_secret'
    data: "{{ vault_forward_auth_secret }}"
    target: 'SECRET'
  - name: 'forward_auth_client_secret'
    data: "{{ vault_forward_auth_client_secret }}"
    target: 'PROVIDERS_OIDC_CLIENT_SECRET'
```

The options are set with `forward_auth_environment`, it is merged over the default of the role (`TZ`).
`DEFAULT_PROVIDER` is `google`, `oidc` or `generic-oauth`, `google` by default. The provider needs its variables and its client secret:

- `google`: `PROVIDERS_GOOGLE_CLIENT_ID` and the secret `PROVIDERS_GOOGLE_CLIENT_SECRET`
- `oidc`: `PROVIDERS_OIDC_ISSUER_URL`, `PROVIDERS_OIDC_CLIENT_ID` and the secret `PROVIDERS_OIDC_CLIENT_SECRET`,
  Traefik Forward Auth reads the discovery document of the issuer at the start
- `generic-oauth`: `PROVIDERS_GENERIC_OAUTH_AUTH_URL`, `..._TOKEN_URL`, `..._USER_URL`, `..._CLIENT_ID` and the secret `PROVIDERS_GENERIC_OAUTH_CLIENT_SECRET`

Traefik uses Traefik Forward Auth with a middleware, e.g. with the labels of a container:

```yaml
traefik.http.middlewares.forward-auth.forwardauth.address: 'http://forward-auth:4181'
traefik.http.middlewares.forward-auth.forwardauth.authResponseHeaders: 'X-Forwarded-User'
traefik.http.routers.app.middlewares: 'forward-auth'
```

### Secrets

The secrets are set with `forward_auth_secrets`, every entry needs `name`, `data` and `target`, `SECRET` (signs the cookies) is mandatory.
The targets are `SECRET` and the client secrets `PROVIDERS_GOOGLE_CLIENT_SECRET`, `PROVIDERS_OIDC_CLIENT_SECRET` and `PROVIDERS_GENERIC_OAUTH_CLIENT_SECRET`.

Traefik Forward Auth has no file variables, but it reads its options from configuration files in INI format, `--config` may be passed several times.
The role creates every secret with `podman secret` as configuration file with one line, the option of the target and the data,
e.g. `providers.oidc.client-secret = <data>`, mounts it to `/run/secrets/<name>` and adds `--config=/run/secrets/<name>` to the command.
So the secrets are neither part of the environment nor of a file on the host.
The data of a secret is the value of the line, it must not be empty, contain line breaks, start or end with whitespace or start with a quote.
Neither the targets nor the deprecated `COOKIE_SECRET` and `CLIENT_SECRET` may be set in `forward_auth_environment`.

### Rules

Rules are set with `forward_auth_rules`, a dictionary of the rules by their names (letters, digits, `_` and `-`).
Every rule needs `rule` (a rule of Traefik), `action` is `auth` (default) or `allow`, `provider` is the provider of the rule.
The role writes the rules to `<home>/rules.ini`, mounts it read-only to `/etc/traefik-forward-auth/rules.ini` and adds it with `--config` to the command.

```yaml
forward_auth_rules:
  health:
    action: 'allow'
    rule: 'Path(`/health`)'
  admin:
    rule: 'PathPrefix(`/admin`)'
    provider: 'oidc'
```

### Allowed variables

The role only allows the environment variables in `security_traefik_forward_auth__environment_allowed` and the secrets in `security_traefik_forward_auth__secret_options`,
it stops before any change if unknown variables or secrets are set.
This prevents unexpected behavior by accident, e.g. by a typo or a variable that has to be passed as secret.
The list is generated from `internal/config.go` and `internal/provider/*.go` of Traefik Forward Auth v2.2.0,
without `CONFIG` (the configuration files are set by the role) and the deprecated `COOKIE_DOMAINS`, `COOKIE_SECURE`, `CLIENT_ID` and `PROMPT`.
The check uses the environment of the container after merging `forward_auth_container`, so variables set with `forward_auth_container.environment` are checked as well.

### Container

Ports, volumes, additional hosts (`etc_hosts`) and dependencies (`requires`) are changed with `forward_auth_container`, it is merged over the default of the container.
The merge is not recursive, `publish`, `volumes` and `command` replace the values of the default completely,
`forward_auth_container.environment` replaces the environment including `forward_auth_environment`, use `forward_auth_environment` instead.
The default command is the list of the configuration files, the rules and one file per secret.

### Validation

The role checks before any change:

- the image exists for the architecture of the host
- `forward_auth_secrets` is a list of entries with `name`, `data` and `target` and unique names, `SECRET` is set, all targets are known
- no secret or deprecated secret is set in `forward_auth_environment`, the data of the secrets fits into a line of a configuration file
- `DEFAULT_PROVIDER` and `DEFAULT_ACTION` are valid, the default provider and the providers of the rules have their variables and client secrets
- `INSECURE_COOKIE` and `MATCH_WHITELIST_OR_DOMAIN` are `true` or `false` and no value contains a line break
- `forward_auth_rules` is a dictionary of rules with valid names, only known keys, `rule`, a valid `action` and `provider`
- only allowed environment variables are set in the container

If `forward_auth_container` or `forward_auth_environment` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Restart and updates

Traefik Forward Auth is restarted if it was running and a secret, the rules or the quadlet unit changed, otherwise it is started and enabled.
If the start fails, the role shows the journal of the service.
Afterwards the role waits up to 60 seconds until port `4181` accepts connections and shows the journal otherwise,
Traefik Forward Auth exits if the configuration or the setup of a provider fails.
Updates of the image are done by `container_update` with `forward_auth_autoupdate_enabled: true` and `forward_auth_autoupdate_schedule`,
without `forward_auth_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

| Former variable | Replacement |
|---|---|
| `forward_auth_ip`, `forward_auth_ipv6`, `forward_auth_network`, `forward_auth_hostname`, `forward_auth_timezone`, `forward_auth_labels`, `forward_auth_version`, `forward_auth_container` | Unchanged |
| `forward_auth_secret` | Entry of `forward_auth_secrets` with the target `SECRET` |
| `forward_auth_client_secret` | Entry of `forward_auth_secrets` with the target of the provider, e.g. `PROVIDERS_OIDC_CLIENT_SECRET` |
| `forward_auth_container.environment` | `forward_auth_environment` |
| `forward_auth_container.secrets` with `type=env` | Removed, the secrets of `forward_auth_secrets` are configuration files |
| Rules in `forward_auth_container.command` | `forward_auth_rules` |
| `forward_auth_version: '2-arm64'` | `forward_auth_version: '2'`, the role appends the suffix of the architecture |
| none | `forward_auth_home`, mandatory, the directory of `rules.ini` |
| none | `forward_auth_autoupdate_enabled`, `forward_auth_autoupdate_schedule` |
| `podman___update_mode` | Removed, updates are done by `container_update` |

Fixed errors and changed behavior:

- the former role created the podman secrets `forward_auth_secret` and `forward_auth_client_secret`, but never passed them to the container
- `/etc/localtime` and `/etc/timezone` are no longer mounted, the time zone is set with `forward_auth_timezone` and `TZ`
- the role chooses the tag of the image by the architecture of the host
- the environment, the secrets and the rules are checked before any change
- the role restarts Traefik Forward Auth if a secret, the rules or the quadlet unit changed and waits until it listens
- the tags are `security` and `security_traefik_forward_auth`

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root. The VMs need access to Docker Hub.

| Platform | Test case |
|---|---|
| `molecule-forward-auth-default` | Only the mandatory variables, the default provider `google` with its client ID and client secret |
| `molecule-forward-auth` | IPv6, labels, `INSECURE_COOKIE`, the provider `generic-oauth` and a rule allowing a path without login |

`prepare` creates the podman network, installs curl and pulls the image with the tag of the architecture.
`side_effect` runs the role with `forward_auth_container` not a dictionary, `forward_auth_secrets` not a list, a secret without target, duplicate names of secrets,
an unknown secret, without `SECRET`, `SECRET` and `COOKIE_SECRET` in the environment, a secret starting with whitespace,
an unknown variable and `CONFIG` in the environment, a boolean that is no boolean, a line break in a value, an unknown default provider,
the provider `oidc` without issuer and client secret, `forward_auth_rules` not a dictionary, invalid rules and a rule using a provider without configuration
and checks that it fails with the expected message and the quadlet unit and `rules.ini` are unchanged (tasks marked `expect ERROR`),
then it changes the rule on `molecule-forward-auth`, `rules.ini` changes and Traefik Forward Auth has to restart.
`verify` checks the quadlet unit without the mounts of the time zone and without secrets in the environment, the configuration files in the command,
the service, the environment and `rules.ini` and sends the requests of the middleware of Traefik:
the protected paths redirect to the login of the provider with the client ID, so `SECRET` and the client secret were read from their files,
the path of the rule is allowed without login.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd security_traefik_forward_auth
MOLECULE_TART_IMAGE='debian' molecule test
```
