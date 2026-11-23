Keeper synchronizes calendars, it runs in the container image `ghcr.io/ridafkih/keeper-services` (`2.34` by default, `keeper_version` sets the tag) as podman quadlet.
The image contains the web interface (port 3000), the API, the cron jobs and the worker, s6 migrates the database on every start before it starts them.
The web interface proxies `/api` to the API, only port 3000 has to be reachable.
Keeper keeps its state in PostgreSQL and Redis, they are not part of the role. The role creates no directories.

### Configuration

Keeper is configured with environment variables in `keeper_environment`, it is mandatory.
`BETTER_AUTH_URL`, the public URL of Keeper, is mandatory, it is used for the redirects and better-auth only accepts requests from this origin
and the origins in `TRUSTED_ORIGINS`. `REDIS_URL` is set in `keeper_environment` or as secret if it contains a password.
Booleans are the strings `true` or `false`, Keeper does not accept other values, YAML booleans are rejected.
The time zone of the container is `keeper_timezone`, the image sets no `TZ` and the role sets no default for it.
The variables are described in the [README of Keeper](https://github.com/ridafkih/keeper.sh#collective-services-image).

```yaml
keeper_environment:
  BETTER_AUTH_URL: 'https://keeper.example.org'
  REDIS_URL: "redis://{{ redis_ip }}:6379/"
```

### Secrets

`keeper_secrets` is a list of podman secrets with `name`, `data` and `target`, the usual name of the variable.
Keeper reads its settings only from the environment with the schemas of `services/*/src/env.ts` and has no file variables,
so the secrets are passed in the environment of the container with `type=env,target=<target>`, they are not part of the quadlet unit.

`DATABASE_URL`, `BETTER_AUTH_SECRET` and `ENCRYPTION_KEY` are mandatory.
`BETTER_AUTH_SECRET` signs the sessions, `ENCRYPTION_KEY` encrypts the passwords of CalDAV accounts, it is 32 bytes in base64 (`openssl rand -base64 32`).
The allowed targets are `BETTER_AUTH_SECRET`, `DATABASE_URL`, `ENCRYPTION_KEY`, `GOOGLE_CLIENT_SECRET`, `MICROSOFT_CLIENT_SECRET`,
`OIDC_CLIENT_SECRET`, `OTEL_EXPORTER_OTLP_HEADERS`, `REDIS_URL` and `RESEND_API_KEY`.
None of them may be set in `keeper_environment`, except `REDIS_URL` if it is no secret.

```yaml
keeper_secrets:
  - name: 'keeper_database_url'
    data: "postgres://keeper:{{ vault_keeper_database_password }}@{{ postgres_ip }}:5432/keeper"
    target: 'DATABASE_URL'
  - name: 'keeper_better_auth_secret'
    data: "{{ vault_keeper_better_auth_secret }}"
    target: 'BETTER_AUTH_SECRET'
  - name: 'keeper_encryption_key'
    data: "{{ vault_keeper_encryption_key }}"
    target: 'ENCRYPTION_KEY'
```

### Users

Keeper has no administrator. Users sign up in the web interface with a username and a password,
Keeper stores them with the email `<username>@local`.
`REGISTRATION_EMAIL_DOMAINS` restricts new users to a comma separated list of email domains,
users with a username and a password need `local` in the list.
With OIDC (`OIDC_ISSUER_URL`, `OIDC_CLIENT_ID` and the secret `OIDC_CLIENT_SECRET`) no new users with a username are created,
`DISABLE_LOCAL_AUTH: 'true'` also disables the sign-in with a username and a password, it has no effect without OIDC.

### Allowed variables

The role only allows the environment variables in `app_keeper__environment_allowed` and the secrets listed above,
it stops before any change if unknown variables or secrets are set.
This prevents unexpected behavior by accident, e.g. by a typo or a variable that has to be passed as secret.
The check uses the environment and the secrets of the container after merging `keeper_container`.
The list is generated from `services/api`, `services/cron` and `services/worker/src/env.ts`, `applications/web/src/server/config.ts`
and the OpenTelemetry variables of the README of Keeper v2.34.2, new versions of the image may add variables.

Not allowed are the variables set by the image (`ENV`, `PORT`, `API_PORT`, `VITE_API_URL`, `ICU_TIMEZONE_FILES_DIR`, `VERSION`, `COMMIT_SHA`)
and the variables of the commercial service keeper.sh: `COMMERCIAL_MODE` with the billing by Polar (`POLAR_*`),
the passkeys (`PASSKEY_*`), which only work with `COMMERCIAL_MODE`, and the ads and the analytics
(`VITE_GOOGLE_ADS_*`, `VITE_GOOGLE_ANALYTICS_ID`, `VITE_VISITORS_NOW_TOKEN`, `OPENAI_APPS_CHALLENGE_TOKEN`).

### Container

Ports, volumes, additional hosts (`etc_hosts`) and the dependencies are changed with `keeper_container`, it is merged over the default of the container.
The dependencies of the quadlet unit are lists: `requires`, `wants`, `after`, `part_of` and `binds_to` are units,
`requires_mounts_for` are paths. They are written to `[Unit]` as `Requires=`, `Wants=`, `After=`, `PartOf=`, `BindsTo=` and `RequiresMountsFor=`.
The merge is not recursive, `keeper_container.environment` replaces the environment including `keeper_environment`, use `keeper_environment` instead.
For a reverse proxy, e.g. Traefik, the labels are set with `keeper_labels`.

```yaml
keeper_container:
  wants: [ 'network-online.target' ]
  after: [ 'network-online.target' ]
```

### Validation

The role checks before any change:

- `keeper_secrets` is a list of entries with `name`, `data` and `target` and unique names
- `keeper_environment` is a dictionary with `BETTER_AUTH_URL`, an http or https URL
- the secrets `DATABASE_URL`, `BETTER_AUTH_SECRET` and `ENCRYPTION_KEY` are set, `ENCRYPTION_KEY` is 32 bytes in base64
- `REDIS_URL` is set in `keeper_environment` or as secret, not both
- no secret is set in `keeper_environment`, secrets and values contain no line breaks, booleans are the strings `true` or `false`
- only allowed environment variables without line breaks and allowed secrets are set in the container

If `keeper_container` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Check mode

The role runs with `--check`, also on a host where it never ran, and reports the secrets and the quadlet unit.
The start and the wait for Keeper do not run in check mode.

### Restart and updates

Keeper is restarted if it was running and a secret or the quadlet unit changed, e.g. after changing `keeper_environment`,
otherwise it is started and enabled. If the start fails, the role shows the error and the journal of the service.
Afterwards the role waits up to 180 seconds until `/api/health` reports `ok` and shows the journal if Keeper does not answer.
Updates of the image are done by `container_update` with `keeper_autoupdate_enabled: true` and `keeper_autoupdate_schedule`,
without `keeper_autoupdate_schedule` the schedule of `container_update` is used. The image migrates the database on the start.

### Migration

| Former variable | Now |
|---|---|
| `keeper_db_host`, `keeper_db_port`, `keeper_db_user`, `keeper_db_pass`, `keeper_db_name` | secret `DATABASE_URL`, e.g. `postgres://keeper:<password>@<host>:5432/keeper` |
| `keeper_redis_host`, `keeper_redis_port` | `keeper_environment.REDIS_URL` or secret `REDIS_URL`, e.g. `redis://<host>:6379/` |
| `keeper_url` | `keeper_environment.BETTER_AUTH_URL`, if needed also `TRUSTED_ORIGINS` |
| `keeper_encryption_key` | secret `ENCRYPTION_KEY` |
| `keeper_better_auth_secret` | secret `BETTER_AUTH_SECRET` |

- The secrets were created with fixed names (`keeper_database_url`, `keeper_encryption_key`, `keeper_better_auth_secret`),
  they are listed in `keeper_secrets` now, the same names keep the existing secrets.
- `BETTER_AUTH_URL` was fixed to `http://localhost:3000/`, the redirects of the sign-in with Google or Microsoft pointed to localhost,
  `keeper_url` was only set as `TRUSTED_ORIGINS`.
- `WORKER_JOB_QUEUE_ENABLED` is not set anymore, the image sets it to `true`.
- `/etc/localtime` and `/etc/timezone` are not mounted anymore, the time zone is set by podman with `keeper_timezone`.
- `podman___update_mode` is not evaluated anymore, the role neither stops the container nor pulls the image or recreates the container.
- The default of `keeper_version` is `2.34` instead of `2.11`, the image migrates the database on the start.
- The service restarts after a crash (`Restart=always`), the tags are `app` and `app_keeper`.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root. The VMs need access to `ghcr.io` and Docker Hub.

| Platform | Test case |
|---|---|
| `molecule-keeper-default` | Only the mandatory variables, `REDIS_URL` in the environment |
| `molecule-keeper` | IPv6, labels, `TRUSTED_ORIGINS`, `CRON_JOBS_ENABLED` and `REDIS_URL` with a password as secret |

`prepare` creates the podman network, pulls the images and starts PostgreSQL and Redis with a password on every VM.
`check` runs `converge` with `--check` on the new VMs.
`side_effect` runs the role with `keeper_container` and `keeper_environment` not a dictionary, a secret without `target`, without `DATABASE_URL`,
without `BETTER_AUTH_URL`, without `REDIS_URL`, `REDIS_URL` in the environment and as secret, a secret in the environment,
an invalid `ENCRYPTION_KEY`, a YAML boolean, a line break in a value, an invalid `BETTER_AUTH_URL`, `COMMERCIAL_MODE` and an unknown secret
and checks that it fails with the expected message and the quadlet unit is unchanged (tasks marked `expect ERROR`),
then it changes `TRUSTED_ORIGINS` on `molecule-keeper`, the quadlet unit changes and Keeper has to restart,
`molecule-keeper-default` runs again without a change and must not restart.
`verify` checks the quadlet unit with the secrets in the environment without their values and without volumes,
the service without automatic restarts, the addresses, the time zone and the environment of the container,
the health check, the sign-up of a user, the refused second sign-up, the sign-in with the password (200) and a wrong one (401),
the session of the signed in user and the user in PostgreSQL.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd app_keeper
MOLECULE_TART_IMAGE='debian' molecule test
```
