Prometheus runs in the container image [prom/prometheus](https://hub.docker.com/r/prom/prometheus) (`latest` by default) as podman quadlet.
The configuration is generated from variables and mounted read-only to `/etc/prometheus/prometheus.yml`, Prometheus reads it with `--config.file`.

### Configuration

`prometheus_config` is the content of [prometheus.yml](https://prometheus.io/docs/prometheus/latest/configuration/configuration/) as dictionary,
every key replaces the key of the default completely.
The default is `prometheus.yml` of Prometheus v3.16.0: `global` with `scrape_interval` and `evaluation_interval` of `15s`
and the job `prometheus` scraping Prometheus itself on `localhost:9090`.
The keys of the first level are checked against `monitoring_prometheus__config_allowed`, generated from `Config` in `config/config.go`
of Prometheus v3.16.0, `promtool` checks the keys below.

```yaml
prometheus_config:
  global:
    scrape_interval: '30s'
    evaluation_interval: '30s'
  scrape_configs:
    - job_name: 'prometheus'
      static_configs:
        - targets: [ 'localhost:9090' ]
    - job_name: 'node'
      static_configs:
        - targets: [ 'host1.example.org:9100', 'host2.example.org:9100' ]
```

### Rules

`prometheus_rules` is a dictionary of [rule files](https://prometheus.io/docs/prometheus/latest/configuration/recording_rules/),
the key is the name of the file without `.yml` (letters, digits, `.`, `_` and `-`), the value its content.
The role writes them to `<prometheus_home>/rules`, mounts the directory read-only to `/etc/prometheus/rules`
and adds `/etc/prometheus/rules/*.yml` to `rule_files` of the configuration. Rule files that are not declared are removed.

```yaml
prometheus_rules:
  node:
    groups:
      - name: 'node'
        rules:
          - record: 'instance:node_cpu:rate5m'
            expr: 'sum by (instance) (rate(node_cpu_seconds_total{mode!="idle"}[5m]))'
          - alert: 'NodeDown'
            expr: 'up{job="node"} == 0'
            for: '5m'
```

### Container

Ports, volumes, flags and dependencies are changed with `prometheus_container`, it is merged over the default of the container.
The merge is not recursive, `publish`, `volumes`, `command` and `environment` replace the values of the default completely.
The default starts Prometheus with the flags of the image, `--config.file=/etc/prometheus/prometheus.yml` and `--storage.tsdb.path=/prometheus`,
and mounts the configuration, the rule files and the data directory,
further [flags](https://prometheus.io/docs/prometheus/latest/command-line/prometheus/) or volumes need the complete list:

```yaml
prometheus_container:
  publish: [ '9090:9090' ]
  command:
    - '--config.file=/etc/prometheus/prometheus.yml'
    - '--storage.tsdb.path=/prometheus'
    - '--storage.tsdb.retention.time=30d'
```

The dependencies of the quadlet unit are lists: `requires`, `wants`, `after`, `part_of` and `binds_to` are units,
`requires_mounts_for` are paths. They are written to `[Unit]` as `Requires=`, `Wants=`, `After=`, `PartOf=`, `BindsTo=` and `RequiresMountsFor=`.

The time zone of the container is `prometheus_timezone`, set by podman. `prometheus_environment` has no default and only takes `TZ`,
Prometheus reads no other variables, the check uses the environment of the container after merging `prometheus_container`.
This prevents unexpected behavior by accident, e.g. by a variable meant for another image.

### Secrets

Prometheus does not replace environment variables in the configuration, passwords and tokens are read from files.
`prometheus_secrets` creates podman secrets, every entry needs `name` and `data`,
the secret is mounted to `/run/secrets/<name>` and is referenced with `password_file`, `bearer_token_file` or `credentials_file` in the configuration.
So the secrets are neither part of the configuration file nor of the quadlet unit:

```yaml
prometheus_secrets:
  - name: 'prometheus_node_password'
    data: "{{ vault_prometheus_node_password }}"
prometheus_config:
  scrape_configs:
    - job_name: 'node'
      basic_auth:
        username: 'prometheus'
        password_file: '/run/secrets/prometheus_node_password'
      static_configs:
        - targets: [ 'host1.example.org:9100' ]
```

Unlike other roles the secrets have no `target`: the options carrying secrets are part of lists (e.g. `scrape_configs`, `remote_write`),
a path to the option cannot address them. The role checks instead that every secret is referenced with `/run/secrets/<name>` in `prometheus_config`
and that the fields `password`, `bearer_token`, `credentials`, `client_secret` and `secret_key` are not set, the secrets are files.

### Data

The time series database is stored in `<prometheus_home>/data`, mounted to `/prometheus`.
The role creates the directory for the user `nobody` (65534) of the image.

### Validation

The role checks before any change:

- `prometheus_secrets` is a list of entries with `name` and `data` and unique names, the data are strings without line breaks,
  every secret is referenced in `prometheus_config`, podman checks the names of the secrets
- `prometheus_config` contains only known keys on the first level and no fields carrying secrets
- `prometheus_rules` is a dictionary of dictionaries, the names consist of letters, digits, `.`, `_` and `-`
- `prometheus_environment`, if set, is a dictionary without line breaks, only `TZ` without line breaks is set in the container

If `prometheus_config` or `prometheus_container` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.
`promtool` of the image checks the rule files and the configuration in a throwaway container before they are replaced,
the rule files first, so an invalid rule fails before the configuration changes.
The configuration is checked with `--syntax-only`, the files it references are not available in the throwaway container.

### Check mode

The role runs with `--check`, also on a host where it never ran, and reports the directories, the rule files, the configuration,
the secrets and the quadlet unit. `promtool`, the start and the wait for Prometheus do not run in check mode.

### Restart and updates

Prometheus is restarted if it was running and the configuration, a rule file, a secret or the quadlet unit changed, otherwise it is started and enabled.
If the start fails, the role shows the error and the journal of the service.
Afterwards the role waits until `/-/ready` answers, Prometheus replays the write-ahead log before, and shows the journal otherwise.
Updates of the image are done by `container_update` with `prometheus_autoupdate_enabled: true` and `prometheus_autoupdate_schedule`,
without `prometheus_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

- `TZ` is not set by default anymore and `/etc/localtime` and `/etc/timezone` are not mounted anymore, the time zone is set by podman with `prometheus_timezone`.
- `prometheus_environment` is new, it only takes `TZ`.
- The names of `prometheus_secrets` are not checked by the role anymore, podman checks them. Secrets that are not referenced in `prometheus_config`
  and passwords in plain text in `prometheus_config` are rejected.
- Unknown keys on the first level of `prometheus_config` are rejected.
- `wants`, `after`, `part_of`, `binds_to` and `requires_mounts_for` of `prometheus_container` are new.
- The role waits until Prometheus is ready and shows the journal if the start fails.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-prometheus-default` | Without `prometheus_config`, Prometheus scrapes itself like the image |
| `molecule-prometheus` | Own scrape job with `basic_auth` and the password from a secret, two rule files, the retention as flag in `prometheus_container.command` |

`prepare` creates the podman network and pulls the image.
`check` runs `converge` with `--check` on the new VMs.
`side_effect` runs the role with `prometheus_config` not a dictionary, an invalid name of a rule file, a secret without data, an unknown key,
a password in `prometheus_config`, a secret that is not referenced, a line break in a secret, `prometheus_environment` not a dictionary,
an unknown variable, a line break in the environment of the container, an invalid rule and an invalid configuration
and checks that it fails with the expected message and the configuration and the quadlet unit are unchanged (tasks marked `expect ERROR`),
then it changes the scrape interval and removes a rule file on `molecule-prometheus`, Prometheus has to restart,
`molecule-prometheus-default` runs again without a change and Prometheus must not restart.
`verify` checks the quadlet unit, the service without automatic restarts, the time zone without `TZ` and without volumes of the time zone,
the owner of the data directory, the rule files and with the API of Prometheus
the scrape interval, the retention, the jobs of the targets that are up and the rule groups.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd monitoring_prometheus
MOLECULE_TART_IMAGE='debian' molecule test
```
