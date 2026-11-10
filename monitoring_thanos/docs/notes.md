Thanos runs in the container image [thanosio/thanos](https://hub.docker.com/r/thanosio/thanos) as podman quadlet.
The image has no tag `latest`, `thanos_version` is mandatory, e.g. `v0.42.5`.

### Components

Thanos consists of several [components](https://thanos.io/tip/thanos/getting-started.md/), they may run on the same host.
`thanos_component` selects the component the role runs, the container is named `thanos-<component>`.
The role supports the components `sidecar`, `receive`, `query`, `store`, `compact` and `rule`.
`receive`, `store`, `compact` and `rule` keep their data in `<thanos_home>/data`, the role creates it owned by user `nobody` (65534).
All components serve their HTTP endpoints (`/-/ready`, `/metrics`) on port `10902`, all but `compact` serve gRPC on port `10901`.

### Sidecar

The [sidecar](https://thanos.io/tip/components/sidecar.md/) runs next to Prometheus,
it serves the StoreAPI on port `10901` and its HTTP endpoints on port `10902`.
`thanos_prometheus_url` is the URL of Prometheus, `http://prometheus:9090` by default,
`thanos_prometheus_data` is the directory of the TSDB of Prometheus on the host, it is mounted to `/prometheus`.
The sidecar runs as user `nobody` (65534) like Prometheus, the owner of the TSDB, because it writes `thanos.shipper.json` there.

Prometheus needs `external_labels` that identify it uniquely in the Thanos system, the sidecar is not ready without them.
To upload blocks to the object storage, the local compaction of Prometheus has to be disabled with equal block durations,
with [monitoring_prometheus](https://ansible-roles.org/roles/monitoring-prometheus):

```yaml
prometheus_config:
  global:
    scrape_interval: '15s'
    evaluation_interval: '15s'
    external_labels:
      cluster: 'home'
      replica: 'prometheus1'
prometheus_container:
  command:
    - '--config.file=/etc/prometheus/prometheus.yml'
    - '--storage.tsdb.path=/prometheus'
    - '--storage.tsdb.min-block-duration=2h'
    - '--storage.tsdb.max-block-duration=2h'

thanos_component: 'sidecar'
thanos_version: 'v0.42.5'
thanos_prometheus_url: 'http://prometheus:9090'
thanos_prometheus_data: '/opt/prometheus/data'
```

### Receive

[Receive](https://thanos.io/tip/components/receive.md/) stores the samples Prometheus sends with remote write,
it serves the StoreAPI on port `10901`, its HTTP endpoints on port `10902` and remote write on port `19291` with the path `/api/v1/receive`.
`thanos_home` is the directory on the host, the TSDB is stored in `<home>/data`, the role creates it owned by user `nobody` (65534).
Without a hashring receive runs as single node and stores all samples itself.

Receive refuses to start without external labels, the default command sets `receive_replica` to `thanos_hostname`.
Other labels and flags like `--tsdb.retention` (`15d` by default) are set with `thanos_container.command`.

```yaml
prometheus_config:
  global:
    scrape_interval: '15s'
    evaluation_interval: '15s'
    external_labels:
      cluster: 'home'
  remote_write:
    - url: 'http://thanos-receive:19291/api/v1/receive'

thanos_component: 'receive'
thanos_version: 'v0.42.5'
thanos_home: '/srv/container/thanos-receive'
thanos_hostname: 'thanos-receive'
```

### Query

[Query](https://thanos.io/tip/components/query.md/) answers PromQL queries with the data of the StoreAPIs of the other components,
its HTTP API and UI are on port `10902`.
`thanos_query_endpoints` is the mandatory list of the gRPC addresses of the StoreAPIs (sidecar, receive, store, rule),
the role passes it as `--endpoint.sd-config`.
The default command deduplicates the replica labels `replica`, `receive_replica` and `rule_replica`.

```yaml
thanos_component: 'query'
thanos_version: 'v0.42.5'
thanos_hostname: 'thanos-query'
thanos_query_endpoints:
  - 'thanos-sidecar:10901'
  - 'thanos-store:10901'
  - 'thanos-rule:10901'
```

### Store

[Store](https://thanos.io/tip/components/store.md/) serves the blocks of the object storage with the StoreAPI, `thanos_objstore` is mandatory.
`<thanos_home>/data` is a cache, it is rebuilt if removed.

```yaml
thanos_component: 'store'
thanos_version: 'v0.42.5'
thanos_home: '/srv/container/thanos-store'
thanos_hostname: 'thanos-store'
thanos_objstore:
  type: 'S3'
  config:
    bucket: 'thanos'
    endpoint: 's3.example.org'
    access_key: 'thanos'
    secret_key: "{{ vault_thanos_secret_key }}"
```

### Compact

[Compact](https://thanos.io/tip/components/compact.md/) compacts and downsamples the blocks of the object storage, `thanos_objstore` is mandatory.
Only one compact may run per bucket. It runs with `--wait`, so it does not exit after one run, and serves only HTTP on port `10902`.
`<thanos_home>/data` is its working directory. Retention flags like `--retention.resolution-raw` are set with `thanos_container.command`.

### Rule

[Rule](https://thanos.io/tip/components/rule.md/) evaluates rules against query and serves the results with the StoreAPI.
`thanos_query_url` is the mandatory HTTP URL of query, e.g. `http://thanos-query:10902`.
The default command sets the external label `rule_replica` to `thanos_hostname`,
the TSDB is stored in `<thanos_home>/data` for 48h, with `thanos_objstore` the blocks are uploaded.
Alertmanagers (`--alertmanagers.url`) and the evaluation interval (`--eval-interval`, `1m` by default) are set with `thanos_container.command`.

`thanos_rules` is a dictionary of [rule files](https://thanos.io/tip/components/rule.md/#configuring-rules) like `prometheus_rules`,
the key is the name of the file without `.yml` (letters, digits, `.`, `_` and `-`), the value its content.
The role writes them to `<thanos_home>/rules` after checking them with `thanos tools rules-check`,
mounts the directory read-only to `/etc/thanos/rules` and removes rule files that are not declared.

```yaml
thanos_component: 'rule'
thanos_version: 'v0.42.5'
thanos_home: '/srv/container/thanos-rule'
thanos_hostname: 'thanos-rule'
thanos_query_url: 'http://thanos-query:10902'
thanos_rules:
  node:
    groups:
      - name: 'node'
        rules:
          - record: 'instance:node_cpu:rate5m'
            expr: 'sum by (instance) (rate(node_cpu_seconds_total{mode!="idle"}[5m]))'
```

### Object storage

`thanos_objstore` is the content of [bucket.yml](https://thanos.io/tip/thanos/storage.md/) as dictionary, it needs `type`.
The role stores it as podman secret `<container name>-objstore` (`thanos-<component>-objstore` by default) and mounts it to `/etc/thanos/bucket.yml`,
so the credentials are neither a file on the host nor part of the quadlet unit.
Store and compact need `thanos_objstore`.
Without it the secret is removed and sidecar, receive and rule upload nothing, they only serve the StoreAPI.

```yaml
thanos_objstore:
  type: 'S3'
  config:
    bucket: 'thanos'
    endpoint: 's3.example.org'
    access_key: 'thanos'
    secret_key: "{{ vault_thanos_secret_key }}"
```

### Container

Ports, volumes and flags are changed with `thanos_container`, it is merged over the default of the container.
The merge is not recursive, `publish`, `volumes`, `command` and `environment` replace the values of the default completely.
Every default mounts `/etc/localtime` and `/etc/timezone`, with an object storage the command contains `--objstore.config-file`:

- `sidecar` mounts the TSDB of Prometheus to `/prometheus`, the command has `--tsdb.path` and `--prometheus.url`
- `receive` mounts `<home>/data` to `/var/thanos/receive`, the command has `--tsdb.path` and `--label`
- `query` mounts nothing else, the command has `--endpoint.sd-config` and `--query.replica-label`
- `store` mounts `<home>/data` to `/var/thanos/store`, the command has `--data-dir`
- `compact` mounts `<home>/data` to `/var/thanos/compact`, the command has `--wait` and `--data-dir`
- `rule` mounts `<home>/data` to `/var/thanos/rule` and `<home>/rules` read-only to `/etc/thanos/rules`,
  the command has `--data-dir`, `--rule-file`, `--query` and `--label`

Further flags (see the flags of every [component](https://thanos.io/tip/thanos/getting-started.md/)) or volumes need the complete list.
The command is written space separated into the quadlet unit,
an argument containing `"`, e.g. a label, has to be enclosed in `'`, otherwise the `"` are lost:

```yaml
thanos_container:
  publish: [ '10901:10901' ]
  command:
    - 'sidecar'
    - '--tsdb.path=/prometheus'
    - '--prometheus.url=http://prometheus:9090'
    - '--objstore.config-file=/etc/thanos/bucket.yml'
    - '--shipper.upload-compacted'
```

```yaml
thanos_container:
  command:
    - 'rule'
    - '--data-dir=/var/thanos/rule'
    - '--rule-file=/etc/thanos/rules/*.yml'
    - '--query=http://thanos-query:10902'
    - '''--label=rule_replica="thanos-rule"'''
    - '--alertmanagers.url=http://alertmanager:9093'
```

### Validation

The role checks before any change that `thanos_component` is supported, that `thanos_objstore` is a dictionary with `type`
and is set for store and compact, that `thanos_query_endpoints` of query is a non-empty list of addresses
and that `thanos_rules` is a dictionary of dictionaries with valid names.
If `thanos_container` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Restart and updates

The container is restarted if it was running and the secret of the object storage, the rule files or the quadlet unit changed,
otherwise it is started and enabled.
Updates of the image are done by `container_update` with `thanos_autoupdate_enabled: true` and `thanos_autoupdate_schedule`,
without `thanos_autoupdate_schedule` the schedule of `container_update` is used.
The image has no tag `latest`, an update needs a new `thanos_version`.

### Multiple instances

`tasks/loop.yml` runs the role for every entry in `thanos_instances`, e.g. a sidecar for every Prometheus on the host.
Every entry takes the variables without the prefix `thanos_`, e.g. `component`, `home`, `ip`, `objstore`, `query_endpoints`, `rules` and `container`,
missing keys get the defaults of the role.
Every instance needs its own container name (`container.name`), the secret of the object storage is named after it.

Include `tasks/loop.yml` in the play instead of the role:

```yaml
- name: 'Configure host.example.org'
  become: 'yes'
  hosts: 'host23'
  tasks:
    - tags: [ 'monitoring_thanos' ]
      ansible.builtin.include_tasks:
        file: 'roles/monitoring_thanos/tasks/loop.yml'
```

The instances are defined in `thanos_instances`, e.g. in the host variables:

```yaml
thanos_instances:
  - component: 'sidecar'
    version: 'v0.42.5'
    ip: '192.168.99.41'
    network: 'podman99'
    hostname: 'thanos-sidecar-home'
    timezone: 'Europe/Berlin'
    prometheus_url: 'http://prometheus-home:9090'
    prometheus_data: '/srv/container/prometheus-home/data'
    container:
      name: 'thanos-sidecar-home'
  - component: 'sidecar'
    version: 'v0.42.5'
    ip: '192.168.99.43'
    network: 'podman99'
    hostname: 'thanos-sidecar-lab'
    timezone: 'Europe/Berlin'
    prometheus_url: 'http://prometheus-lab:9090'
    prometheus_data: '/srv/container/prometheus-lab/data'
    objstore:
      type: 'S3'
      config:
        bucket: 'thanos-lab'
        endpoint: 's3.example.org'
        access_key: 'thanos'
        secret_key: "{{ vault_thanos_lab_secret_key }}"
    container:
      name: 'thanos-sidecar-lab'
```

### Tests

The molecule scenario `default` runs the role in three [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-thanos-default` | Sidecar without object storage, it only serves the StoreAPI |
| `molecule-thanos` | Sidecar uploading to the object storage `FILESYSTEM`, the volume of the bucket is added with `thanos_container.volumes` |
| `molecule-thanos-receive` | Receive without object storage, Prometheus sends its samples with remote write |

`prepare` creates the podman network, pulls the images, creates the directory of the bucket
and runs Prometheus with `monitoring_prometheus`, with external labels and equal block durations or remote write to receive.
`side_effect` runs the role with `thanos_container` not a dictionary, an unknown component, an object storage without `type`,
store without object storage, `thanos_query_endpoints` not a list and an invalid name of a rule file
and checks that it fails with the expected message and the quadlet unit is unchanged (tasks marked `expect ERROR`),
then it changes the object storage on `molecule-thanos`, the secret changes and the sidecar has to restart.
`verify` checks the quadlet unit, the service, the secret and with the HTTP endpoints of the sidecar
that it is ready, connected to Prometheus and uploads only with an object storage.
For receive it checks the external label in the command of the container, the data directory
and that the TSDB of the tenant `default-tenant` received samples of Prometheus.

The molecule scenario `loop` tests `tasks/loop.yml` in one VM `molecule-thanos-loop`.
`prepare` runs two Prometheus `prometheus-a` and `prometheus-b` with `monitoring_prometheus`,
`converge` deploys the sidecars `thanos-sidecar-a` (without object storage) and `thanos-sidecar-b` (object storage `FILESYSTEM`) from `thanos_instances`,
each connected to its own Prometheus.
`verify` checks every instance like the scenario `default` and that the quadlet units only contain the secret of their own instance.

The molecule scenario `stack` runs all components on one VM `molecule-thanos-stack` with `tasks/loop.yml`.
`prepare` runs Prometheus with `monitoring_prometheus`, `converge` deploys sidecar, store and compact sharing the bucket `FILESYSTEM`,
rule with a recording rule `thanos:up:count` and query connected to sidecar, store and rule.
`verify` checks the quadlet unit, the service and the readiness of every instance, the rule file and the external label of rule,
and with the API of query that sidecar, store and rule are connected and the samples of Prometheus and the recording rule are returned.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd monitoring_thanos
MOLECULE_TART_IMAGE='debian' molecule test
MOLECULE_TART_IMAGE='debian' molecule test -s loop
MOLECULE_TART_IMAGE='debian' molecule test -s stack
```
