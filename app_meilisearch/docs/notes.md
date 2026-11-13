Meilisearch runs in the container image [getmeili/meilisearch](https://hub.docker.com/r/getmeili/meilisearch) as podman quadlet,
it listens on port 7700. The database, the dumps and the snapshots are kept in `<meilisearch_home>/data`, mounted as `/meili_data`.
The role knows no application, applications like Karakeep connect with the address `http://<meilisearch_ip>:7700` and the master key.

### Configuration

Meilisearch is configured with environment variables in `meilisearch_environment`, merged over the default of the role.
The default sets `TZ` to `meilisearch_timezone`, `MEILI_ENV` to `production` and `MEILI_NO_ANALYTICS` to `true`.
Booleans may be given as YAML booleans, the role passes them as `true` or `false`.
The variables are described in the [configuration of Meilisearch](https://www.meilisearch.com/docs/learn/self_hosted/configure_meilisearch_at_launch).

```yaml
meilisearch_environment:
  MEILI_LOG_LEVEL: 'WARN'
  MEILI_MAX_INDEXING_MEMORY: '2 GiB'
  MEILI_SCHEDULE_SNAPSHOT: '86400'
```

`meilisearch_version` is `v1.41.0` by default, the version of the compose file of Karakeep v0.34.1.
Meilisearch only opens databases of its own version, a new version needs a dump (`MEILI_IMPORT_DUMP`)
or `MEILI_EXPERIMENTAL_DUMPLESS_UPGRADE: true`, so the version is fixed and changed on purpose, not with `latest`.

### Secrets

`meilisearch_secrets` is a list of podman secrets with `name`, `data` and `target`, the usual name of the variable.
Meilisearch reads its settings only from the environment or a configuration file and has no file variables,
so the secrets are passed in the environment of the container with `type=env,target=<target>`, they are not part of the quadlet unit.

`MEILI_MASTER_KEY` is mandatory and needs at least 16 characters, in production Meilisearch protects all routes except `GET /health` with it.
The allowed targets are `MEILI_MASTER_KEY`, `MEILI_TASK_WEBHOOK_AUTHORIZATION_HEADER` and `MEILI_EXPERIMENTAL_PERSONALIZATION_API_KEY`,
none of them may be set in `meilisearch_environment`.

```yaml
meilisearch_secrets:
  - name: 'meilisearch_master_key'
    data: "{{ vault_meilisearch_master_key }}"
    target: 'MEILI_MASTER_KEY'
```

### Allowed variables

The role only allows the environment variables in `app_meilisearch__environment_allowed` and the secrets listed above,
it stops before any change if unknown variables or secrets are set.
This prevents unexpected behavior by accident, e.g. by a typo or a variable that has to be passed as secret.
The check uses the environment and the secrets of the container after merging `meilisearch_container`.
The list is generated from the `MEILI_*` constants of `crates/meilisearch/src/option.rs` of Meilisearch v1.41.0 without the secrets,
new versions of the image may add variables. `MEILI_SERVER_PROVIDER` is set by the image and not allowed.

### Container

Ports, volumes, additional hosts (`etc_hosts`) and dependencies (`requires`) are changed with `meilisearch_container`, it is merged over the default of the container.
The merge is not recursive, `meilisearch_container.environment` replaces the environment including `meilisearch_environment`, use `meilisearch_environment` instead.
For a reverse proxy, e.g. Traefik, the labels are set with `meilisearch_labels`.
The image runs Meilisearch as root, the data directory belongs to root with the mode `0750`.

### Validation

The role checks before any change:

- `meilisearch_secrets` is a list of entries with `name`, `data` and `target` and unique names
- the secret `MEILI_MASTER_KEY` is set and has at least 16 characters
- `MEILI_ENV` is `production` or `development`
- no secret is set in `meilisearch_environment`, secrets and values contain no line breaks, booleans are `true` or `false`
- only allowed environment variables and secrets are set in the container

If `meilisearch_container` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Restart and updates

Meilisearch is restarted if it was running and a secret or the quadlet unit changed, e.g. after changing `meilisearch_environment`,
otherwise it is started and enabled. If the start fails, the role shows the journal of the service.
Afterwards the role waits up to 120 seconds until `/health` reports `available`.
Updates of the image are done by `container_update` with `meilisearch_autoupdate_enabled: true` and `meilisearch_autoupdate_schedule`,
without `meilisearch_autoupdate_schedule` the schedule of `container_update` is used. Mind the migration of the database with a fixed version.

### Migration

The role is new, there are no former variables.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-meilisearch-default` | Only the mandatory variables and the master key |
| `molecule-meilisearch` | IPv6, labels, `MEILI_LOG_LEVEL`, `MEILI_MAX_INDEXING_THREADS` and `MEILI_EXPERIMENTAL_ENABLE_METRICS` |

`prepare` creates the podman network and pulls the image.
`side_effect` runs the role with `meilisearch_container` not a dictionary, a secret without `target`, without the master key, a short master key,
the master key in the environment, an invalid `MEILI_ENV`, an invalid boolean, a line break in a value, an unknown environment variable and an unknown secret
and checks that it fails with the expected message and the quadlet unit is unchanged (tasks marked `expect ERROR`),
then it adds a document to the index `molecule` on `molecule-meilisearch` and changes `MEILI_LOG_LEVEL`, the quadlet unit changes and Meilisearch has to restart.
`verify` checks the quadlet unit with the secret in the environment without its value, the service, the addresses, the environment and the data directory,
the health check, the version without (401) and with the master key (200) and searches the document,
on `molecule-meilisearch` the document added before the restart.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd app_meilisearch
MOLECULE_TART_IMAGE='debian' molecule test
```
