The role installs the [OpenTelemetry Collector](https://opentelemetry.io/docs/collector/) on Debian from the packages of the
[releases](https://github.com/open-telemetry/opentelemetry-collector-releases/releases) and writes its configuration.

| File | Content |
|---|---|
| `/etc/<distribution>/config.yaml` | The configuration from `otelcol_config`, mode `0640`, group of the service user |
| `/etc/<distribution>/<distribution>.conf` | Options of the service (`--config=/etc/<distribution>/config.yaml`), from the package, not changed |
| `/lib/systemd/system/<distribution>.service` | Unit of the collector, from the package |

### Distribution

`otelcol_distribution` selects the distribution, `otelcol` (default, core components) or `otelcol-contrib` (core and contrib components).
The service has the name of the distribution, it runs as the user `otel` (`otelcol`) or `otelcol-contrib`, created by the package.

The other distribution is removed with its configuration (`apt purge`), both use the same ports with the default configuration.
The distributions `otelcol-prometheus` and `otelcol-otlp` are not supported, their packages come without configuration
and their builds lack the components of the default configuration.

### Version

`otelcol_version` is `latest` (default) or a release, e.g. `0.164.0` or `v0.164.0`, like the tag of a container image.

- `latest` is the newest release of the collector (tag `v<version>`) with a package of the distribution for the architecture of the host.
  The role reads the releases from the GitHub API, without a token the API allows 60 requests per hour and address.
  The repository releases other tools too (`cmd/builder/...`), they are skipped, and so are releases without packages.
- A release is installed only if the installed version of the distribution differs, an older release is installed as a downgrade.
- The host downloads the package from GitHub, the role checks it against the checksum of the release (`<package>.sha256`) before it installs it.
  The package is downloaded into a temporary directory that is removed afterwards.
- The package names the architecture differently from dpkg: `i386` is `386`, `armhf` is `armv7`, `ppc64el` is `ppc64le`.

The package enables and restarts the collector on its installation and keeps a changed `config.yaml` on an update.

### Configuration

`otelcol_config` is a mapping of the configuration of the collector, it replaces the configuration completely.
The default is `/etc/otelcol/config.yaml` of the package (the same in both distributions):
OTLP, Jaeger, Zipkin and its own metrics are received on all addresses and written to the log with the `debug` exporter.

```yaml
otelcol_config:
  receivers:
    otlp:
      protocols:
        grpc:
          endpoint: '127.0.0.1:4317'
        http:
          endpoint: '127.0.0.1:4318'
  exporters:
    otlphttp:
      endpoint: 'https://otlp.example.org'
  service:
    pipelines:
      metrics:
        receivers: [ 'otlp' ]
        exporters: [ 'otlphttp' ]
```

The role checks the configuration with `<distribution> validate` before it replaces `config.yaml`,
an invalid configuration lets the role fail and the running collector keeps its configuration.
The collector restarts when the configuration changed.
Secrets can be read from the environment with `${env:NAME}`, the environment is set in `/etc/<distribution>/<distribution>.conf`.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The base VM is cloned for every platform and the clones are deleted afterwards, the playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root.
The VMs need access to GitHub.

| Platform | Role in the test |
|---|---|
| `molecule-otelcol` | Defaults: the latest release of `otelcol` with the default configuration |
| `molecule-otelcol-contrib` | `otelcol-contrib` 0.163.2 with an own configuration, `prepare` installs `otelcol` that has to be removed |

`side_effect` updates `otelcol-contrib` to 0.164.0, the configuration has to stay.
Afterwards it runs the role with an unknown distribution, a version without patch level, a configuration that is no mapping
and a configuration with an unknown receiver and checks that the role fails with the expected message and `config.yaml` is unchanged
(tasks marked `expect ERROR`).
`verify` checks the installed packages and versions, the service, the configuration and the OTLP port.

```shell
cd monitoring_opentelemetry_collector
MOLECULE_TART_IMAGE='debian' molecule test
```
