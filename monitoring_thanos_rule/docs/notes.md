[Thanos Rule](https://thanos.io/tip/components/rule.md/) runs in the container image [thanosio/thanos](https://hub.docker.com/r/thanosio/thanos) as podman quadlet `thanos-rule`.
It evaluates recording and alerting rules against query and serves the results with the StoreAPI on port `10901`,
its HTTP endpoints (`/-/ready`, `/metrics`) are on port `10902`.
The image has no tag `latest`, `thanos_rule_version` is mandatory, e.g. `v0.42.5`.

### Configuration

`thanos_rule_query_url` is the mandatory HTTP URL of query, e.g. `http://thanos-query:10902`.
`thanos_rule_home` is the directory on the host, the TSDB of the results is stored in `<home>/data` (mounted to `/var/thanos/rule`) for 48h,
the role creates it owned by user `nobody` (65534), rule runs as this user.
The default command sets the external label `rule_replica` to `thanos_rule_hostname`.
Alertmanagers (`--alertmanagers.url`) and the evaluation interval (`--eval-interval`, `1m` by default) are set with `thanos_rule_container.command`.

`thanos_rule_rules` is a dictionary of [rule files](https://thanos.io/tip/components/rule.md/#configuring-rules) like `prometheus_rules`,
the key is the name of the file without `.yml` (letters, digits, `.`, `_` and `-`), the value its content.
The role writes them to `<home>/rules` after checking them with `thanos tools rules-check` of the image in a throwaway container without network,
mounts the directory read-only to `/etc/thanos/rules` and removes rule files that are not declared.

```yaml
thanos_rule_version: 'v0.42.5'
thanos_rule_home: '/srv/container/thanos-rule'
thanos_rule_ip: '192.168.99.46'
thanos_rule_network: 'podman99'
thanos_rule_hostname: 'thanos-rule'
thanos_rule_timezone: 'Europe/Berlin'
thanos_rule_query_url: 'http://thanos-query:10902'
thanos_rule_rules:
  node:
    groups:
      - name: 'node'
        rules:
          - record: 'instance:node_cpu:rate5m'
            expr: 'sum by (instance) (rate(node_cpu_seconds_total{mode!="idle"}[5m]))'
```

### Secrets

`thanos_rule_objstore` is the content of [bucket.yml](https://thanos.io/tip/thanos/storage.md/) as dictionary, it needs `type`.
Thanos reads the credentials of the object storage only from this file, it has no file variables and no references to the environment,
so the whole file is the secret instead of entries of a list of secrets.
The role stores it as podman secret `<container name>-objstore` (`thanos-rule-objstore` by default) and mounts it to `/etc/thanos/bucket.yml`,
so the credentials are neither a file on the host nor part of the quadlet unit, the command gets `--objstore.config-file`.
Without `thanos_rule_objstore` the secret is removed and rule uploads no blocks, it only serves its results with the StoreAPI.

```yaml
thanos_rule_objstore:
  type: 'S3'
  config:
    bucket: 'thanos'
    endpoint: 's3.example.org'
    access_key: 'thanos'
    secret_key: "{{ vault_thanos_secret_key }}"
```

### Allowed variables

Thanos reads no environment variables, the role only allows `TZ` in `thanos_rule_environment`, it is set to `thanos_rule_timezone`.
This prevents unexpected behavior by accident, e.g. by a variable meant for another image.
The check uses the environment of the container after merging `thanos_rule_container`.

### Container

Ports, volumes, flags and dependencies (`requires`) are changed with `thanos_rule_container`, it is merged over the default of the container.
The merge is not recursive, `publish`, `volumes` and `command` replace the values of the default completely.
The default mounts `<home>/data` to `/var/thanos/rule` and `<home>/rules` read-only to `/etc/thanos/rules`,
the command has `--data-dir`, `--rule-file`, `--query` and `--label`.
Further flags (see the [flags of rule](https://thanos.io/tip/components/rule.md/#flags)) or volumes need the complete list.
The command is written space separated into the quadlet unit, an argument containing `"`, e.g. a label, has to be enclosed in `'`, otherwise the `"` are lost.
For a reverse proxy, e.g. Traefik, the labels are set with `thanos_rule_labels`.

```yaml
thanos_rule_container:
  command:
    - 'rule'
    - '--data-dir=/var/thanos/rule'
    - '--rule-file=/etc/thanos/rules/*.yml'
    - '--query=http://thanos-query:10902'
    - '''--label=rule_replica="thanos-rule"'''
    - '--alertmanagers.url=http://alertmanager:9093'
```

### Validation

The role checks before any change:

- `thanos_rule_rules` is a dictionary of dictionaries with valid names
- `thanos_rule_query_url` is an HTTP URL
- `thanos_rule_objstore` is a dictionary with `type`
- the values of `thanos_rule_environment` contain no line breaks
- only `TZ` is set in the environment of the container
- `thanos tools rules-check` accepts every rule file before it is replaced

If `thanos_rule_container` or `thanos_rule_environment` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Restart and updates

Rule is restarted if it was running and the secret of the object storage, the rule files or the quadlet unit changed, otherwise it is started and enabled.
If the start fails, the role shows the journal of the service.
Afterwards the role waits up to 120 seconds until `/-/ready` answers and shows the journal if rule is not ready.
Updates of the image are done by `container_update` with `thanos_rule_autoupdate_enabled: true` and `thanos_rule_autoupdate_schedule`,
without `thanos_rule_autoupdate_schedule` the schedule of `container_update` is used.
The image has no tag `latest`, an update needs a new `thanos_rule_version`.

### Migration

The role replaces the component `rule` of `monitoring_thanos`, `thanos_component` is removed.

| Former variable | Replacement |
|---|---|
| `thanos_component: 'rule'` | Removed, the role `monitoring_thanos_rule` |
| `thanos_version`, `thanos_home`, `thanos_ip`, `thanos_ipv6`, `thanos_network`, `thanos_hostname`, `thanos_timezone`, `thanos_labels` | `thanos_rule_version`, `thanos_rule_home`, `thanos_rule_ip`, `thanos_rule_ipv6`, `thanos_rule_network`, `thanos_rule_hostname`, `thanos_rule_timezone`, `thanos_rule_labels` |
| `thanos_query_url` | `thanos_rule_query_url` |
| `thanos_rules` | `thanos_rule_rules` |
| `thanos_objstore` | `thanos_rule_objstore` |
| `thanos_container` | `thanos_rule_container` |
| `thanos_autoupdate_enabled`, `thanos_autoupdate_schedule` | `thanos_rule_autoupdate_enabled`, `thanos_rule_autoupdate_schedule` |
| `thanos_instances`, `tasks/loop.yml` | Removed, the role runs once per host |

Changed behavior:

- `/etc/localtime` and `/etc/timezone` are no longer mounted, the time zone is set with `thanos_rule_timezone` and `TZ`,
  the quadlet unit changes once and rule restarts, volumes in `thanos_rule_container` should no longer contain them
- `thanos_rule_environment` sets the environment, it is checked against the allowed variables
- `thanos_rule_query_url` has to be an HTTP URL
- the role waits until rule is ready and shows the journal if the start fails
- the container, the secret and the directories keep their names `thanos-rule`, `thanos-rule-objstore`, `<home>/data` and `<home>/rules`

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root. The VMs need access to Docker Hub.

| Platform | Test case |
|---|---|
| `molecule-thanos-rule-default` | Only the mandatory variables, no rule files and no query, rule starts and fails the evaluations |
| `molecule-thanos-rule` | IPv6, labels, a recording and an alerting rule file and the upload to the object storage `FILESYSTEM` |

`prepare` creates the podman network, pulls the image, creates the directory of the bucket
and a rule file `stale.yml` that is not declared.
`side_effect` runs the role with `thanos_rule_container` not a dictionary, an object storage without `type` and not a dictionary,
an invalid name of a rule file, a rule file not a dictionary, a URL of query without scheme,
a line break in the environment and an unknown environment variable
and checks that it fails with the expected message and the quadlet unit is unchanged (tasks marked `expect ERROR`),
then it changes a rule on `molecule-thanos-rule`, the rule file changes and rule has to restart.
`verify` checks the quadlet unit without the mounts of the time zone, the service, the environment, the secret,
the external label in the command of the container, that only the declared rule files exist, the data directory owned by `nobody`,
that rule is ready and loaded the rules of every declared file.
The evaluation of the rules against query is tested by the scenario `stack` of `monitoring_thanos_query`.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd monitoring_thanos_rule
MOLECULE_TART_IMAGE='debian' molecule test
```
