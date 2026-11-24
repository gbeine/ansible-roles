Readeck runs in the container image [readeck/readeck](https://codeberg.org/readeck/-/packages/container/readeck) (`latest` by default) as podman quadlet,
the web interface and the API listen on port 8000.
The role runs Readeck as UID and GID 1000, the image would run it as root.
Below `readeck_home` the role creates `config.toml` (mounted read only to `/etc/readeck/config.toml`) and `data` (mounted to `/readeck`,
the volume and working directory of the image). Readeck keeps the SQLite database, the bookmarks and the content scripts in `data/data`.

The role creates no users, the first user is created in the onboarding of the web interface,
with `podman exec -it readeck /bin/readeck user -config /etc/readeck/config.toml -u <user>` or by a provider of OIDC with `provisioning`.

### Configuration

Readeck is configured with its configuration file `config.toml`, the options are set in `readeck_config`, merged recursively over the default of the role.
The default is empty, everything not set uses the defaults of Readeck, see the [documentation](https://readeck.org/en/docs/configuration).
The keys are the sections of `config.toml` (`main`, `server`, `auth`, `email`, `accounts`, `extractor`, `bookmarks`, `worker`, `metrics`, `customize`)
with their options, `server.session` and `auth.oidc` are sections below `server` and `auth`.
TOML is typed: booleans are YAML booleans, numbers are numbers, lists are lists, `null` removes a section or an option.

```yaml
readeck_config:
  main:
    log_level: 'WARN'
  server:
    base_url: 'https://readeck.example.org/'
    trusted_proxies: [ '10.89.0.0/24' ]
  email:
    host: 'mail.example.org'
    port: 587
    username: 'readeck'
    encryption: 'starttls'
    from: 'readeck@example.org'
  extractor:
    workers: 2
```

The role fixes some options: `main.data_directory` stays `data` (below the volume `/readeck`), the image sets `READECK_SERVER_HOST` to `0.0.0.0`,
it takes precedence over `server.host`, and the port is the port of the container, 8000. These options must not be set in `readeck_config`.
The time zone of the container is `readeck_timezone`, the image sets no `TZ`.

### Options with keys

Readeck composes the variables of the providers of OIDC from their position in the list `auth.oidc.providers`:
the client secret of the provider `<n>` (counted from 0) is `READECK_AUTH_OIDC_PROVIDERS_<n>_CLIENT_SECRET`.
The role generates the allowed targets of `readeck_secrets` from the list, every provider needs its client secret.

| Option | Generated target of the secret |
|---|---|
| `auth.oidc.providers[<n>].client_secret` | `READECK_AUTH_OIDC_PROVIDERS_<n>_CLIENT_SECRET` |

```yaml
readeck_config:
  auth:
    oidc:
      providers:
        - name: 'Keycloak'
          url: 'https://sso.example.org/realms/main'
          client_id: 'readeck'
          # Pairs of a group of the provider and a group of Readeck (user, staff, admin)
          groups: [ [ 'readeck-admins', 'admin' ], [ 'readeck-users', 'user' ] ]
          provisioning: true
readeck_secrets:
  - name: 'readeck_secret_key'
    data: "{{ vault_readeck_secret_key }}"
    target: 'READECK_SECRET_KEY'
  - name: 'readeck_oidc_client_secret'
    data: "{{ vault_readeck_oidc_client_secret }}"
    target: 'READECK_AUTH_OIDC_PROVIDERS_0_CLIENT_SECRET'
```

The redirect URI of the client at the provider is `<base_url>login/oidc`, set `server.base_url` to the public URL of Readeck.

### Secrets

`readeck_secrets` is a list of podman secrets with `name`, `data` and `target`, the target is the variable of Readeck.
The configuration file cannot read files and Readeck has no file variables (`internal/configs/configs.go` of Readeck 0.23.6),
so the secrets are passed in the environment of the container with `type=env,target=<target>`.
Readeck reads the environment after the configuration file, the environment takes precedence, and removes the variables of the secrets
from its environment after reading them. The secrets are neither part of `config.toml` nor of the quadlet unit.

| Target | Option of `config.toml` |
|---|---|
| `READECK_SECRET_KEY` | `main.secret_key`, mandatory |
| `READECK_DATABASE_SOURCE` | `database.source`, e.g. `postgres://readeck:<password>@postgresql:5432/readeck`, SQLite in `data/db.sqlite3` without it |
| `READECK_MAIL_PASSWORD` | `email.password` |
| `READECK_WORKER_DSN` | `worker.dsn`, e.g. `redis://:<password>@redis:6379/0`, the worker runs in memory without it |
| `READECK_AUTH_OIDC_PROVIDERS_<n>_CLIENT_SECRET` | `client_secret` of the provider `<n>` of `auth.oidc.providers` |

Without a secret key Readeck writes a new configuration file with a generated key, so `READECK_SECRET_KEY` is mandatory
and the configuration file is mounted read only. The secret key signs the sessions and encrypts data in the database, keep it.
None of the targets may be set in `readeck_environment`, their options not in `readeck_config`.

### Allowed variables

The role only allows the options in `app_readeck__config_allowed` and the fields of a provider in `app_readeck__oidc_allowed`,
the environment variables in `app_readeck__environment_allowed` (`TZ`) and the secrets listed above,
it stops before any change if unknown options, variables or secrets are set.
This prevents unexpected behavior by accident, e.g. by a typo or an option that has to be passed as secret, Readeck itself ignores unknown options.
The options are generated from the fields of `config` and its sections in `internal/configs/configs.go` of Readeck 0.23.6
without the secrets and the options fixed by the role, new versions of the image may add options.
The options of Readeck are not set with `READECK_*` in the environment, they are unknown variables of `readeck_environment`.
`readeck_environment` has no default, without it the quadlet unit has no environment and nothing is checked.
The check of the environment and the secrets uses the container after merging `readeck_container`.

### Container

Ports, volumes, additional hosts (`etc_hosts`), the user and the dependencies are changed with `readeck_container`, it is merged over the default of the container.
The dependencies of the quadlet unit are lists: `requires`, `wants`, `after`, `part_of` and `binds_to` are units,
`requires_mounts_for` are paths. They are written to `[Unit]` as `Requires=`, `Wants=`, `After=`, `PartOf=`, `BindsTo=` and `RequiresMountsFor=`.
The merge is not recursive, `readeck_container.volumes` replaces the data directory and the configuration file,
`readeck_container.command` the start with the configuration file.
The data directory belongs to UID and GID 1000 with the mode `0750`, another `user` in `readeck_container` needs the owner of the directory changed.
For a reverse proxy, e.g. Traefik, the labels are set with `readeck_labels`.

```yaml
readeck_container:
  requires: [ 'postgresql.service' ]
  after: [ 'postgresql.service' ]
```

### Validation

The role checks before any change:

- `readeck_secrets` is a list of entries with `name`, `data` and `target` and unique names
- `readeck_config` is a dictionary with only allowed options, no secrets and no options fixed by the role,
  booleans are YAML booleans, numbers are numbers, strings contain no line breaks
- `auth.oidc.providers` is a list of providers with `name`, `url` and `client_id`, only the allowed fields, `provisioning` is a boolean,
  `groups` a list of pairs of strings, no `client_secret`
- the secret `READECK_SECRET_KEY` and the client secret of every provider are set, secrets are not empty and contain no line breaks,
  no secret is set in `readeck_environment`
- only allowed environment variables without line breaks and allowed secrets are set in the container

If `readeck_container` or `readeck_config` is no dictionary, merging it fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Check mode

The role runs with `--check`, also on a host where it never ran, and reports the directories, the configuration file, the secrets and the quadlet unit.
The start and the wait for Readeck do not run in check mode.

### Restart and updates

Readeck is restarted if it was running and the configuration file, a secret or the quadlet unit changed,
otherwise it is started and enabled. If the start fails, the role shows the error and the journal of the service.
Afterwards the role asks `/api/info` up to 60 times every 2 seconds, each request waits at most 5 seconds,
and shows the journal if Readeck is not available. With `server.cert_file` Readeck answers with TLS, the role asks with `https` then.
Updates of the image are done by `container_update` with `readeck_autoupdate_enabled: true` and `readeck_autoupdate_schedule`,
without `readeck_autoupdate_schedule` the schedule of `container_update` is used. Readeck migrates its database on the start.

### Migration

The role is new, there are no former variables. An existing installation of the image keeps its data when `data` contains the former volume `/readeck`:
the secret key of the former `config.toml` becomes the secret `READECK_SECRET_KEY`, the other options move to `readeck_config`,
the files below `data` have to belong to UID and GID 1000.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-readeck-default` | Only the mandatory variables and the secret key |
| `molecule-readeck` | IPv6, labels, `main.log_level`, `extractor.workers` and a provider of OIDC with groups, provisioning and its client secret |

`prepare` creates the podman network and pulls the image.
`check` runs `converge` with `--check` on the new VMs.
`side_effect` runs the role with `readeck_container` and `readeck_config` not a dictionary, `readeck_secrets` not a list, a secret without `target`,
an unknown option, an option fixed by the role, the secret key in the configuration, a string as boolean, a line break in an option,
a provider of OIDC with `client_secret`, without `url` and without its client secret, without the secret key,
the secret key and an option in the environment, an unknown environment variable in the container and an unknown secret
and checks that it fails with the expected message and the quadlet unit and the configuration file are unchanged (tasks marked `expect ERROR`),
then it changes `main.log_level` on `molecule-readeck`, the configuration file changes, the quadlet unit not, and Readeck has to restart,
`molecule-readeck-default` runs again without a change and must not restart.
`verify` checks the quadlet unit with the user and the secrets in the environment without their values, the configuration file,
the data directory and the database, the service without automatic restarts, the addresses, the time zone and the environment,
the version of `/api/info` and the provider of OIDC on the login page, creates a user with `readeck user` and the hash of its password,
logs in with a wrong and the right password and reads the profile with the session cookie of the login (from `Set-Cookie`, the uri module keeps no cookies of a redirect it does not follow).

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd app_readeck
MOLECULE_TART_IMAGE='debian' molecule test
```
