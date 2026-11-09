Prometheus runs in the container image [prom/prometheus](https://hub.docker.com/r/prom/prometheus) (`latest` by default) as podman quadlet.
The configuration is generated from variables and mounted read-only to `/etc/prometheus/prometheus.yml`, Prometheus reads it with `--config.file`.

### Configuration

`prometheus_config` is the content of [prometheus.yml](https://prometheus.io/docs/prometheus/latest/configuration/configuration/) as dictionary,
every key replaces the key of the default completely.
The default is `prometheus.yml` of the image: `global` with `scrape_interval` and `evaluation_interval` of `15s`
and the job `prometheus` scraping Prometheus itself on `localhost:9090`.

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

Ports, volumes and flags are changed with `prometheus_container`, it is merged over the default of the container.
The merge is not recursive, `publish`, `volumes` and `command` replace the lists of the default completely.
The default starts Prometheus with the flags of the image, `--config.file=/etc/prometheus/prometheus.yml` and `--storage.tsdb.path=/prometheus`,
and mounts `/etc/localtime`, `/etc/timezone`, the configuration, the rule files and the data directory,
further [flags](https://prometheus.io/docs/prometheus/latest/command-line/prometheus/) or volumes need the complete list:

```yaml
prometheus_container:
  publish: [ '9090:9090' ]
  command:
    - '--config.file=/etc/prometheus/prometheus.yml'
    - '--storage.tsdb.path=/prometheus'
    - '--storage.tsdb.retention.time=30d'
```

### Secrets

Prometheus does not replace environment variables in the configuration, passwords and tokens are read from files.
`prometheus_secrets` creates podman secrets, every entry needs `name` and `data`,
the secret is mounted to `/run/secrets/<name>` and is used with `password_file`, `bearer_token_file` or `credentials_file` in the configuration.
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

### Data

The time series database is stored in `<prometheus_home>/data`, mounted to `/prometheus`.
The role creates the directory for the user `nobody` (65534) of the image.

### Validation

The role checks before any change that the names of the rule files and secrets consist of letters, digits, `.`, `_` and `-`,
that the rule files are dictionaries and that the secrets have `name` and `data`.
If `prometheus_config` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.
`promtool` of the image checks the rule files and the configuration in a throwaway container before they are replaced,
the rule files first, so an invalid rule fails before the configuration changes.
The configuration is checked with `--syntax-only`, the files it references are not available in the throwaway container.

### Restart and updates

Prometheus is restarted if it was running and the configuration, a rule file, a secret or the quadlet unit changed, otherwise it is started and enabled.
Updates of the image are done by `container_update` with `prometheus_autoupdate_enabled: true` and `prometheus_autoupdate_schedule`,
without `prometheus_autoupdate_schedule` the schedule of `container_update` is used.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-prometheus-default` | Without `prometheus_config`, Prometheus scrapes itself like the image |
| `molecule-prometheus` | Own scrape job with `basic_auth` and the password from a secret, two rule files, the retention as flag in `prometheus_container.command` |

`prepare` creates the podman network and pulls the image.
`side_effect` runs the role with `prometheus_config` not a dictionary, an invalid name of a rule file, a secret without data, an invalid rule and an invalid configuration and checks that it fails with the expected message
and the configuration and the quadlet unit are unchanged (tasks marked `expect ERROR`),
then it changes the scrape interval and removes a rule file on `molecule-prometheus`, Prometheus has to restart.
`verify` checks the quadlet unit, the service, the owner of the data directory, the rule files and with the API of Prometheus
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
