[Thanos Query](https://thanos.io/tip/components/query.md/) runs in the container image [thanosio/thanos](https://hub.docker.com/r/thanosio/thanos) as podman quadlet `thanos-query`.
It answers PromQL queries with the data of the StoreAPIs of the other components of Thanos,
its HTTP API, UI and endpoints (`/-/ready`, `/metrics`) are on port `10902`, its own StoreAPI on port `10901`.
The image has no tag `latest`, `thanos_query_version` is mandatory, e.g. `v0.42.5`.

### Configuration

`thanos_query_endpoints` is the mandatory list of the gRPC addresses of the StoreAPIs (sidecar, receive, store, rule),
the role passes it as `--endpoint.sd-config`.
An address is a host name or IP address with port, IPv6 addresses in brackets, the DNS prefixes of Thanos (`dns+`, `dnssrv+`) are allowed.
Query connects to the endpoints in the background, an endpoint that is not reachable does not stop query.
The default command deduplicates the replica labels `replica` (Prometheus), `receive_replica` and `rule_replica`.
Query stores nothing, the role creates no directories.

```yaml
thanos_query_version: 'v0.42.5'
thanos_query_ip: '192.168.99.43'
thanos_query_network: 'podman99'
thanos_query_hostname: 'thanos-query'
thanos_query_timezone: 'Europe/Berlin'
thanos_query_endpoints:
  - 'thanos-sidecar:10901'
  - 'thanos-store:10901'
  - 'thanos-rule:10901'
```

### Secrets

Query reads no credentials, it has no object storage and no secrets.

### Allowed variables

Thanos reads no environment variables, the role only allows `TZ` in `thanos_query_environment`, it is set to `thanos_query_timezone`.
This prevents unexpected behavior by accident, e.g. by a variable meant for another image.
The check uses the environment of the container after merging `thanos_query_container`.

### Container

Ports, volumes, flags and dependencies (`requires`) are changed with `thanos_query_container`, it is merged over the default of the container.
The merge is not recursive, `publish`, `volumes` and `command` replace the values of the default completely.
The default mounts nothing, the command has `--endpoint.sd-config` and `--query.replica-label`.
Further flags (see the [flags of query](https://thanos.io/tip/components/query.md/#flags)) need the complete list,
the configuration of the endpoints then has to be written by hand.
The command is written space separated into the quadlet unit, an argument containing `"` or spaces has to be enclosed in `'`, otherwise the `"` are lost.
For a reverse proxy, e.g. Traefik, the labels are set with `thanos_query_labels`.

```yaml
thanos_query_container:
  publish: [ '10902:10902' ]
  command:
    - 'query'
    - '''--endpoint.sd-config={"endpoints": [{"address": "thanos-sidecar:10901"}]}'''
    - '--query.replica-label=replica'
    - '--query.timeout=5m'
```

### Validation

The role checks before any change:

- `thanos_query_endpoints` is a non-empty list of strings
- the addresses contain only letters, digits, `.`, `_`, `-`, `+`, `:` and brackets and are unique
- the values of `thanos_query_environment` contain no line breaks
- only `TZ` is set in the environment of the container

If `thanos_query_container` or `thanos_query_environment` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Restart and updates

Query is restarted if it was running and the quadlet unit changed, e.g. by changed endpoints, otherwise it is started and enabled.
If the start fails, the role shows the journal of the service.
Afterwards the role waits up to 120 seconds until `/-/ready` answers and shows the journal if query is not ready.
Updates of the image are done by `container_update` with `thanos_query_autoupdate_enabled: true` and `thanos_query_autoupdate_schedule`,
without `thanos_query_autoupdate_schedule` the schedule of `container_update` is used.
The image has no tag `latest`, an update needs a new `thanos_query_version`.

### Migration

The role replaces the component `query` of `monitoring_thanos`, `thanos_component` is removed.
The other components are the roles `monitoring_thanos_sidecar`, `monitoring_thanos_receive`, `monitoring_thanos_store`,
`monitoring_thanos_compact` and `monitoring_thanos_rule`.

| Former variable | Replacement |
|---|---|
| `thanos_component: 'query'` | Removed, the role `monitoring_thanos_query` |
| `thanos_version`, `thanos_ip`, `thanos_ipv6`, `thanos_network`, `thanos_hostname`, `thanos_timezone`, `thanos_labels` | `thanos_query_version`, `thanos_query_ip`, `thanos_query_ipv6`, `thanos_query_network`, `thanos_query_hostname`, `thanos_query_timezone`, `thanos_query_labels` |
| `thanos_query_endpoints` | `thanos_query_endpoints`, unchanged |
| `thanos_home` | Removed, query stores nothing |
| `thanos_objstore` | Removed, query uses no object storage |
| `thanos_container` | `thanos_query_container` |
| `thanos_autoupdate_enabled`, `thanos_autoupdate_schedule` | `thanos_query_autoupdate_enabled`, `thanos_query_autoupdate_schedule` |
| `thanos_instances`, `tasks/loop.yml` | Removed, the role runs once per host |

Changed behavior:

- `/etc/localtime` and `/etc/timezone` are no longer mounted, the time zone is set with `thanos_query_timezone` and `TZ`,
  the quadlet unit changes once and query restarts, volumes in `thanos_query_container` should no longer contain them
- `thanos_query_environment` sets the environment, it is checked against the allowed variables
- the addresses of `thanos_query_endpoints` are checked, an address containing `'` broke the quoted argument of the quadlet unit before
- the role waits until query is ready and shows the journal if the start fails
- the container keeps its name `thanos-query`

### Tests

The molecule scenarios run the role in [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root. The VMs need access to Docker Hub.

The scenario `default` has two VMs:

| Platform | Test case |
|---|---|
| `molecule-thanos-query-default` | Only the mandatory variables, query is connected to one sidecar |
| `molecule-thanos-query` | IPv6 and labels |

`prepare` creates the podman network, pulls the images and runs Prometheus with `monitoring_prometheus`
and the sidecar with `monitoring_thanos_sidecar`.
`side_effect` runs the role with `thanos_query_container` not a dictionary, the endpoints not a list and empty,
an invalid and a duplicate address, a line break in the environment and an unknown environment variable
and checks that it fails with the expected message and the quadlet unit is unchanged (tasks marked `expect ERROR`),
then it adds an endpoint that does not run on `molecule-thanos-query`, the quadlet unit changes and query has to restart.
`verify` checks the quadlet unit without volumes and secrets, the service, the environment,
the configuration of the endpoints in the command of the container, that query is ready, is connected to the sidecar
and returns the samples of Prometheus.

The scenario `stack` runs all components on one VM `molecule-thanos-query-stack`:
`prepare` runs Prometheus, `converge` runs `monitoring_thanos_sidecar`, `monitoring_thanos_store`, `monitoring_thanos_compact`,
`monitoring_thanos_rule` with the recording rule `thanos:up:count` and `monitoring_thanos_query` connected to sidecar, store and rule,
sidecar, store and compact share a bucket in the file system.
`verify` checks the quadlet unit, the service and `/-/ready` of every component, the rule file and the external label of rule
and with the API of query that sidecar, store and rule are connected and the samples of Prometheus and the recording rule are returned.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd monitoring_thanos_query
MOLECULE_TART_IMAGE='debian' molecule test
MOLECULE_TART_IMAGE='debian' molecule test -s stack
```
