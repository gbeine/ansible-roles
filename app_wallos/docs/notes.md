[Wallos](https://wallosapp.com/) runs in the container image [bellamy/wallos](https://hub.docker.com/r/bellamy/wallos) (`latest` by default) as podman quadlet `wallos`.
The image runs nginx and PHP-FPM, it serves HTTP on port `80`, TLS is terminated by a reverse proxy, e.g. Traefik.
Wallos stores its SQLite database in `<home>/db` and the uploaded logos in `<home>/logos`.

### Configuration

```yaml
wallos_home: '/srv/container/wallos'
wallos_ip: '192.168.99.50'
wallos_network: 'podman99'
wallos_hostname: 'wallos'
wallos_timezone: 'Europe/Berlin'
wallos_admin:
  username: 'admin'
  email: 'admin@example.org'
  password: "{{ vault_wallos_admin_password }}"
  language: 'de'
  currency: 'EUR'
wallos_labels:
  traefik.enable: 'true'
  traefik.http.routers.wallos.rule: 'Host(`wallos.example.org`)'
  traefik.http.services.wallos.loadbalancer.server.port: 80
```

Without users Wallos lets the first visitor register and makes this user the administrator.
The role creates the administrator `wallos_admin` before anybody else can register, afterwards the registration of Wallos is closed
until the administrator opens it on the administration page.
`wallos_admin` needs `username`, `email` and `password`, `language` (`en` by default) and `currency` (`EUR` by default)
are the language and the main currency of the administrator, they are only used when the administrator is registered.

The module `app_wallos_admin` of the role runs PHP in the container as `www-data`, the user of PHP-FPM, and passes the values on stdin.
The image creates the database as root at every start and hands it to `www-data` after the migrations,
`/health.php` answers before, so the module waits until `www-data` may write the database:

- without users it sends the registration form of Wallos inside the container to `http://127.0.0.1/registration.php`,
  so Wallos creates the administrator with its household and default names and the password does not leave the container
- with users the user with the id 1 is the administrator, the module checks the password with `password_verify`
  and only changes the username, the email or the password if they differ

The environment is set with `wallos_environment`, it is merged over the default of the role (`TZ`).
Wallos reads `TZ` for its cron jobs, `SSRF_ALLOWLIST` (hosts allowed for webhooks, it overrides the setting of the administration page)
and the `OIDC_*` variables for the login with OpenID Connect, variables set in the environment cannot be changed on the administration page.
`startup.sh` of the image sets the user `www-data` to `PUID` and `PGID` (82 by default) and owns the database and the logos by it,
the role creates `<home>/db` and `<home>/logos` with the same IDs.

```yaml
wallos_environment:
  PUID: 1000
  PGID: 1000
  OIDC_ENABLED: true
  OIDC_PROVIDER_NAME: 'Authentik'
  OIDC_CLIENT_ID: 'wallos'
  OIDC_ISSUER: 'https://sso.example.org/application/o/wallos/'
  OIDC_REDIRECT_URL: 'https://wallos.example.org/'
  OIDC_USER_IDENTIFIER: 'preferred_username'
  OIDC_SCOPES: 'openid email profile'
wallos_secrets:
  - name: 'wallos_oidc_client_secret'
    data: "{{ vault_wallos_oidc_client_secret }}"
    target: 'OIDC_CLIENT_SECRET'
```

With `OIDC_ISSUER` Wallos reads the URLs of the provider from its discovery document,
otherwise `OIDC_AUTH_URL`, `OIDC_TOKEN_URL` and `OIDC_USERINFO_URL` are needed.

### Secrets

The secrets are set with `wallos_secrets`, every entry needs `name`, `data` and `target`, the only allowed target is `OIDC_CLIENT_SECRET`.
The role creates every entry with `podman secret` and mounts it to `/run/secrets/<name>`,
the file variable `OIDC_CLIENT_SECRET_FILE` points to it, Wallos reads the client secret from the file.
Neither the target nor the file variable may be set in `wallos_environment`.
The administrator of Wallos sees the client secret on the administration page.

### Allowed variables

The role only allows the environment variables in `app_wallos__environment_allowed` and the secrets in `app_wallos__secret_files`,
it stops before any change if unknown variables or secrets are set.
This prevents unexpected behavior by accident, e.g. by a typo or a variable that has to be passed as secret.
The lists are generated from `startup.sh`, `endpoints/cronjobs/settimezone.php`, `includes/oidc_settings.php` and `includes/ssrf_helper.php` of Wallos v5.11.1.
`DEMO_MODE` is not allowed, it turns the instance into a demo.
The check uses the environment of the container after merging `wallos_container`, so variables set with `wallos_container.environment` are checked as well.

### Container

Ports, volumes, additional hosts (`etc_hosts`) and dependencies (`requires`) are changed with `wallos_container`, it is merged over the default of the container.
The merge is not recursive, `publish` and `volumes` replace the values of the default completely,
`wallos_container.environment` replaces the environment including `wallos_environment` and the file variables of the secrets, use `wallos_environment` instead.

### Validation

The role checks before any change:

- `wallos_secrets` is a list of entries with `name`, `data` and `target` and unique names, only `OIDC_CLIENT_SECRET` is a target
- no secret, file variable of a secret or secret with line breaks is set in `wallos_environment`
- `PUID` and `PGID` are numbers
- the `OIDC_*` booleans are `true` or `false` and no value contains a line break
- `wallos_admin` is a dictionary with `username` (letters, digits, `.`, `_`, `@` and `-`), a valid `email`, a `password` without line breaks
  and a `language` and `currency` known by Wallos
- only allowed environment variables are set in the container

If `wallos_container` or `wallos_environment` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Restart and updates

Wallos is restarted if it was running and a secret or the quadlet unit changed, otherwise it is started and enabled.
If the start fails, the role shows the journal of the service.
Afterwards the role waits up to 120 seconds until `/health.php` answers and shows the journal if Wallos does not answer.
Updates of the image are done by `container_update` with `wallos_autoupdate_enabled: true` and `wallos_autoupdate_schedule`,
without `wallos_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

| Former variable | Replacement |
|---|---|
| `wallos_home`, `wallos_ip`, `wallos_ipv6`, `wallos_network`, `wallos_hostname`, `wallos_timezone`, `wallos_labels`, `wallos_version`, `wallos_container`, `wallos_autoupdate_enabled` | Unchanged |
| `wallos_secrets` with `type=env` | `wallos_secrets` with the target `OIDC_CLIENT_SECRET`, mounted as file |
| `wallos_container.environment` | `wallos_environment` |
| `podman___update_mode` | Removed, updates are done by `container_update` |
| none | `wallos_admin`, mandatory |
| none | `wallos_environment`, `wallos_autoupdate_schedule` |

Changed behavior:

- `/etc/localtime` and `/etc/timezone` are no longer mounted, the time zone is set with `wallos_timezone` and `TZ`,
  the quadlet unit changes once and Wallos restarts, volumes in `wallos_container` should no longer contain them
- the role creates the administrator, the first visitor cannot become the administrator anymore;
  an existing administrator (the user with the id 1) gets the username, the email and the password of `wallos_admin`
- the owner of `<home>/db` and `<home>/logos` follows `PUID` and `PGID`, the mode is `0755` instead of `0700`,
  the image sets both at every start anyway
- the environment and the secrets are checked against the allowed variables, secrets are passed as files instead of the environment
- the role no longer pulls the image and recreates the container, it restarts Wallos only if a secret or the quadlet unit changed
- the role waits until Wallos answers and shows the journal if the start fails
- the tags are `app` and `app_wallos`

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root. The VMs need access to Docker Hub.

| Platform | Test case |
|---|---|
| `molecule-wallos-default` | Only the mandatory variables, the administrator with the default language and currency |
| `molecule-wallos` | IPv6, labels, `PUID` and `PGID` 1000, the login with OIDC and the client secret as file, an administrator with language and currency |

`prepare` creates the podman network, installs curl and pulls the image.
`side_effect` runs the role with `wallos_container` not a dictionary, `wallos_secrets` not a list, a secret without target, duplicate names of secrets,
an unknown secret, a secret and its file variable in the environment, a secret with a line break, `PUID` not a number,
an unknown variable in `wallos_environment` and in `wallos_container.environment`, a boolean that is no boolean, a line break in a value,
`wallos_admin` not a dictionary, without password, with an invalid username and email and with an unknown key, language and currency
and checks that it fails with the expected message and the quadlet unit is unchanged (tasks marked `expect ERROR`),
then it changes the client secret and the password of the administrator on `molecule-wallos`, the secret changes, Wallos has to restart
and the module has to set the password.
`verify` checks the quadlet unit without the mounts of the time zone and without secrets in the environment, the service, the environment,
the owners of the directories and of the database, that `/health.php` answers, that the registration is closed,
logs in as the administrator with the current password and opens the administration page.
On `molecule-wallos` it checks that the login page offers the login with OIDC, so the variables reach PHP-FPM,
and that the administration page shows the changed client secret read from the file.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd app_wallos
MOLECULE_TART_IMAGE='debian' molecule test
```
