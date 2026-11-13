step-ca, the certificate authority of smallstep, runs in the container image [smallstep/step-ca](https://hub.docker.com/r/smallstep/step-ca)
(`latest` by default, `stepca_version` sets the tag) as podman quadlet. It listens with TLS on port 9000 and serves the API of the CA, ACME and the health check `/health`.
The image runs step-ca as `step` (1000), all data of the CA (certificates, keys, the database and `config/ca.json`) is kept in `<stepca_home>`, mounted as `/home/step`.

### Initialization

The image initializes the CA with `step ca init` if `config/ca.json` is missing: it creates the root and the intermediate certificate,
the provisioner of the administrator and `ca.json`, writes the password of the CA to `secrets/password` and shows the password of the administrator once.
step-ca only needs `secrets/password` afterwards, so the initialization runs exactly once in its own container `stepca-init`:

- the role checks `<stepca_home>/config/ca.json`, the same file the entrypoint checks, and skips the initialization if it exists
- `stepca-init` uses the image and the volume of the quadlet unit, the variables of `stepca_init_environment` and the secrets as files, without network
- the role waits for the end of the initialization in the log and removes `stepca-init` afterwards, also if the initialization failed
- if the initialization fails, the content of `<stepca_home>` has to be removed before the next run

The quadlet unit contains neither the variables nor the secrets of the initialization.
Changing `stepca_init_environment` or the secrets after the initialization has no effect, the CA is changed with `stepca_config` or the step CLI.

`stepca_init_environment` contains the variables `DOCKER_STEPCA_INIT_*` of the entrypoint, `DOCKER_STEPCA_INIT_NAME` and `DOCKER_STEPCA_INIT_DNS_NAMES` are mandatory,
the DNS names may be a list. The default enables the remote management, SSH and ACME and sets the provisioner `admin` and the administrator `step`.
The role sets `DOCKER_STEPCA_INIT_ADDRESS` to `:9000`, another port is published with `stepca_container.publish`.
Booleans may be given as YAML booleans, the role passes them as `true` or `false`.

```yaml
stepca_init_environment:
  DOCKER_STEPCA_INIT_NAME: 'Example CA'
  DOCKER_STEPCA_INIT_DNS_NAMES: [ 'ca.example.org', 'localhost' ]
  DOCKER_STEPCA_INIT_SSH: false
```

### Configuration

`stepca_config` is merged recursively into the `ca.json` created by the initialization, lists are replaced.
The role writes `ca.json` with the mode `0600` and restarts step-ca if it changed.
Allowed are the keys `federatedRoots`, `insecureAddress`, `dnsNames`, `logger`, `db`, `monitoring`, `authority`, `tls`, `templates`, `commonName`, `crl` and `metricsAddress`,
in `authority` the keys `template`, `claims`, `policy`, `disableIssuedAtCheck`, `backdate`, `enableAdmin` and `disableGetSSHHosts`.
The keys and certificates (`root`, `crt`, `key`, `ssh`, `kms`, `password`), the address and the provisioners are created by the initialization,
the provisioners and the administrators are managed with the step CLI or the remote management.
step-ca ignores unknown keys of `ca.json`, so the role rejects all keys that are not allowed.
The keys are described in the [configuration of step-ca](https://smallstep.com/docs/step-ca/configuration/).

```yaml
stepca_config:
  logger:
    format: 'json'
  authority:
    claims:
      defaultTLSCertDuration: '24h'
      maxTLSCertDuration: '168h'
```

### Secrets

`stepca_secrets` is a list of podman secrets with `name`, `data` and `target`, the usual name of the variable.
All secrets are only needed by the initialization, they are mounted as `/run/secrets/<name>` in `stepca-init` only and the role sets their file variables:

| Target | File variable | Content |
|---|---|---|
| `DOCKER_STEPCA_INIT_PASSWORD` | `DOCKER_STEPCA_INIT_PASSWORD_FILE` | The password of the CA and of the provisioner of the administrator, mandatory |
| `DOCKER_STEPCA_INIT_ROOT` | `DOCKER_STEPCA_INIT_ROOT_FILE` | An existing root certificate |
| `DOCKER_STEPCA_INIT_KEY` | `DOCKER_STEPCA_INIT_KEY_FILE` | The key of the existing root |
| `DOCKER_STEPCA_INIT_KEY_PASSWORD` | `DOCKER_STEPCA_INIT_KEY_PASSWORD_FILE` | The password of the key of the existing root |

Neither a target nor a file variable may be set in `stepca_environment` or `stepca_init_environment`.

```yaml
stepca_secrets:
  - name: 'stepca_init_password'
    data: "{{ vault_stepca_password }}"
    target: 'DOCKER_STEPCA_INIT_PASSWORD'
```

### Allowed variables

step-ca reads no environment variables, the role only allows `TZ` in `stepca_environment`.
`stepca_init_environment` only allows the variables of the entrypoint without the secrets, `pki_stepca__init_environment_allowed`.
This prevents unexpected behavior by accident, e.g. by a typo or a variable that has to be passed as secret.
The lists are taken from `docker/Dockerfile` and `docker/entrypoint.sh` of step-ca v0.30.2.

### Container

Ports, volumes, additional hosts (`etc_hosts`) and dependencies (`requires`) are changed with `stepca_container`, it is merged over the default of the container.
The merge is not recursive. For a reverse proxy, e.g. Traefik with TLS passthrough, the labels are set with `stepca_labels`.
The directory belongs to `step` (1000) with the mode `0750`.

### Validation

The role checks before any change:

- `stepca_secrets` is a list of entries with `name`, `data` and `target` and unique names
- `DOCKER_STEPCA_INIT_NAME`, `DOCKER_STEPCA_INIT_DNS_NAMES` and the secret `DOCKER_STEPCA_INIT_PASSWORD` are set
- no secret, no file variable of a secret and no variable set by the role is set in the environments
- values contain no line breaks, booleans are `true` or `false`
- `stepca_config` is a dictionary of the allowed keys, `dnsNames` is a list with at least one name
- only allowed variables and secrets are set

If `stepca_container` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Restart and updates

step-ca is restarted if it was running and `ca.json` or the quadlet unit changed, otherwise it is started and enabled.
If the start fails, the role shows the journal of the service.
Afterwards the role waits up to 120 seconds until `/health` reports `ok` and shows the journal if step-ca does not answer.
The root of the CA is self-signed, the health check does not validate the certificate.
Updates of the image are done by `container_update` with `stepca_autoupdate_enabled: true` and `stepca_autoupdate_schedule`,
without `stepca_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

| Former variable | Replacement |
|---|---|
| `stepca_init_name` | `stepca_init_environment.DOCKER_STEPCA_INIT_NAME` |
| `stepca_init_dns_name` | `stepca_init_environment.DOCKER_STEPCA_INIT_DNS_NAMES`, a list or a string |
| `stepca_init_remote_management` | `stepca_init_environment.DOCKER_STEPCA_INIT_REMOTE_MANAGEMENT` |
| `stepca_init_provisioner_name` | `stepca_init_environment.DOCKER_STEPCA_INIT_PROVISIONER_NAME` |
| `stepca_init_admin_subject` | `stepca_init_environment.DOCKER_STEPCA_INIT_ADMIN_SUBJECT` |
| `stepca_init_ssh` | `stepca_init_environment.DOCKER_STEPCA_INIT_SSH` |
| `stepca_init_acme` | `stepca_init_environment.DOCKER_STEPCA_INIT_ACME` |
| `stepca_init_address` | Removed, the role sets `:9000`, the port is published with `stepca_container.publish` |
| `stepca_init_password` | An entry of `stepca_secrets` with the target `DOCKER_STEPCA_INIT_PASSWORD` |
| `stepca_publish` | `stepca_container.publish` |
| `podman___update_mode` | Removed, updates are done by `container_update` with `stepca_autoupdate_enabled` |

Changed behavior:

- the initialization runs once in `stepca-init`, the quadlet unit has no variables and no secret of the initialization anymore,
  on existing installations the quadlet unit changes once and step-ca restarts
- the secret is mounted as file with `DOCKER_STEPCA_INIT_PASSWORD_FILE` instead of the environment, the former podman secret `stepca_init_password` may be reused as name
- `/etc/localtime` and `/etc/timezone` are no longer mounted, the time zone is set with `stepca_timezone`
- the handler `Restart step-ca container` is removed
- `stepca_config` changes `ca.json`, the role validates all variables before any change

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root. The VMs need access to Docker Hub.

| Platform | Test case |
|---|---|
| `molecule-stepca-default` | Only the mandatory variables, remote management, SSH and ACME by default |
| `molecule-stepca` | IPv6, labels, without SSH, standalone, the format of the logger and the durations of the certificates in `stepca_config` |

`prepare` creates the podman network, installs `curl` and pulls the image.
`side_effect` runs the role with `stepca_container` not a dictionary, a secret without `target`, without the password, without the name of the CA,
the password in the environment of the initialization, the address of the initialization, an invalid boolean, a line break in a value,
an unknown variable of the initialization, an unknown variable, an unknown secret, `stepca_config` not a dictionary, the root and the provisioners in `stepca_config`
and checks that it fails with the expected message and the quadlet unit and `ca.json` are unchanged (tasks marked `expect ERROR`),
then it raises the maximum duration of the certificates on `molecule-stepca`, `ca.json` changes, step-ca has to restart and the root stays the same,
the initialization does not run again.
`verify` checks the quadlet unit without the variables and secrets of the initialization, the service, the addresses, the environment,
that `stepca-init` does not exist, the files and the values of `stepca_config` in `ca.json`, the health check and the directory of ACME
and issues certificates with the provisioner `admin`: with the password, not with a wrong one, with an allowed duration and not with a longer one than the maximum.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd pki_stepca
MOLECULE_TART_IMAGE='debian' molecule test
```
