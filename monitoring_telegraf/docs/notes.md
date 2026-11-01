Telegraf runs in the official container image [telegraf](https://hub.docker.com/_/telegraf) (`alpine` by default) as podman quadlet.
The configuration is generated from variables and mounted read-only to `/etc/telegraf/telegraf.conf`.

### Requirements

The configuration is rendered with the filter [`community.general.to_toml`](https://docs.ansible.com/ansible/latest/collections/community/general/to_toml_filter.html),
which needs the Python library [tomlkit](https://pypi.org/project/tomlkit/) on the Ansible controller, e.g. `pip install tomlkit` in the environment of Ansible and molecule.

### Configuration

Outputs and inputs are lists, every element needs `plugin`, processors and aggregators need `type`.
All other keys of an element are the settings of the plugin, mappings become tables and lists of mappings become arrays of tables.
Several elements with the same plugin become several instances of the plugin.

```yaml
telegraf_global_tags:
  site: 'home'
telegraf_agent_interval: '30s'
telegraf_agent:
  debug: true
telegraf_outputs:
  - plugin: 'influxdb_v2'
    urls: [ 'https://influxdb.example.org:8086' ]
    token: '${INFLUX_TOKEN}'
    organization: 'home'
    bucket: 'telegraf'
telegraf_inputs:
  - plugin: 'ping'
    urls: [ 'router.example.org' ]
  - plugin: 'snmp'
    agents: [ 'udp://switch.example.org:161' ]
    tags:
      device: 'switch'
    field:
      - name: 'uptime'
        oid: 'RFC1213-MIB::sysUpTime.0'
telegraf_processors:
  - type: 'rename'
    replace:
      - measurement: 'ping'
        dest: 'latency'
```

becomes

```toml
[global_tags]
site = "home"

[agent]
interval = "30s"
...
debug = true

[[outputs.influxdb_v2]]
urls = ["https://influxdb.example.org:8086"]
token = "${INFLUX_TOKEN}"
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
```

The settings of the section `[agent]` are set with the variables `telegraf_agent_*` and `telegraf_agent` for all other settings.
Empty sections are not written.
The role fails before it changes anything if there is no output or no input, or if an element misses `plugin` or `type`.

The container has the capability `NET_RAW` for the input `ping`.
Additional volumes, e.g. for sockets or files read by inputs, are added with `telegraf_volumes`:

```yaml
telegraf_volumes:
  - '/run/mosquitto:/run/mosquitto:ro'
```

### Environment and secrets

Telegraf replaces `${VARIABLE}` in the configuration with environment variables.
Variables are set with `telegraf_environment`, which is merged over the defaults of the role (`TZ`).
Secrets, e.g. tokens and passwords, are passed as podman secrets with `telegraf_secrets` and must not be set in `telegraf_environment`,
so they are neither part of the configuration file nor of the quadlet unit:

```yaml
telegraf_secrets:
  - name: 'telegraf_influx_token'
    data: "{{ vault_telegraf_influx_token }}"
    target: 'INFLUX_TOKEN'
```

### Restart and updates

Telegraf is restarted if it was running and the configuration, a secret or the quadlet unit changed, otherwise it is started and enabled.
Updates of the image are done by `container_update` with `telegraf_autoupdate_enabled: true` and `telegraf_autoupdate_schedule`.

### Migration

| Before | Now |
|---|---|
| `telegraf_use_podman: false`, installation from the InfluxData repository | removed, only podman |
| `telegraf_sudoers`, `telegraf_systemd_override_unit`, `telegraf_systemd_override_service` | removed with the native installation |
| `podman___update_mode` | `telegraf_autoupdate_enabled` |
| tokens and passwords in `telegraf_outputs` or `telegraf_inputs` | `telegraf_secrets` and `${VARIABLE}` in the configuration |
| `telegraf_outputs` and `telegraf_inputs` mandatory by `mandatory` | checked by the role |
| configuration from a Jinja template | `community.general.to_toml`, strings are escaped |

### Tests

The molecule scenario `default` uses tart with one VM `molecule-telegraf`.
`prepare` creates the podman network and a directory for the metrics.
Telegraf collects `cpu` and `mem` and writes them with the output `file` to the directory,
the global tags use a secret (`${MOLECULE_SECRET}`) and an environment variable (`${MOLECULE_ENV}`).
`side_effect` changes the environment variable and checks that telegraf was restarted.
`verify` checks the quadlet unit, the secret, parses the configuration as TOML and checks that the metrics carry the secret and the changed environment variable.

```
cd monitoring_telegraf
MOLECULE_TART_IMAGE='debian' molecule test
```
