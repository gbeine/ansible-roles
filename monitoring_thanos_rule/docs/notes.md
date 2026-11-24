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

### Object storage

`thanos_rule_objstore` is the content of [bucket.yml](https://thanos.io/tip/thanos/storage.md/) as dictionary, with it rule uploads the blocks of its results.
The name stays `objstore` instead of `config`, it is the configuration of the object storage, not of rule, the flags are part of the command.
The role writes it to `<home>/bucket.yml` and mounts the file read-only to `/etc/thanos/bucket.yml`, the command gets `--objstore.config-file`.
Without `thanos_rule_objstore` the role removes bucket.yml, rule uploads no blocks and only serves its results with the StoreAPI.
The keys of the first level are `type`, `config` and `prefix`, `type` is one of the providers of github.com/thanos-io/objstore
(`FILESYSTEM`, `GCS`, `S3`, `AZURE`, `SWIFT`, `COS`, `ALIYUNOSS`, `BOS`, `OCI`, `OBS`),
the allow lists are generated from `client/factory.go` and `objstore.go` of the version of Thanos v0.42.5 and prevent unexpected behavior by accident.

```yaml
thanos_rule_objstore:
  type: 'S3'
  config:
    bucket: 'thanos'
    endpoint: 's3.example.org'
    access_key: 'thanos'
thanos_rule_secrets:
  - name: 'thanos_rule_s3_secret_key'
    data: "{{ vault_thanos_secret_key }}"
    target: 'config.secret_key'
```

### Secrets

The providers read their credentials (e.g. `secret_key` of S3) only from bucket.yml, they cannot read them from files,
but Thanos replaces `$(VARIABLE)` in bucket.yml with the environment (`extflag.WithEnvSubstitution` of `--objstore.config-file`).
The secrets are entries of `thanos_rule_secrets` with `name`, `data` and `target`, the role creates them with `podman secret`
and passes them with `type=env` as `THANOS_SECRET_<TARGET>` (the target in upper case, dots replaced by `_`).
The target is the path of the option in `thanos_rule_objstore`, the role writes the reference `"$(THANOS_SECRET_CONFIG_SECRET_KEY)"` there,
so bucket.yml and the quadlet unit contain no credentials.

- The last key of a target is one of the options carrying secrets (`monitoring_thanos_rule__objstore_secret_keys`, e.g. `secret_key`, `session_token`,
  `service_account`, `storage_account_key`, `password`), these options must not be set in `thanos_rule_objstore`, `null` or an empty string are allowed.
- A target must not be set in `thanos_rule_objstore`, its path leads through dictionaries and every target is set once, secrets need an object storage.
- The data of a secret is a string without line breaks, `"` and `\`, the reference is double-quoted in bucket.yml,
  a key or service account file has to be a single line (e.g. the JSON of `service_account`).

A changed secret restarts the running rule.

### Allowed variables

Thanos reads no environment variables besides the references in bucket.yml, the role only allows `TZ` in `thanos_rule_environment`.
`thanos_rule_environment` has no default, without it the container has no environment, the time zone is set by podman with `thanos_rule_timezone`.
This prevents unexpected behavior by accident, e.g. by a variable meant for another image, the secrets are set with `thanos_rule_secrets`.
The check uses the environment of the container after merging `thanos_rule_container`.

### Container

Ports, volumes, flags and dependencies (`requires`, `wants`, `after`, `part_of`, `binds_to`, `requires_mounts_for`) are changed with `thanos_rule_container`, it is merged over the default of the container.
The merge is not recursive, `publish`, `volumes` and `command` replace the values of the default completely.
The default mounts `<home>/data` to `/var/thanos/rule`, `<home>/rules` read-only to `/etc/thanos/rules`
and with object storage `<home>/bucket.yml` to `/etc/thanos/bucket.yml`,
the command has `--data-dir`, `--rule-file`, `--query`, `--label` and with object storage `--objstore.config-file`.
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

The role checks before any change, the messages name only the failing checks:

- `Render the configuration` evaluates the variables once, a missing `thanos_rule_query_url`, `thanos_rule_container` that is no dictionary
  or a failing template (e.g. an unknown filter) stop the role there
- `thanos_rule_secrets` is a list of entries with `name`, `data` and `target` with unique names
- `thanos_rule_objstore` is a dictionary, if it is set with the allowed keys, a known `type`, `config` is a dictionary, the options carrying secrets are not set
- the targets of the secrets are known, unique, not set in `thanos_rule_objstore` and lead through dictionaries, the data are valid,
  secrets need an object storage
- `thanos_rule_rules` is a dictionary of dictionaries with names of letters, digits, `.`, `_` and `-`, `thanos_rule_query_url` is an HTTP URL
- `thanos_rule_environment` is a dictionary without line breaks, only `TZ` is set in the environment of the container
- `thanos tools rules-check` accepts every rule file before it is replaced

### Check mode

The role runs with `--check`, also on a host where it never ran, and reports the changes of the rule files, bucket.yml and the quadlet unit,
rule is neither started nor restarted.

### Restart and updates

Rule is restarted if it was running and the rule files (written or removed), bucket.yml (written or removed), a secret or the quadlet unit changed, otherwise it is started and enabled.
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
| `thanos_objstore` | `thanos_rule_objstore` without the credentials, they are entries of `thanos_rule_secrets` with the path of the option as `target` |
| `thanos_container` | `thanos_rule_container` |
| `thanos_autoupdate_enabled`, `thanos_autoupdate_schedule` | `thanos_rule_autoupdate_enabled`, `thanos_rule_autoupdate_schedule` |
| `thanos_instances`, `tasks/loop.yml` | Removed, the role runs once per host |

Changed behavior:

- bucket.yml is no longer the podman secret `thanos-rule-objstore` but the file `<home>/bucket.yml` without credentials,
  the credentials are `thanos_rule_secrets` passed in the environment, the former secret is removed with `podman secret rm thanos-rule-objstore`
- `/etc/localtime` and `/etc/timezone` are no longer mounted and `TZ` has no default, the time zone is set by podman with `thanos_rule_timezone`,
  the quadlet unit changes once and rule restarts, volumes in `thanos_rule_container` should no longer contain them
- `thanos_rule_environment` has no default and is checked against the allowed variables, unknown keys, types and plain credentials of the object storage stop the role
- `thanos_rule_query_url` has to be an HTTP URL
- the quadlet unit has the dependencies `Wants`, `After`, `PartOf`, `BindsTo` and `RequiresMountsFor` of `thanos_rule_container` besides `Requires`
- the role waits until rule is ready and shows the journal if the start fails
- the container and the directories keep their names `thanos-rule`, `<home>/data` and `<home>/rules`

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root. The VMs need access to Docker Hub.

| Platform | Test case |
|---|---|
| `molecule-thanos-rule-default` | Only the mandatory variables, no rule files, no object storage and no query, rule starts and fails the evaluations |
| `molecule-thanos-rule` | IPv6, labels, a recording and an alerting rule file and the object storage `S3` on an S3 server of rclone, the secret key is an entry of `thanos_rule_secrets` |

`prepare` creates the podman network, pulls the images, starts the S3 server (`rclone serve s3`) with the bucket `thanos`
and creates a rule file `stale.yml` that is not declared.
`check` runs `converge` with `--check` on the new VMs.
`side_effect` runs the role with invalid variables (tasks marked `expect ERROR`, the quadlet unit and bucket.yml stay unchanged):
`thanos_rule_container` and `thanos_rule_objstore` no dictionaries, an unknown type and key of the object storage, a secret key in the object storage,
a secret without target, an unknown target, a target set in the object storage, a quote in a secret, secrets without object storage,
an invalid name of a rule file, a rule file not a dictionary, a URL of query without scheme, an invalid rule (`thanos tools rules-check`),
`thanos_rule_environment` no dictionary, a line break in the environment of the container and an unknown environment variable.
Afterwards it changes a rule on `molecule-thanos-rule`, the rule file changes and rule has to restart,
and runs the role again on `molecule-thanos-rule-default`, rule must not restart.
`verify` checks the quadlet unit (secrets, time zone, no `TZ`, volume and flag of bucket.yml only with object storage), the service without automatic restarts,
bucket.yml with the reference of the secret and without the secret key or no bucket.yml without object storage,
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
