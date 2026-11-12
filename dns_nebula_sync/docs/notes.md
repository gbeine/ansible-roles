[nebula-sync](https://github.com/lovelaze/nebula-sync) synchronizes the configuration of a primary Pi-hole (v6) to one or more replicas.
It runs in the container image `ghcr.io/lovelaze/nebula-sync`, synchronizes once on start and then on the schedule in `CRON`.

### Environment and secrets

All variables are set with `nebula_sync_environment`, which is merged over the defaults of the role, see the [configuration of nebula-sync](https://github.com/lovelaze/nebula-sync#configuration).
`PRIMARY` and `REPLICAS` contain the passwords of the Pi-hole instances and are passed as podman secrets with `nebula_sync_secrets`, they must not be set in `nebula_sync_environment`.
Every secret has a `name`, the `data` and the `target`, the usual name of the variable.
The role creates the secret with `podman secret create`, mounts it to `/run/secrets/<name>` and sets the file variable of nebula-sync,
`PRIMARY_FILE` for `PRIMARY` and `REPLICAS_FILE` for `REPLICAS`,
so the passwords are neither part of the quadlet unit nor of the environment of the container.

The role requires the following variables and checks them before it changes anything:

| Variable | Set with | Default of the role |
|---|---|---|
| `FULL_SYNC` | `nebula_sync_environment` | `false` |
| `PRIMARY` | `nebula_sync_secrets` | –, `http://host\|password` |
| `REPLICAS` | `nebula_sync_secrets` | –, `http://host\|password` separated by commas |

The role sets `TZ` to `nebula_sync_timezone` and keeps two defaults of former versions of the role, which differ from the defaults of nebula-sync:

| Variable | Default of the role | Default of nebula-sync |
|---|---|---|
| `RUN_GRAVITY` | `true` | `false` |
| `CRON` | `0 */6 * * *` | none, nebula-sync synchronizes once and exits |

Full synchronization with Teleporter:

```yaml
nebula_sync_environment:
  FULL_SYNC: 'true'
nebula_sync_secrets:
  - name: 'nebula_sync_primary'
    data: "http://192.168.99.53|{{ vault_pihole_primary_password }}"
    target: 'PRIMARY'
  - name: 'nebula_sync_replicas'
    data: "http://192.168.99.54|{{ vault_pihole_replica1_password }},http://192.168.99.55|{{ vault_pihole_replica2_password }}"
    target: 'REPLICAS'
```

Selective synchronization of the DNS settings without the upstreams and of the domain lists, with a webhook on failure:

```yaml
nebula_sync_environment:
  FULL_SYNC: 'false'
  SYNC_CONFIG_DNS: 'true'
  SYNC_CONFIG_DNS_EXCLUDE: 'upstreams'
  SYNC_GRAVITY_DOMAIN_LIST: 'true'
  WEBHOOK_SYNC_FAILURE_URL: 'https://hc-ping.com/<uuid>/fail'
```

Settings that a replica gets by environment variables (`FTLCONF_*`) are read-only in Pi-hole and cannot be synchronized, set them on the primary only or exclude them.

### Allowed variables

The role only allows the environment variables in `dns_nebula_sync__environment_allowed` and the secrets with the targets `PRIMARY` and `REPLICAS`,
it stops before any change if unknown variables or secrets are set.
This prevents unexpected behavior by accident, e.g. by a typo or a variable that has to be passed as secret.
The check uses the environment and the secrets of the container after merging `nebula_sync_container`,
so variables set with `nebula_sync_container.environment` are checked as well.
The allowed variables are the variables of nebula-sync v0.11.3 (README and `internal/config`) without `PRIMARY`, `REPLICAS`
and the internal variables `API_ENABLED` and `NS_DEBUG`,
and the file variables of the secrets. The role sets them from `nebula_sync_secrets`, they must not be set in `nebula_sync_environment`.
The webhooks have no file variables, a token in `WEBHOOK_*_URL` or `WEBHOOK_*_HEADERS` is part of the environment.

### Validation

The role checks before any change that `nebula_sync_secrets` is a list of entries with `name`, `data` and `target` and unique names,
that `FULL_SYNC` and the secrets `PRIMARY` and `REPLICAS` are set, that neither a secret nor its file variable is set in `nebula_sync_environment`
and that only allowed variables and secrets are used.
If `nebula_sync_container` is no dictionary, merging it with the default fails before anything changes.

### Changes and restarts

A running container is restarted when a secret or the quadlet unit changed, e.g. after changing `nebula_sync_environment`, and synchronizes again on start.
The first start of the container does not trigger an additional restart.

### Migration

Former versions of the role had a variable for every setting, they were replaced by `nebula_sync_environment` and `nebula_sync_secrets`:

| Former variable | Now |
|---|---|
| `nebula_sync_primary` | secret with target `PRIMARY` |
| `nebula_sync_replicas` | secret with target `REPLICAS` |
| `nebula_sync_full_sync`, `nebula_sync_run_gravity`, `nebula_sync_cron` | `FULL_SYNC`, `RUN_GRAVITY`, `CRON` |
| `nebula_sync_skip_tls_verification` | `CLIENT_SKIP_TLS_VERIFICATION` |
| `nebula_sync_retry_delay_seconds`, `nebula_sync_timeout_seconds` | `CLIENT_RETRY_DELAY_SECONDS`, `CLIENT_TIMEOUT_SECONDS` |
| `nebula_sync_sync_config_<section>` | `SYNC_CONFIG_<SECTION>` |
| `nebula_sync_sync_config_<section>_include`, `_exclude` | `SYNC_CONFIG_<SECTION>_INCLUDE`, `_EXCLUDE` |
| `nebula_sync_sync_gravity_<table>` | `SYNC_GRAVITY_<TABLE>` |
| `nebula_sync_webhook_sync_success_url`, `nebula_sync_webhook_sync_failure_url` | `WEBHOOK_SYNC_SUCCESS_URL`, `WEBHOOK_SYNC_FAILURE_URL` |

The former role set all `SYNC_*` and `CLIENT_*` variables explicitly to the defaults of nebula-sync, the role does not set them anymore.
Former versions put the passwords in `PRIMARY` and `REPLICAS` into the environment of the quadlet unit, the secrets keep them out of it.
The secrets are mounted as files and read with `PRIMARY_FILE` and `REPLICAS_FILE`, before they were passed as environment variables, `nebula_sync_secrets` stays the same.
The tags are `dns` and `dns_nebula_sync`.

### Tests

The molecule scenario `default` runs the role in a [tart](https://tart.run) VM `molecule-nebula-sync` on a macOS controller, the base VM has to be Debian 13.
The base VM is cloned and the clone is deleted afterwards, the base VM itself is never changed.
The playbooks creating and destroying the VMs are shared by all tart scenarios and live in `.molecule/tart/` in the repository root.

`prepare` sets up podman and the network `podman-molecule` with the role `container_podman`, pulls the images
and starts two Pi-hole containers, the primary with the upstream `9.9.9.9` and a replica with the default upstreams.
`converge` runs nebula-sync with a selective synchronization of the DNS upstreams and the Pi-hole URLs and passwords as secrets.
`side_effect` runs the role with `nebula_sync_container` not a dictionary, `nebula_sync_secrets` not a list, without the secret of the replicas,
the file variable of the primary in the environment, an unknown environment variable in `nebula_sync_environment` and in `nebula_sync_container.environment` and an unknown secret
and checks that it fails with the expected message and the quadlet unit is unchanged (tasks marked `expect ERROR`),
then it changes `CLIENT_TIMEOUT_SECONDS` and checks that the running service is restarted.
`verify` checks the quadlet unit with the mounted secrets, `PRIMARY_FILE` and `REPLICAS_FILE` and no passwords in the environment, the podman secrets and the service,
and checks with the API of the replica that the upstreams of the primary were synchronized.
The VM needs access to the GitHub container registry and Docker Hub.

Requirements on the controller: `tart`, `sshpass` (`brew install hudochenkov/sshpass/sshpass`), `molecule` and the collection `containers.podman`.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd dns_nebula_sync
MOLECULE_TART_IMAGE='debian' molecule test
```
