n8n runs in the official container image [n8nio/n8n](https://docs.n8n.io/hosting/installation/docker/) as podman quadlet and is configured with environment variables.
See the [environment variables of n8n](https://docs.n8n.io/hosting/configuration/environment-variables/) for all variables.
`<n8n_home>/data` is mounted to `/home/node/.n8n`, it contains the sqlite database, the settings and the generated encryption key.
n8n runs as the user `node` (uid 1000) of the image and listens on port 5678 (`N8N_PORT`).

### Configuration

All variables are set with `n8n_environment`, which is merged over the defaults of the role
(`TZ`, `GENERIC_TIMEZONE` and `N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS: true`).
Booleans may be written as YAML booleans, the role passes them as `true` and `false`.

```yaml
n8n_environment:
  N8N_HOST: 'n8n.example.org'
  N8N_PROTOCOL: 'https'
  N8N_WEBHOOK_URL: 'https://n8n.example.org/'
  N8N_PROXY_HOPS: 1
```

Without `DB_TYPE` n8n uses sqlite in `<n8n_home>/data`. With `DB_TYPE: postgresdb` the variables `DB_POSTGRESDB_HOST`, `DB_POSTGRESDB_DATABASE`,
`DB_POSTGRESDB_USER` and the secret `DB_POSTGRESDB_PASSWORD` are mandatory, `DB_POSTGRESDB_PORT` defaults to 5432.

```yaml
n8n_environment:
  DB_TYPE: 'postgresdb'
  DB_POSTGRESDB_HOST: 'postgres'
  DB_POSTGRESDB_DATABASE: 'n8n'
  DB_POSTGRESDB_USER: 'n8n'
```

### Owner

`n8n_owner` sets the owner of n8n, n8n creates or updates the owner from it on every start (`N8N_INSTANCE_OWNER_MANAGED_BY_ENV`),
also a changed password. Without `n8n_owner` the owner is created in the browser after the first start.

```yaml
n8n_owner:
  email: 'admin@example.org'
  first_name: 'Admin'
  last_name: 'Example'
  password: "{{ vault_n8n_owner_password }}"
```

The password needs 8 to 64 characters with at least one digit and one uppercase letter like n8n requires.
n8n reads the password as bcrypt hash, the role creates it with its module `app_n8n_owner_secret` (`library/`) and stores it in the podman secret
`<container name>_owner_password_hash`, which is mounted as `N8N_INSTANCE_OWNER_PASSWORD_HASH_FILE`.
The salt is derived from the email and the password, so the hash only changes with them and n8n only restarts after a change.
The host of the role needs `python3-bcrypt`, the role installs it. The variables `N8N_INSTANCE_OWNER_*` are set by the role and must not be set in `n8n_environment`.

### Secrets

Variables carrying secrets are passed as podman secrets with `n8n_secrets` and must not be set in `n8n_environment`.
Every secret has a `name`, the `data` and the `target`, the name of the variable, e.g. `DB_POSTGRESDB_PASSWORD`.
The role creates the secret with `podman secret create`, mounts it to `/run/secrets/<name>` and sets `<target>_FILE`,
n8n reads every variable from the file `<variable>_FILE`, so the secret is neither part of the quadlet unit nor of the environment of the container.

```yaml
n8n_secrets:
  - name: 'n8n_db_password'
    data: "{{ vault_n8n_db_password }}"
    target: 'DB_POSTGRESDB_PASSWORD'
  - name: 'n8n_encryption_key'
    data: "{{ vault_n8n_encryption_key }}"
    target: 'N8N_ENCRYPTION_KEY'
```

No secret is mandatory. Without `N8N_ENCRYPTION_KEY` n8n creates a key in `<n8n_home>/data/config`, the credentials can only be read with this key,
setting it as secret keeps it outside the data. The allowed targets are listed in `app_n8n__secret_files`, e.g. `DB_POSTGRESDB_PASSWORD`, `N8N_ENCRYPTION_KEY`,
`N8N_USER_MANAGEMENT_JWT_SECRET`, `N8N_SMTP_PASS`, `QUEUE_BULL_REDIS_PASSWORD`, `CREDENTIALS_OVERWRITE_DATA` and the keys and tokens of external services.

### Allowed variables

The role only allows the environment variables in `app_n8n__environment_allowed` and the secrets in `app_n8n__secret_files`,
it stops before any change if unknown variables or secrets are set.
This prevents unexpected behavior by accident, e.g. by a typo, a deprecated variable or a variable that has to be passed as secret.
The variables are generated from all `@Env` of the packages of n8n 2.47.5 without the secrets, plus `TZ` of the image and the file variables of the secrets.
The booleans (`app_n8n__environment_booleans`) are the fields of the type boolean. New versions of n8n may add variables, the lists are generated again.
The check uses the environment and the secrets of the container after merging `n8n_container`,
so variables set with `n8n_container.environment` are checked as well.

### Container

Ports, volumes, additional hosts (`etc_hosts`) and dependencies (`requires`) are changed with `n8n_container`, it is merged over the default of the container.
The merge is not recursive, `n8n_container.volumes` replaces `/home/node/.n8n`, `n8n_container.environment` replaces the environment including `n8n_environment`.
The role waits until `/healthz` of n8n answers, n8n migrates the database and applies the owner on every start, it shows the log of the service otherwise.

### Validation

The role checks before any change:

- `n8n_secrets` is a list of entries with `name`, `data` and `target` with unique names
- `DB_TYPE` is `sqlite` or `postgresdb`, `postgresdb` has the variables of PostgreSQL and the secret `DB_POSTGRESDB_PASSWORD`
- neither a secret nor its file variable nor a variable of the owner is set in `n8n_environment`
- the booleans of n8n are `true` or `false`, values have no line breaks
- `n8n_owner` has only known keys, a valid email and a password following the rules of n8n
- only allowed environment variables and secrets are set in the container

If `n8n_container` is no dictionary, merging it with the default fails before anything changes.

### Restart and updates

n8n is restarted if it was running and a secret, the hash of the password of the owner or the quadlet unit changed, otherwise it is started and enabled.
Updates of the image are done by `container_update` with `n8n_autoupdate_enabled: true` and `n8n_autoupdate_schedule`,
without `n8n_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

The single variables are replaced by `n8n_environment` and `n8n_secrets`:

| Former variable | Now |
|---|---|
| `n8n_host`, `n8n_port` | `N8N_HOST`, `N8N_PORT` |
| `n8n_base_url` | `N8N_WEBHOOK_URL`, `WEBHOOK_URL` is deprecated by n8n |
| `n8n_db_host`, `n8n_db_port`, `n8n_db_name`, `n8n_db_user` | `DB_TYPE: postgresdb` with `DB_POSTGRESDB_HOST`, `DB_POSTGRESDB_PORT`, `DB_POSTGRESDB_DATABASE`, `DB_POSTGRESDB_USER` |
| `n8n_db_pass` | secret `DB_POSTGRESDB_PASSWORD`, it was part of the environment in plain text |
| `n8n_hosts` | `n8n_container.etc_hosts` |
| `n8n_hostname` | mandatory, the default `n8n.<dns_hostname>` is removed |
| `n8n_ip`, `n8n_ipv6`, `n8n_network`, `n8n_timezone`, `n8n_home`, `n8n_version`, `n8n_autoupdate_*` | stay |

- PostgreSQL was mandatory, without `DB_TYPE` n8n uses sqlite now, set `DB_TYPE: postgresdb` for existing installations.
- The former role set `N8N_RUNNERS_ENABLED` and `EXPRESS_TRUST_PROXY`, n8n 2.47.5 does not know them anymore,
  task runners are always enabled and `N8N_PROXY_HOPS` replaces the trust of the proxy.
- The former default of `n8n_autoupdate_schedule` (`*-*-* 04:00:00`) is removed, the schedule of `container_update` is used.
- `n8n_container` was not merged, it is merged over the default now. `n8n_labels` is new.
- If `N8N_ENCRYPTION_KEY` is set for an existing installation, it has to be the key of `<n8n_home>/data/config`, otherwise the credentials cannot be read.
- The volumes `/etc/localtime` and `/etc/timezone` are removed, the timezone is set by podman and `TZ`.
- The service is not stopped on every run anymore, `podman___update_mode` is removed.
- The tag `app_n8n` stays, the tag `app` is added.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-n8n-default` | Only the mandatory variables, sqlite, without owner |
| `molecule-n8n` | IPv6, labels, PostgreSQL with the secret `DB_POSTGRESDB_PASSWORD`, the secret `N8N_ENCRYPTION_KEY` and the owner |

`prepare` creates the podman network, pulls the image and starts PostgreSQL on `molecule-n8n`.
`side_effect` runs the role with `n8n_container` not a dictionary, a secret without `target`, the database password in the environment,
PostgreSQL without the database password, an invalid `DB_TYPE`, a variable of the owner in the environment, an invalid boolean, a line break in a value,
an owner without email, a weak password of the owner, an unknown environment variable and an unknown secret
and checks that it fails with the expected message and the quadlet unit is unchanged (tasks marked `expect ERROR`),
then it changes the password of the owner on `molecule-n8n`, the secret of the hash changes and n8n has to restart.
`verify` checks the quadlet unit with the secrets as files and without passwords, the service, the addresses and the environment of the container,
`/healthz`, the setup of the owner in `/rest/settings`, the login of the owner with the changed password and the refused former password
and the tables of n8n in PostgreSQL.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd app_n8n
MOLECULE_TART_IMAGE='debian' molecule test
```
