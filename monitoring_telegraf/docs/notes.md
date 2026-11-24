Telegraf runs in the official container image [telegraf](https://hub.docker.com/_/telegraf) (`alpine` by default) as podman quadlet.
The role writes `telegraf.conf` from `telegraf_config` and mounts it read-only to `/etc/telegraf/telegraf.conf`.

### Requirements

The configuration is rendered with the filter [`community.general.to_toml`](https://docs.ansible.com/ansible/latest/collections/community/general/to_toml_filter.html),
which needs the Python library [tomlkit](https://pypi.org/project/tomlkit/) on the Ansible controller, e.g. `pip install tomlkit` in the environment of Ansible and molecule.

### Configuration

`telegraf_config` is `telegraf.conf` as dictionary, every key replaces the key of the default of the role, the merge is not recursive.
The default only contains `agent`:

```yaml
agent:
  interval: '10s'
  round_interval: true
  metric_batch_size: 1000
  metric_buffer_limit: 10000
  collection_jitter: '0s'
  flush_interval: '10s'
  flush_jitter: '0s'
  precision: '0s'
  omit_hostname: true
```

`telegraf_config.agent` replaces the whole section, it contains all settings of the agent that differ from the defaults of Telegraf.
The sections `outputs`, `inputs`, `processors`, `aggregators` and `secretstores` map the name of a plugin to a list of tables,
every table is an instance of the plugin (`[[inputs.cpu]]`), mappings become tables and lists of mappings become arrays of tables.
Telegraf needs at least one output and one input.

```yaml
telegraf_config:
  agent:
    interval: '30s'
    flush_interval: '30s'
    omit_hostname: true
  global_tags:
    site: 'home'
  outputs:
    influxdb_v2:
      - urls: [ 'https://influxdb.example.org:8086' ]
        token: '@{secrets:telegraf_influx_token}'
        organization: 'home'
        bucket: 'telegraf'
  inputs:
    ping:
      - urls: [ 'router.example.org' ]
    snmp:
      - agents: [ 'udp://switch.example.org:161' ]
        tags:
          device: 'switch'
        field:
          - name: 'uptime'
            oid: 'RFC1213-MIB::sysUpTime.0'
  processors:
    rename:
      - replace:
          - measurement: 'ping'
            dest: 'latency'
```

becomes

```toml
[agent]
interval = "30s"
flush_interval = "30s"
omit_hostname = true

[global_tags]
site = "home"

[[outputs.influxdb_v2]]
urls = ["https://influxdb.example.org:8086"]
token = "@{secrets:telegraf_influx_token}"
organization = "home"
bucket = "telegraf"

[[inputs.ping]]
urls = ["router.example.org"]

[[inputs.snmp]]
agents = ["udp://switch.example.org:161"]

[[inputs.snmp.field]]
name = "uptime"
oid = "RFC1213-MIB::sysUpTime.0"

[inputs.snmp.tags]
device = "switch"

[[processors.rename]]
[[processors.rename.replace]]
measurement = "ping"
dest = "latency"

[[secretstores.docker]]
id = "secrets"
```

The allowed keys of the first level are `monitoring_telegraf__config_allowed`, generated from the tables `loadConfig` of `config/config.go` of Telegraf v1.40.4 reads,
without the legacy aliases `tags` and `plugins`. Telegraf reads any other table as an input, the allow list prevents unexpected behavior by accident, e.g. by a typo.
`telegraf config check` of the image checks the plugins and their options before the file is replaced.

### Secrets

Secrets are entries of `telegraf_secrets` with `name` and `data`, the role creates them with `podman secret`
and mounts them to `/run/secrets/<name>` (owner `telegraf` of the image, uid 100, gid 101, mode `0400`).
With secrets the role adds the [Docker secret store](https://github.com/influxdata/telegraf/tree/master/plugins/secretstores/docker)
`[[secretstores.docker]]` with the id `secrets`, plugins reference a secret with `@{secrets:<name>}`:

```yaml
telegraf_secrets:
  - name: 'telegraf_influx_token'
    data: "{{ vault_telegraf_influx_token }}"
telegraf_config:
  outputs:
    influxdb_v2:
      - urls: [ 'https://influxdb.example.org:8086' ]
        token: '@{secrets:telegraf_influx_token}'
```

Only options with secret store support take references, the README of a plugin lists them in the section `Secret-store support`.
The entries have no `target`: the options of the plugins are part of lists (several instances of a plugin),
a path in the configuration would need the position in the list, the configuration references the secret itself.
The role checks instead that every secret is referenced with `@{secrets:<name>}` in `telegraf_config`
and that the fields carrying secrets (`monitoring_telegraf__config_secret_keys`, e.g. `password`, `token`, `basic_password`)
contain no plain values, only references of a secret store, `null` or an empty string are allowed.
A changed secret restarts the running service.

### Allowed variables

`telegraf_environment` has no default, without it the container has no environment.
The entrypoint of the image reads no variables, Telegraf and its library gopsutil only read `monitoring_telegraf__environment_allowed`:
`TZ`, the variables of gopsutil v4.26.10 for the file systems of the host (`HOST_PROC`, `HOST_SYS`, `HOST_ETC`, `HOST_VAR`, `HOST_RUN`, `HOST_DEV`, `HOST_ROOT`, `HOST_PROC_MOUNTINFO`)
and `HOST_MOUNT_PREFIX` of the input `disk`.
The list prevents unexpected behavior by accident, options belong to `telegraf_config`, secrets to `telegraf_secrets`.
The environment of the container is checked after merging `telegraf_container`.

```yaml
telegraf_environment:
  HOST_PROC: '/host/proc'
  HOST_MOUNT_PREFIX: '/host'
telegraf_container:
  volumes:
    - '/opt/telegraf/telegraf.conf:/etc/telegraf/telegraf.conf:ro'
    - '/proc:/host/proc:ro'
    - '/:/host:ro'
```

### Container

The container is `monitoring_telegraf__podman_container_default` merged with `telegraf_container`, the merge is not recursive.
The default has the capability `cap_net_raw` (`cap_add`) for the input `ping` and the volume of the configuration,
`telegraf_container.volumes` replaces the volumes completely and has to contain the volume of the configuration.
The time zone is set by podman (`telegraf_timezone`), the image has no variable `TZ` and needs no `/etc/localtime`.
`requires`, `wants`, `after`, `part_of`, `binds_to` and `requires_mounts_for` of `telegraf_container` become the dependencies of the quadlet unit.

### Validation

All checks run before anything changes, the messages name only the failing checks:

- `Render the configuration` evaluates the variables once, a failing template or `telegraf_config` that is no dictionary stops the role there,
- `telegraf_secrets` is a list of entries with `name` and `data`, the names are unique, the data are strings without line breaks,
- the keys of the first level of `telegraf_config`, `agent` and `global_tags` are dictionaries, plugins are dictionaries of lists of tables, at least one output and one input,
- the fields carrying secrets are references, every secret is referenced,
- `telegraf_environment` is a dictionary, the variables of the container are allowed and contain no line breaks,
- `telegraf config check` of the image checks the configuration in a throwaway container without network before it is replaced,
  it resolves the references of the secret store, the container gets placeholder files of the secrets, the podman secrets are created after the check.

### Check mode

The role runs with `--check`, also on a host where it never ran, and reports the changes of the configuration and the quadlet unit,
the service is neither started nor restarted.

### Restart and updates

Telegraf is restarted if it was running and the configuration, a secret or the quadlet unit changed, otherwise it is started and enabled.
Telegraf exits if a plugin cannot start, the role waits until the service runs for 10 seconds without an automatic restart and reports the journal otherwise.
Updates of the image are done by `container_update` with `telegraf_autoupdate_enabled: true` and `telegraf_autoupdate_schedule`, without `telegraf_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

| Former variable | Now |
|---|---|
| `telegraf_agent_interval`, `telegraf_agent_round_interval`, `telegraf_agent_metric_batch_size`, `telegraf_agent_metric_buffer_limit`, `telegraf_agent_collection_jitter`, `telegraf_agent_flush_interval`, `telegraf_agent_flush_jitter`, `telegraf_agent_precision`, `telegraf_agent_omit_hostname` | `interval`, `round_interval`, … in `telegraf_config.agent`, the section replaces the default completely |
| `telegraf_agent` | `telegraf_config.agent` |
| `telegraf_global_tags` | `telegraf_config.global_tags` |
| `telegraf_outputs`, `telegraf_inputs` (lists with `plugin`) | `telegraf_config.outputs`, `telegraf_config.inputs`, `{<plugin>: [<settings without plugin>, …]}` |
| `telegraf_processors`, `telegraf_aggregators` (lists with `type`) | `telegraf_config.processors`, `telegraf_config.aggregators`, `{<type>: [<settings without type>, …]}` |
| `telegraf_publish`, `telegraf_volumes` | `publish`, `volumes` of `telegraf_container`, `volumes` replaces the volumes of the role and contains the volume of the configuration |
| `telegraf_secrets` with `target` and `${TARGET}` in the configuration | `telegraf_secrets` with `name` and `data`, `@{secrets:<name>}` in an option with secret store support |
| `TZ` of `telegraf_environment` (default `telegraf_timezone`) | removed, podman sets the time zone with `telegraf_timezone` |

Example:

```yaml
# before
telegraf_agent_interval: '30s'
telegraf_outputs:
  - plugin: 'influxdb_v2'
    urls: [ 'https://influxdb.example.org:8086' ]
    token: '${INFLUX_TOKEN}'
telegraf_inputs:
  - plugin: 'cpu'
  - plugin: 'mem'
telegraf_secrets:
  - name: 'telegraf_influx_token'
    data: "{{ vault_telegraf_influx_token }}"
    target: 'INFLUX_TOKEN'

# now
telegraf_config:
  agent:
    interval: '30s'
    flush_interval: '10s'
    omit_hostname: true
  outputs:
    influxdb_v2:
      - urls: [ 'https://influxdb.example.org:8086' ]
        token: '@{secrets:telegraf_influx_token}'
  inputs:
    cpu: [ {} ]
    mem: [ {} ]
telegraf_secrets:
  - name: 'telegraf_influx_token'
    data: "{{ vault_telegraf_influx_token }}"
```

Changed behavior:

- The volumes `/etc/localtime` and `/etc/timezone` and the default of `TZ` are removed.
- Variables of `telegraf_environment` besides the allowed ones stop the role, environment variables in the configuration (`${VARIABLE}`) are no longer available for options.
- Fields carrying secrets with plain values and secrets that are not referenced stop the role.
- `telegraf config check` checks the configuration before it is replaced, the role waits until Telegraf runs.
- The quadlet unit has the dependencies `RequiresMountsFor`, `Wants`, `After`, `PartOf` and `BindsTo` of `telegraf_container` besides `Requires`.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs, `prepare` creates the podman network, a directory for the metrics and pulls the image.

| Platform | Test case |
|---|---|
| `molecule-telegraf-default` | The mandatory values and a configuration with the input `mem` and the output `file` to stdout |
| `molecule-telegraf` | A secret in the secret store, an own agent, global tags, the outputs `file` (volume) and `prometheus_client` with basic authentication, `HOST_MOUNT_PREFIX` |

- `check` runs `converge` with `--check` on the new VMs.
- `side_effect` runs the role with invalid variables (tasks marked `expect ERROR`, the quadlet unit and the configuration stay unchanged):
  `telegraf_config` no dictionary, an unknown key, no output, a plugin that is no list, a plain password, a secret not referenced, a line break in a secret,
  a secret without data, `telegraf_environment` no dictionary, an unknown variable, a line break in the environment of the container and an unknown option of a plugin (`telegraf config check`).
  Afterwards it changes the secret on `molecule-telegraf`, the service has to restart, and runs the role again on `molecule-telegraf-default`, the service must not restart.
- `verify` checks the quadlet unit (image, volume, capability, secrets), the configuration (owner, mode, secret store, no secret), the time zone without `TZ`, no automatic restarts,
  the owner and mode of the secret file as the user `telegraf`, the metrics of `prometheus_client` with the changed password (the former one is rejected) and the global tags in the metrics file.

```
cd monitoring_telegraf
MOLECULE_TART_IMAGE='debian' molecule test
```
