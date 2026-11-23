Meilisearch runs in the container image [getmeili/meilisearch](https://hub.docker.com/r/getmeili/meilisearch) as podman quadlet,
it listens on port 7700. The database, the dumps and the snapshots are kept in `<meilisearch_home>/data`, mounted as `/meili_data`.
The role knows no application, applications like Karakeep connect with the address `http://<meilisearch_ip>:7700` and the master key.

### Configuration

Meilisearch is configured with its configuration file `config.toml`, the options are set in `meilisearch_config`, merged over the default of the role.
The default sets `env` to `production` and `no_analytics` to `true`.
The role writes the file to `<meilisearch_home>/config.toml`, it is mounted read only as `/etc/meilisearch/config.toml`
and the role sets `MEILI_CONFIG_FILE_PATH` to it.
The keys are the options of Meilisearch in snake case, TOML is typed: booleans are YAML booleans, numbers are numbers, `null` removes an option.
The options are described in the [configuration of Meilisearch](https://www.meilisearch.com/docs/learn/self_hosted/configure_meilisearch_at_launch).

```yaml
meilisearch_config:
  log_level: 'WARN'
  max_indexing_memory: '2 GiB'
  schedule_snapshot: 86400
  experimental_enable_metrics: true
```

Meilisearch ignores `import_dump`, `import_snapshot` and their `ignore_*` options in the configuration file,
they are set in `meilisearch_environment`, the booleans as strings `true` or `false`.
Like in Meilisearch, `MEILI_IGNORE_MISSING_DUMP` and `MEILI_IGNORE_DUMP_IF_DB_EXISTS` need `MEILI_IMPORT_DUMP`,
the `MEILI_IGNORE_*_SNAPSHOT` variables `MEILI_IMPORT_SNAPSHOT`, a dump and a snapshot are not imported together.
The quadlet unit starts Meilisearch with the import on every start, once the database exists Meilisearch refuses to start,
so the role requires `MEILI_IGNORE_DUMP_IF_DB_EXISTS: 'true'` with `MEILI_IMPORT_DUMP` and `MEILI_IGNORE_SNAPSHOT_IF_DB_EXISTS: 'true'`
with `MEILI_IMPORT_SNAPSHOT`, e.g. to import a dump into a new instance:

```yaml
meilisearch_environment:
  MEILI_IMPORT_DUMP: '/meili_data/dumps/20261123.dump'
  MEILI_IGNORE_DUMP_IF_DB_EXISTS: 'true'
```

The environment takes precedence over the configuration file, `crates/meilisearch/src/option.rs` only exports the options of the file
to the environment if a variable is not set. The time zone of the container is `meilisearch_timezone`, the image sets no `TZ`.

`meilisearch_version` is `v1.58.0` by default. Meilisearch only opens databases of its own version,
another version needs a dump (`MEILI_IMPORT_DUMP`) or `upgrade_db: true` in `meilisearch_config` (from v1.12 on),
so the version is fixed and changed on purpose, not with `latest`.

### Secrets

`meilisearch_secrets` is a list of podman secrets with `name`, `data` and `target`, the usual name of the variable.
The configuration file cannot read files and Meilisearch has no file variables,
so the secrets are passed in the environment of the container with `type=env,target=<target>`, they are not part of the quadlet unit
and not part of the configuration file, the environment takes precedence over the file.

`MEILI_MASTER_KEY` is mandatory and needs at least 16 characters, in production Meilisearch protects all routes except `GET /health` with it.
The allowed targets are `MEILI_MASTER_KEY`, `MEILI_TASK_WEBHOOK_AUTHORIZATION_HEADER`, `MEILI_EXPERIMENTAL_PERSONALIZATION_API_KEY`
and `MEILI_S3_SECRET_KEY`, none of them may be set in `meilisearch_environment`,
their options (`master_key`, `task_webhook_authorization_header`, `experimental_personalization_api_key`, `s3_secret_key`) not in `meilisearch_config`.

```yaml
meilisearch_secrets:
  - name: 'meilisearch_master_key'
    data: "{{ vault_meilisearch_master_key }}"
    target: 'MEILI_MASTER_KEY'
```

### Allowed options and variables

The role only allows the options in `app_meilisearch__config_allowed`, the environment variables in `app_meilisearch__environment_allowed`
and the secrets listed above, it stops before any change if unknown options, variables or secrets are set.
This prevents unexpected behavior by accident, e.g. by a typo or an option that has to be passed as secret,
Meilisearch itself refuses to start with an unknown option in the configuration file.
The check of the environment and the secrets uses the container after merging `meilisearch_container`.
The options are generated from the fields of `Opt`, `IndexerOpts` and `S3SnapshotOpts` of `crates/meilisearch/src/option.rs` of Meilisearch v1.58.0
without the secrets and `config_file_path`, the environment allows `TZ` and the variables of the options the configuration file ignores.
New versions of the image may add options. `MEILI_SERVER_PROVIDER` is set by the image and not allowed.

### Container

Ports, volumes, additional hosts (`etc_hosts`) and the dependencies are changed with `meilisearch_container`, it is merged over the default of the container.
The dependencies of the quadlet unit are lists: `requires`, `wants`, `after`, `part_of` and `binds_to` are units,
`requires_mounts_for` are paths. They are written to `[Unit]` as `Requires=`, `Wants=`, `After=`, `PartOf=`, `BindsTo=` and `RequiresMountsFor=`.
The merge is not recursive, `meilisearch_container.volumes` replaces the data directory and the configuration file,
`meilisearch_container.environment` replaces the environment including `MEILI_CONFIG_FILE_PATH`, use `meilisearch_environment` instead.
For a reverse proxy, e.g. Traefik, the labels are set with `meilisearch_labels`.
The image runs Meilisearch as root, the directories belong to root with the mode `0750`, the configuration file with `0640`.

```yaml
meilisearch_container:
  wants: [ 'network-online.target' ]
  after: [ 'network-online.target' ]
```

### Validation

The role checks before any change:

- `meilisearch_secrets` is a list of entries with `name`, `data` and `target` and unique names
- `meilisearch_config` contains only allowed options and no secrets, `env` is `production` or `development`,
  booleans are YAML booleans, `schedule_snapshot` is a boolean or a number of seconds, strings contain no line breaks
- the secret `MEILI_MASTER_KEY` is set and has at least 16 characters
- no secret and not `MEILI_CONFIG_FILE_PATH` is set in `meilisearch_environment`, secrets and values contain no line breaks,
  the booleans of the environment are the strings `true` or `false`, the `MEILI_IGNORE_*` variables have their import,
  `MEILI_IMPORT_DUMP` and `MEILI_IMPORT_SNAPSHOT` are not set together and have their `MEILI_IGNORE_*_IF_DB_EXISTS`
- only allowed environment variables without line breaks and allowed secrets are set in the container

If `meilisearch_container`, `meilisearch_config` or `meilisearch_environment` is no dictionary, merging it fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Check mode

The role runs with `--check`, also on a host where it never ran, and reports the directories, the configuration file, the secrets and the quadlet unit.
The start and the wait for Meilisearch do not run in check mode.

### Restart and updates

Meilisearch is restarted if it was running and the configuration file, a secret or the quadlet unit changed,
otherwise it is started and enabled. If the start fails, the role shows the error and the journal of the service.
Afterwards the role asks `/health` up to 60 times every 2 seconds, each request waits at most 5 seconds,
until it reports `available` and shows the journal if Meilisearch is not available.
Updates of the image are done by `container_update` with `meilisearch_autoupdate_enabled: true` and `meilisearch_autoupdate_schedule`,
without `meilisearch_autoupdate_schedule` the schedule of `container_update` is used. Mind the migration of the database with a fixed version.

### Migration

The options are set in `meilisearch_config` instead of `meilisearch_environment`, the key is the variable without `MEILI_` in lower case:

| Former variable in `meilisearch_environment` | Option in `meilisearch_config` |
|---|---|
| `MEILI_ENV` | `env` |
| `MEILI_NO_ANALYTICS` | `no_analytics` |
| `MEILI_LOG_LEVEL` | `log_level` |
| `MEILI_<OPTION>`, e.g. `MEILI_MAX_INDEXING_THREADS`, `MEILI_SCHEDULE_SNAPSHOT`, `MEILI_SSL_CERT_PATH` | `<option>`, e.g. `max_indexing_threads`, `schedule_snapshot`, `ssl_cert_path` |
| `MEILI_EXPERIMENTAL_DUMPLESS_UPGRADE` | `upgrade_db` (renamed in v1.51) |
| `MEILI_CONFIG_FILE_PATH` | set by the role |

- `MEILI_IMPORT_DUMP`, `MEILI_IMPORT_SNAPSHOT` and their `MEILI_IGNORE_*` variables stay in `meilisearch_environment`, as strings `true` or `false`.
- Booleans and numbers of `meilisearch_config` are YAML booleans and numbers, not strings.
- `MEILI_EXPERIMENTAL_REPLICATION_PARAMETERS` and `MEILI_EXPERIMENTAL_NO_SNAPSHOT_COMPACTION` are removed in Meilisearch v1.58.0.
- The role sets no default for `TZ` anymore, the time zone of the container is `meilisearch_timezone`.
- The default of `meilisearch_version` is `v1.58.0` instead of `v1.41.0`, an existing database needs `upgrade_db: true` once,
  afterwards it is removed again.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-meilisearch-default` | Only the mandatory variables and the master key |
| `molecule-meilisearch` | IPv6, labels, `log_level`, `max_indexing_threads`, `experimental_enable_metrics`, the import of a missing dump with `MEILI_IGNORE_MISSING_DUMP` |

`prepare` creates the podman network and pulls the image.
`check` runs `converge` with `--check` on the new VMs.
`side_effect` runs the role with `meilisearch_container` and `meilisearch_config` not a dictionary, a secret without `target`, without the master key,
a short master key, the master key in the environment and in the configuration, an unknown option, an invalid `env`, a string as boolean,
a line break in an option and in a value, an invalid boolean in the environment, `MEILI_IGNORE_MISSING_DUMP` without `MEILI_IMPORT_DUMP`,
`MEILI_IMPORT_DUMP` without `MEILI_IGNORE_DUMP_IF_DB_EXISTS`,
a dump and a snapshot together, `MEILI_CONFIG_FILE_PATH` and an option in the environment,
an unknown environment variable and an unknown secret
and checks that it fails with the expected message and the quadlet unit and the configuration file are unchanged (tasks marked `expect ERROR`),
then it adds a document to the index `molecule` on `molecule-meilisearch` and changes `log_level`,
the configuration file changes, the quadlet unit not, and Meilisearch has to restart,
`molecule-meilisearch-default` runs again without a change and must not restart.
`verify` checks the configuration file, the quadlet unit with the secret in the environment without its value,
the service without automatic restarts, the addresses, the time zone, the environment and the data directory,
the health check, the version without (401) and with the master key (200), the metrics enabled by the configuration file
and searches the document, on `molecule-meilisearch` the document added before the restart.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd app_meilisearch
MOLECULE_TART_IMAGE='debian' molecule test
```
