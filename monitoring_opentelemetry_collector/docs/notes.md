The role installs the [OpenTelemetry Collector](https://opentelemetry.io/docs/collector/) on Debian from the packages of the
[releases](https://github.com/open-telemetry/opentelemetry-collector-releases/releases) and writes its configuration.

| File | Content |
|---|---|
| `/etc/<distribution>/config.yaml` | The configuration from `otelcol_config`, mode `0640`, group of the service user |
| `/etc/<distribution>/secrets/<name>` | The secrets of `otelcol_secrets`, mode `0640`, group of the service user, the directory `0750` |
| `/etc/<distribution>/<distribution>.conf` | Options of the service (`--config=/etc/<distribution>/config.yaml`), from the package, not changed |
| `/lib/systemd/system/<distribution>.service` | Unit of the collector, from the package |

### Distribution

`otelcol_distribution` selects the distribution, `otelcol` (default, core components) or `otelcol-contrib` (core and contrib components).
The service has the name of the distribution, it runs as the user `otel` (`otelcol`) or `otelcol-contrib`, created by the package.

The other distribution is removed with its configuration (`apt purge`), both use the same ports with the default configuration.
The distributions `otelcol-prometheus` and `otelcol-otlp` are not supported, their packages come without configuration
and their builds lack the components of the default configuration.

### Version

`otelcol_version` is `latest` (default) or a release, e.g. `0.165.0` or `v0.165.0`, like the tag of a container image.

- `latest` is the newest release of the collector (tag `v<version>`) with a package of the distribution for the architecture of the host.
  The role reads the releases from the GitHub API, without a token the API allows 60 requests per hour and address.
  The repository releases other tools too (`cmd/builder/...`), they are skipped, and so are releases without packages.
- A release is installed only if the installed version of the distribution differs, an older release is installed as a downgrade.
- The host downloads the package from GitHub, the role checks it against the checksum of the release (`<package>.sha256`) before it installs it.
  The package is downloaded into a temporary directory that is removed afterwards.
- The package names the architecture differently from dpkg: `i386` is `386`, `armhf` is `armv7`, `ppc64el` is `ppc64le`.

The package enables and restarts the collector on its installation and keeps a changed `config.yaml` on an update.

### Configuration

`otelcol_config` is merged over the default of the role, every key of the first level replaces the key of the default completely,
`null` removes a key. The default is `/etc/otelcol/config.yaml` of the package 0.165.0 (the same in both distributions):
OTLP, Jaeger, Zipkin and its own metrics are received on all addresses and written to the log with the `debug` exporter.
A configuration with own `receivers`, `exporters` and `service` keeps the `extensions` and `processors` of the default,
the collector starts only the components used in `service`.

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
The collector restarts when the configuration or a secret changed.

### Secrets

The configuration of the collector reads files with `${file:<path>}`, so the secrets are files referenced in the configuration.
`otelcol_secrets` is a list of entries with `name`, `data` and `target`, the target is the path of the option in `otelcol_config`,
the keys separated by dots, e.g. `exporters.otlphttp/backend.headers.authorization`. The role writes the secret to
`/etc/<distribution>/secrets/<name>` (owner root, group of the service user, mode `0640`) and the reference `${file:/etc/<distribution>/secrets/<name>}`
to the option in `config.yaml`, `config.yaml` never contains the secret. Files of secrets that are not part of `otelcol_secrets` anymore are removed.

```yaml
otelcol_secrets:
  - name: 'otelcol_backend_authorization'
    data: "Bearer {{ vault_otelcol_backend_token }}"
    target: 'exporters.otlphttp.headers.authorization'
```

The collector reads the content of the file as YAML, the role writes the secret as JSON string, so a secret like `1234` or `true` stays a string.
The dictionaries on the path of a target may be missing in `otelcol_config`, the role creates them, a list or a value on the path is rejected.
The fields `password`, `client_secret`, `bearer_token`, `api_key`, `token` and `authorization` must not be set in `otelcol_config`,
except to a reference of the environment (`${env:NAME}`), the environment is set in `/etc/<distribution>/<distribution>.conf`.

### Allowed keys

The role only allows the keys `receivers`, `exporters`, `processors`, `connectors`, `extensions` and `service` on the first level of `otelcol_config`,
generated from `Config` in `otelcol/config.go` of the OpenTelemetry Collector v0.165.0, the collector checks the keys below with `validate`.
This prevents unexpected behavior by accident, e.g. by a typo or a password that has to be passed as secret.

### Validation

The role checks before any change:

- `otelcol_distribution` is `otelcol` or `otelcol-contrib`, `otelcol_version` is `latest` or a release with patch level
- `otelcol_config` contains only the allowed keys and no field carrying secrets with a value
- `otelcol_secrets` is a list of entries with `name`, `data` and `target` with unique names matching `^[A-Za-z0-9_][A-Za-z0-9_.-]*$`,
  every target is a path below an allowed key, set once, not set in `otelcol_config` and leads through dictionaries only,
  the data are strings without line breaks

If `otelcol_config` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.
The collector checks the configuration with `validate` before `config.yaml` is replaced, after the installation of the package.

### Check mode

The role runs with `--check`, also on a host where it never ran: it reads the releases, downloads the package and checks its checksum,
and reports the removed and installed packages, the secrets and `config.yaml`. `validate` does not run in check mode.
Without the package the unit of the collector is missing, starting and restarting the collector is skipped in check mode then.

### Migration

- `otelcol_config` replaced the default completely, it is merged over the default now: keys of the default that are not part of `otelcol_config`
  stay, set them to `null` to remove them.
- `otelcol_secrets` is new, secrets passed with `${env:NAME}` keep working.
- Unknown keys on the first level of `otelcol_config` and fields carrying secrets with a value are rejected.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The base VM is cloned for every platform and the clones are deleted afterwards, the playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root.
The VMs need access to GitHub.

| Platform | Role in the test |
|---|---|
| `molecule-otelcol` | Defaults: the latest release of `otelcol` with the default configuration |
| `molecule-otelcol-contrib` | `otelcol-contrib` 0.164.0 with an own configuration and a secret, `prepare` installs `otelcol` that has to be removed |

`check` runs `converge` with `--check` on the new VMs.
`side_effect` updates `otelcol-contrib` to 0.165.0, the configuration has to stay.
Afterwards it runs the role with an unknown distribution, a version without patch level, a configuration that is no dictionary,
an unknown key, a secret in the configuration, a secret without target, an unknown secret, a target set in the configuration,
a secret in a list and a configuration with an unknown receiver and checks that the role fails with the expected message and `config.yaml` is unchanged
(tasks marked `expect ERROR`). `molecule-otelcol` runs the role again without a change, the collector must not restart.
`verify` checks the installed packages and versions, the service without automatic restarts, the configuration with the reference of the secret,
the file of the secret and the OTLP port.

```shell
cd monitoring_opentelemetry_collector
MOLECULE_TART_IMAGE='debian' molecule test
```
