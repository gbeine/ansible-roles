[OAuth2 Proxy](https://oauth2-proxy.github.io/oauth2-proxy/) runs in the container image [oauth2-proxy/oauth2-proxy](https://quay.io/repository/oauth2-proxy/oauth2-proxy) (`latest` by default) as podman quadlet `oauth2-proxy`.
It logs users in with an OAuth2 or OpenID Connect provider and either proxies the requests to the upstreams or answers the forward authentication of a reverse proxy, e.g. nginx or Traefik.
It listens on port `4180`, `/ping` answers if it runs.

### Configuration

```yaml
oauth2_proxy_home: '/srv/container/oauth2-proxy'
oauth2_proxy_ip: '192.168.99.61'
oauth2_proxy_network: 'podman99'
oauth2_proxy_hostname: 'oauth2-proxy'
oauth2_proxy_timezone: 'Europe/Berlin'
oauth2_proxy_config:
  provider: 'oidc'
  provider_display_name: 'Authentik'
  oidc_issuer_url: 'https://sso.example.org/application/o/oauth2-proxy/'
  client_id: 'oauth2-proxy'
  redirect_url: 'https://auth.example.org/oauth2/callback'
  code_challenge_method: 'S256'
  scope: 'openid email profile'
  email_domains: [ '*' ]
  cookie_domains: [ '.example.org' ]
  whitelist_domains: [ '.example.org' ]
  reverse_proxy: true
  set_xauthrequest: true
oauth2_proxy_secrets:
  - name: 'oauth2_proxy_cookie_secret'
    data: "{{ vault_oauth2_proxy_cookie_secret }}"
    target: 'OAUTH2_PROXY_COOKIE_SECRET'
  - name: 'oauth2_proxy_client_secret'
    data: "{{ vault_oauth2_proxy_client_secret }}"
    target: 'OAUTH2_PROXY_CLIENT_SECRET'
```

`oauth2_proxy_config` contains the options of the [configuration file](https://oauth2-proxy.github.io/oauth2-proxy/configuration/overview) of OAuth2 Proxy,
the role writes it to `<home>/oauth2-proxy.cfg`, mounts it read-only to `/etc/oauth2-proxy/oauth2-proxy.cfg` and starts OAuth2 Proxy with `--config`.
The configuration file is TOML, the values are written by their type:

- a string as quoted string, a number as number
- a boolean as `true` or `false`, `false` is a value of an option and does not remove it
- a list as array of strings, e.g. `upstreams` or `email_domains`
- `null` removes the option

The role sets `http_address` to `:4180`, OAuth2 Proxy listens on `127.0.0.1:4180` by default and could not be reached from the network.
`client_id` and `email_domains`, `authenticated_emails_file` or `htpasswd_file` are mandatory, the provider `oidc` needs `oidc_issuer_url`.
The default provider of OAuth2 Proxy is `google`.

### Secrets

The secrets are set with `oauth2_proxy_secrets`, every entry needs `name`, `data` and `target`.
`OAUTH2_PROXY_COOKIE_SECRET` encrypts the sessions, it needs 16, 24 or 32 characters or their URL-safe base64 encoding,
e.g. `openssl rand -base64 32 | tr -- '+/' '-_'`.
`OAUTH2_PROXY_CLIENT_SECRET` is mandatory except for the providers `login.gov` and `entra-id` with `entra_id_federated_token_auth`.

OAuth2 Proxy reads the client secret, the cookie secret and the private key for signed JWTs from files,
the secrets with the targets `OAUTH2_PROXY_CLIENT_SECRET`, `OAUTH2_PROXY_COOKIE_SECRET` and `OAUTH2_PROXY_JWT_KEY` are mounted to `/run/secrets/<name>`,
the role sets `OAUTH2_PROXY_CLIENT_SECRET_FILE`, `OAUTH2_PROXY_COOKIE_SECRET_FILE` and `OAUTH2_PROXY_JWT_KEY_FILE`.

OAuth2 Proxy has no file variant for `redis_password`, `redis_sentinel_password`, `basic_auth_password`, `github_token` and `signature_key`,
the secrets with the targets `OAUTH2_PROXY_REDIS_PASSWORD`, `OAUTH2_PROXY_REDIS_SENTINEL_PASSWORD`, `OAUTH2_PROXY_BASIC_AUTH_PASSWORD`,
`OAUTH2_PROXY_GITHUB_TOKEN` and `OAUTH2_PROXY_SIGNATURE_KEY` are passed in the environment of the container (`type=env`).

The secrets are never part of the configuration file or of `oauth2_proxy_environment`,
the options of the secrets and their files (e.g. `client_secret`, `cookie_secret_file`) must not be set in `oauth2_proxy_config`.

### Allowed variables

The options of `oauth2_proxy_config` are checked against `security_oauth2_proxy__config_allowed`,
generated from the options of `pkg/apis/options/*.go` of OAuth2 Proxy v7.15.6 without the secrets and `http_address`.
The environment of the container only contains `TZ` and the file variables of the secrets, the options are set with `oauth2_proxy_config`,
the targets of the secrets are checked against `security_oauth2_proxy__secret_files` and `security_oauth2_proxy__secrets_env`.
The role stops before any change if unknown options, variables or secrets are set.
This prevents unexpected behavior by accident, e.g. by a typo or a secret written to the configuration file.
The check of the environment uses the environment of the container after merging `oauth2_proxy_container`.

### Container

Ports, volumes, additional hosts (`etc_hosts`) and dependencies (`requires`) are changed with `oauth2_proxy_container`, it is merged over the default of the container.
The merge is not recursive, `publish`, `volumes` and `command` replace the values of the default completely,
files referenced by options, e.g. `htpasswd_file` or `custom_templates_dir`, are mounted with `oauth2_proxy_container.volumes` together with the configuration file.

```yaml
oauth2_proxy_container:
  volumes:
    - '/srv/container/oauth2-proxy/oauth2-proxy.cfg:/etc/oauth2-proxy/oauth2-proxy.cfg:ro'
    - '/srv/container/oauth2-proxy/htpasswd:/etc/oauth2-proxy/htpasswd:ro'
```

### Validation

The role checks before any change:

- `oauth2_proxy_secrets` is a list of entries with `name`, `data` and `target` and unique names, all targets are known
- `oauth2_proxy_config` is a dictionary of known options with strings, numbers, booleans, `null` or lists of them without line breaks,
  without secrets and without `http_address`, with `client_id` and the email validation, `oidc` with `oidc_issuer_url`
- the cookie secret and the client secret are set, the cookie secret has a valid length, no secret contains a line break
- no secret or file variable is set in `oauth2_proxy_environment` and no value contains a line break
- only allowed environment variables are set in the container

If `oauth2_proxy_container` or `oauth2_proxy_environment` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Restart and updates

OAuth2 Proxy is restarted if it was running and a secret, the configuration or the quadlet unit changed, otherwise it is started and enabled.
If the start fails, the role shows the journal of the service.
Afterwards the role waits up to 60 seconds until `/ping` answers and shows the journal otherwise, OAuth2 Proxy exits if the configuration is invalid.
Updates of the image are done by `container_update` with `oauth2_proxy_autoupdate_enabled: true` and `oauth2_proxy_autoupdate_schedule`,
without `oauth2_proxy_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

| Former variable | Replacement |
|---|---|
| `oauth2_proxy_home`, `oauth2_proxy_ip`, `oauth2_proxy_ipv6`, `oauth2_proxy_network`, `oauth2_proxy_hostname`, `oauth2_proxy_timezone`, `oauth2_proxy_labels`, `oauth2_proxy_version`, `oauth2_proxy_container` | Unchanged |
| `oauth2_proxy_http_address`, `oauth2_proxy_http_port` | Removed, the role sets `http_address` to `:4180`, other ports are published with `oauth2_proxy_container.publish` |
| `oauth2_proxy_cookie_secret` | Entry of `oauth2_proxy_secrets` with the target `OAUTH2_PROXY_COOKIE_SECRET` |
| `oauth2_proxy_client_secret` | Entry of `oauth2_proxy_secrets` with the target `OAUTH2_PROXY_CLIENT_SECRET` |
| `oauth2_proxy_email_domains`, `oauth2_proxy_upstreams`, `oauth2_proxy_cookie_domains`, `oauth2_proxy_whitelist_domains` | `email_domains`, `upstreams`, `cookie_domains`, `whitelist_domains` of `oauth2_proxy_config`, lists |
| `oauth2_proxy_client_id`, `oauth2_proxy_redirect_url`, `oauth2_proxy_oidc_issuer_url`, `oauth2_proxy_provider`, `oauth2_proxy_provider_display_name`, `oauth2_proxy_skip_provider_button`, `oauth2_proxy_code_challenge_method` | The options of the same name of `oauth2_proxy_config` |
| `oauth2_proxy_scope` | `scope` of `oauth2_proxy_config`, a string with the scopes separated by spaces |
| `oauth2_proxy_set_xauthrequest`, `oauth2_proxy_set_authorization_header`, `oauth2_proxy_pass_access_token`, `oauth2_proxy_pass_authorization_header`, `oauth2_proxy_pass_user_headers` | The options of the same name of `oauth2_proxy_config` |
| `oauth2_proxy_reverse_proxy`, `oauth2_proxy_cookie_secure`, `oauth2_proxy_cookie_path`, `oauth2_proxy_cookie_name`, `oauth2_proxy_cookie_httponly`, `oauth2_proxy_cookie_samesite` | The options of the same name of `oauth2_proxy_config` |
| none | `oauth2_proxy_environment`, `oauth2_proxy_autoupdate_enabled`, `oauth2_proxy_autoupdate_schedule` |
| `podman___update_mode` | Removed, updates are done by `container_update` |

The defaults of the former role (`cookie_secure`, `cookie_httponly`, `cookie_path`, `cookie_name`, `pass_user_headers` and the booleans set to `false`)
are the defaults of OAuth2 Proxy, they are not written anymore.

Fixed errors and changed behavior:

- the cookie secret and the client secret were written in plain text to the configuration file on the host, they are podman secrets now
- `pass_user_headers` was read from `oauth2_proxy_pass_access_token`
- `provider_display_name` was left out with `skip_provider_button`, now every option is written as set
- an empty `cookie_samesite` was written, now only options set in `oauth2_proxy_config` are written
- `/etc/localtime` and `/etc/timezone` are no longer mounted, the time zone is set with `oauth2_proxy_timezone` and `TZ`
- the configuration, the secrets and the environment are checked before any change
- the role restarts OAuth2 Proxy if a secret, the configuration or the quadlet unit changed and waits until it answers, the handler is removed
- the tags are `security` and `security_oauth2_proxy`

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root. The VMs need access to quay.io.

| Platform | Test case |
|---|---|
| `molecule-oauth2-proxy-default` | Only the mandatory variables, the default provider `google` and a cookie secret of 32 characters |
| `molecule-oauth2-proxy` | IPv6, labels, OpenID Connect without discovery, an upstream, a cookie secret in base64 and the signature key passed in the environment |

`prepare` creates the podman network, installs curl and pulls the image.
`side_effect` runs the role with `oauth2_proxy_container` not a dictionary, `oauth2_proxy_secrets` not a list, a secret without target, duplicate names of secrets,
an unknown secret, without cookie secret and without client secret, a cookie secret of the wrong length, a secret and a file variable in the environment,
an unknown environment variable, `oauth2_proxy_config` not a dictionary, unknown options, secrets and options of the role in the configuration,
a dictionary and a line break as values, without client ID and email domains and the provider `oidc` without issuer
and checks that it fails with the expected message and the quadlet unit and the configuration are unchanged (tasks marked `expect ERROR`),
then it changes the name of the cookie on `molecule-oauth2-proxy`, the configuration changes and OAuth2 Proxy has to restart.
`verify` checks the quadlet unit without the mounts of the time zone, the secrets as files and in the environment, the service,
that the environment only contains the file variables of the client and the cookie secret, the configuration without secrets,
that `/ping` answers, that `/oauth2/start` redirects to the login of the provider with the client ID,
so the client secret and the cookie secret were read from their files, and that `/oauth2/auth` without session answers 401.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd security_oauth2_proxy
MOLECULE_TART_IMAGE='debian' molecule test
```
