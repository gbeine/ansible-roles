Karakeep runs in the container image `ghcr.io/karakeep-app/karakeep` (`release` by default, `karakeep_version` sets the tag) as podman quadlet.
The image contains the web interface (Next.js, port 3000) and the workers, s6 migrates the database before it starts them.
Karakeep keeps its SQLite database and the assets in `<karakeep_home>/data`, mounted as `/data` (`DATA_DIR`).
The search and the crawling with a browser are optional and provided by the roles `app_meilisearch` and `app_karakeep_chrome`.

### Configuration

Karakeep is configured with environment variables in `karakeep_environment`, merged over the default of the role, which sets `TZ` to `karakeep_timezone`.
`NEXTAUTH_URL`, the public URL of Karakeep, is mandatory, better-auth only accepts requests from this origin.
The role sets `DATA_DIR` to `/data`, it must not be set in `karakeep_environment`.
Booleans may be given as YAML booleans, the role passes them as `true` or `false`.
The variables are described in the [configuration of Karakeep](https://docs.karakeep.app/configuration).

Meilisearch and Chrome are bound with their addresses, Meilisearch also needs its master key as secret (see Secrets):

```yaml
karakeep_environment:
  NEXTAUTH_URL: 'https://karakeep.example.org'
  MEILI_ADDR: "http://{{ meilisearch_ip }}:7700"
  BROWSER_WEB_URL: "http://{{ karakeep_chrome_ip }}:9222"
  DISABLE_SIGNUPS: true
```

Without `MEILI_ADDR` Karakeep has no full text search, without `BROWSER_WEB_URL` the workers crawl without a browser, e.g. without screenshots.

The administrator is set with `karakeep_admin` (`name`, `email` and `password`).
Without users the first user who signs up becomes the administrator, so the role creates the administrator itself directly after the start.
The module `app_karakeep_admin` runs node in the container and changes the database with `better-sqlite3` and `bcryptjs` of the image in one transaction,
the data is passed on stdin. It creates the user with a confirmed email and the role `admin` if no user with the email exists,
otherwise it keeps the name, the role and the confirmed email up to date and sets the password only if it differs.
Karakeep identifies users by the email, changing the email creates another administrator.

```yaml
karakeep_admin:
  name: 'Admin'
  email: 'admin@example.org'
  password: "{{ vault_karakeep_admin_password }}"
```

### Secrets

`karakeep_secrets` is a list of podman secrets with `name`, `data` and `target`, the usual name of the variable.
Karakeep reads its settings only from the environment with the schema of `packages/shared/config.ts` and has no file variables,
so the secrets are passed in the environment of the container with `type=env,target=<target>`, they are not part of the quadlet unit.

`NEXTAUTH_SECRET` is mandatory, it signs the sessions. `MEILI_MASTER_KEY` is needed together with `MEILI_ADDR`.
The allowed targets are `NEXTAUTH_SECRET`, `MEILI_MASTER_KEY`, `MEILI_VECTOR_MASTER_KEY`, `OPENAI_API_KEY`, `EMBEDDING_OPENAI_API_KEY`,
`SMTP_PASSWORD`, `OAUTH_CLIENT_SECRET`, `ASSET_STORE_S3_SECRET_ACCESS_KEY`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`,
`TURNSTILE_SECRET_KEY` and `PROMETHEUS_AUTH_TOKEN`, none of them may be set in `karakeep_environment`.

```yaml
karakeep_secrets:
  - name: 'karakeep_nextauth_secret'
    data: "{{ vault_karakeep_nextauth_secret }}"
    target: 'NEXTAUTH_SECRET'
  - name: 'karakeep_meili_master_key'
    data: "{{ vault_meilisearch_master_key }}"
    target: 'MEILI_MASTER_KEY'
```

### Allowed variables

The role only allows the environment variables in `app_karakeep__environment_allowed` and the secrets listed above,
it stops before any change if unknown variables or secrets are set.
This prevents unexpected behavior by accident, e.g. by a typo or a variable that has to be passed as secret.
The check uses the environment and the secrets of the container after merging `karakeep_container`.
The list is generated from the schema of `packages/shared/config.ts` and the variables of `packages/plugins` of Karakeep v0.34.1 without the secrets,
new versions of the image may add variables.
Not allowed are `DATA_DIR`, set by the role, `SERVER_VERSION` and `CHANGELOG_VERSION`, set by the image,
and `DEMO_MODE`, `DEMO_MODE_EMAIL` and `DEMO_MODE_PASSWORD`, the demo mode makes the instance read only and publishes the credentials of a user.

### Container

Ports, volumes, additional hosts (`etc_hosts`) and dependencies (`requires`) are changed with `karakeep_container`, it is merged over the default of the container.
The merge is not recursive, `karakeep_container.environment` replaces the environment including `karakeep_environment`, use `karakeep_environment` instead.
For a reverse proxy, e.g. Traefik, the labels are set with `karakeep_labels`.
The image runs Karakeep as root, the directories belong to root with the mode `0750`.

### Validation

The role checks before any change:

- `karakeep_secrets` is a list of entries with `name`, `data` and `target` and unique names
- `NEXTAUTH_URL` and the secret `NEXTAUTH_SECRET` are set, `MEILI_ADDR` and the secret `MEILI_MASTER_KEY` are only set together
- no secret and not `DATA_DIR` is set in `karakeep_environment`, secrets and values contain no line breaks, booleans are `true` or `false`
- `karakeep_admin` has a name of up to 128 characters, a valid email and a password of 8 to 128 characters, the limits of Karakeep
- only allowed environment variables and secrets are set in the container

If `karakeep_container` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Restart and updates

Karakeep is restarted if it was running and a secret or the quadlet unit changed, e.g. after changing `karakeep_environment`,
otherwise it is started and enabled. If the start fails, the role shows the journal of the service.
Afterwards the role waits up to 300 seconds until `/api/health` reports `ok` and shows the journal if Karakeep does not answer,
then it creates or updates the administrator.
Updates of the image are done by `container_update` with `karakeep_autoupdate_enabled: true` and `karakeep_autoupdate_schedule`,
without `karakeep_autoupdate_schedule` the schedule of `container_update` is used. The image migrates the database on the start.

### Migration

The role is new, there are no former variables.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root. The VMs need access to `ghcr.io` and Docker Hub.

| Platform | Test case |
|---|---|
| `molecule-karakeep-default` | Only the mandatory variables, without Meilisearch and Chrome |
| `molecule-karakeep` | IPv6, labels, Meilisearch, Chrome, `DISABLE_SIGNUPS` and `CRAWLER_STORE_SCREENSHOT` |

`prepare` creates the podman network and pulls the image, on `molecule-karakeep` it deploys Meilisearch and Chrome with `app_meilisearch` and `app_karakeep_chrome`.
`side_effect` runs the role with `karakeep_container` not a dictionary, a secret without `target`, without `NEXTAUTH_SECRET`, without `NEXTAUTH_URL`,
`MEILI_ADDR` without the master key, a secret and `DATA_DIR` in the environment, the demo mode, an unknown secret, an invalid boolean, a line break in a value,
an administrator without password and a password of 7 characters
and checks that it fails with the expected message and the quadlet unit is unchanged (tasks marked `expect ERROR`),
then it changes `CRAWLER_STORE_SCREENSHOT`, the name and the password of the administrator on `molecule-karakeep`,
the quadlet unit changes, Karakeep has to restart and the administrator is updated, not created.
`verify` checks the quadlet unit with the secrets in the environment without their values, the service, the addresses, the environment and the database,
the health check, the sign-in with the password (200), a wrong one and the former one (401), the signed in user of the API with the session and without one (401)
and that the database contains only the administrator with the role `admin`.
On `molecule-karakeep` it creates a text bookmark, finds it with the search of Meilisearch and reads the version of Chrome from the container of Karakeep.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd app_karakeep
MOLECULE_TART_IMAGE='debian' molecule test
```
