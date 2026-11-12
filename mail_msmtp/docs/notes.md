The role runs [msmtpd](https://marlam.de/msmtp/msmtpd.html), the SMTP relay of msmtp, in the container image [ghcr.io/crazy-max/msmtpd](https://github.com/crazy-max/docker-msmtpd).
msmtpd accepts mails on port `2500` of the container and relays them to a smarthost.
The container runs as unprivileged user and has no state, so the role needs no home directory.

msmtp as sendmail replacement on the host is configured by the role `bootstrap_debian` with `debian_mail_enable`, it can use this container as relay.

`msmtp_version` sets the tag of the image, `latest` by default.

### Environment and secrets

All variables are set with `msmtp_environment`, which is merged over the defaults of the role, see the [environment variables of the image](https://github.com/crazy-max/docker-msmtpd#environment-variables).
Variables carrying secrets are passed as podman secrets with `msmtp_secrets` and must not be set in `msmtp_environment`.
Every secret has a `name`, the `data` and the `target`, the usual name of the variable, e.g. `SMTP_PASSWORD`.
The role creates the secret with `podman secret create`, mounts it to `/run/secrets/<name>` and sets the file variable of the image,
so the password is neither part of the quadlet unit nor of the environment of the container:

| `target` | File variable set by the role |
|---|---|
| `SMTP_PASSWORD` | `SMTP_PASSWORD_FILE` |
| `SMTP_USER` | `SMTP_USER_FILE` |

`SMTP_USER` and `SMTP_PASSWORD` are only allowed as secrets.

The role requires the following variables and checks them before it changes anything:

| Variable | Set with | Default of the role |
|---|---|---|
| `SMTP_HOST` | `msmtp_environment` | – |
| `SMTP_USER` | `msmtp_secrets` | –, only required if `SMTP_AUTH` is set and not `off` |
| `SMTP_PASSWORD` | `msmtp_secrets` | –, only required if `SMTP_AUTH` is set and not `off` |

The role sets `TZ` to `msmtp_timezone`.
Quote values like `'on'` and `'off'`, unquoted they are booleans in YAML and passed as `True` and `False` to the container.

With `SMTP_AUTH: 'on'` msmtp chooses the authentication method itself and never chooses a method sending the password in plain text (`plain`, `login`) without TLS.
Use TLS to the smarthost or set the method explicitly, e.g. `SMTP_AUTH: 'plain'`, if the smarthost is reached without TLS in a trusted network.

```yaml
msmtp_ip: '192.168.99.25'
msmtp_network: 'podman99'
msmtp_hostname: 'msmtpd.example.org'
msmtp_timezone: 'Europe/Berlin'
msmtp_environment:
  SMTP_HOST: 'smtp.example.org'
  SMTP_PORT: '587'
  SMTP_TLS: 'on'
  SMTP_STARTTLS: 'on'
  SMTP_AUTH: 'on'
  SMTP_FROM: 'relay@example.org'
  SMTP_DOMAIN: 'example.org'
msmtp_secrets:
  - name: 'msmtpd_smtp_user'
    data: "{{ vault_msmtpd_smtp_user }}"
    target: 'SMTP_USER'
  - name: 'msmtpd_smtp_password'
    data: "{{ vault_msmtpd_smtp_password }}"
    target: 'SMTP_PASSWORD'
```

msmtpd does not authenticate its clients, every host that reaches the container can relay mails through it.
Keep the container in a network that only trusted hosts can reach and do not publish the port to untrusted networks.

### Allowed variables

The role only allows the environment variables in `mail_msmtp__environment_allowed` and the secrets with the targets above,
it stops before any change if unknown variables or secrets are set.
This prevents unexpected behavior by accident, e.g. by a typo or a variable that has to be passed as secret.
The check uses the environment and the secrets of the container after merging `msmtp_container`,
so variables set with `msmtp_container.environment` are checked as well.
The allowed variables are the variables of the image (README and `rootfs/etc/cont-init.d` of crazy-max/docker-msmtpd) without `SMTP_USER` and `SMTP_PASSWORD`,
and the file variables `SMTP_USER_FILE` and `SMTP_PASSWORD_FILE`. The role sets them from `msmtp_secrets`, they must not be set in `msmtp_environment`.

### Validation

The role checks before any change that `msmtp_secrets` is a list of entries with `name`, `data` and `target` and unique names,
that the required variables and secrets are set, that neither a secret nor its file variable is set in `msmtp_environment`
and that only allowed variables and secrets are used.
If `msmtp_container` is no dictionary, merging it with the default fails before anything changes.

### Changes and restarts

A running container is restarted when a secret or the quadlet unit changed, e.g. after changing `msmtp_environment`.
The first start of the container does not trigger an additional restart.

### Migration

Former versions of the role installed the Debian packages `msmtp`, `msmtp-mta`, `bsd-mailx` and `gsasl-common`, wrote `/etc/msmtprc` and enabled the service `msmtpd` on the host.
The role is now split:

- msmtp on the host is configured by `bootstrap_debian`, which also stops and disables the service `msmtpd` of the package `msmtp-mta` on the host:

| Former variable | Now |
|---|---|
| `msmtp_accounts` | `debian_mail_accounts`, same keys |
| `msmtp_aliases` | `debian_mail_aliases`, now a mapping of names to addresses that is written to `/etc/aliases` |
| `msmtp_auto_from` | `debian_mail_auto_from` |
| `msmtp_maildomain` | `debian_mail_maildomain`, default `debian_hostname` instead of `mail_domain` |
| `msmtp_syslog` | `debian_mail_syslog` |
| `vault__msmtp_password` | removed, it was never used |

- msmtpd runs as container with this role and requires `msmtp_ip`, `msmtp_network`, `msmtp_hostname`, `msmtp_timezone` and `SMTP_HOST`.
  The role does not depend on `mail_common` anymore.

Later changes of the container role:

- The secrets are mounted as files and read with `SMTP_PASSWORD_FILE` and `SMTP_USER_FILE`, before they were passed as environment variables.
  `msmtp_secrets` stays the same.
- `SMTP_USER` in `msmtp_environment` is a secret with target `SMTP_USER` now.
- `msmtp_publish` is removed, set the ports with `msmtp_container.publish`.
- `msmtp_autoupdate_schedule` sets the schedule of `container_update`.

### Tests

The molecule scenario `default` runs the role in a [tart](https://tart.run) VM `molecule-msmtpd` on a macOS controller, the base VM has to be Debian 13.
The base VM is cloned and the clone is deleted afterwards, the base VM itself is never changed.
The playbooks creating and destroying the VMs are shared by all tart scenarios and live in `.molecule/tart/` in the repository root.

`prepare` sets up podman and the network `podman-molecule` with the role `container_podman`, pulls the images
and starts [mailpit](https://mailpit.axllent.org) as smarthost, accepting any authentication.
`converge` runs msmtpd with authentication (`SMTP_AUTH: 'plain'`, mailpit is reached without TLS) against mailpit and the password as secret.
`side_effect` runs the role with `msmtp_container` not a dictionary, a secret without target, without the secrets of the authentication,
the user, the password and its file variable in the environment, an unknown environment variable in `msmtp_environment` and in `msmtp_container.environment` and an unknown secret
and checks that it fails with the expected message and the quadlet unit is unchanged (tasks marked `expect ERROR`),
then it changes `SMTP_DOMAIN` and checks that the running service is restarted.
`verify` checks the quadlet unit with the mounted secrets, `SMTP_USER_FILE` and `SMTP_PASSWORD_FILE` without the password, the podman secrets and the service,
checks that the image wrote the user and the password of the secret files to `/etc/msmtprc`,
sends a mail to msmtpd and checks with the API of mailpit that it was relayed.
The VM needs access to the GitHub container registry and Docker Hub.

Requirements on the controller: `tart`, `sshpass` (`brew install hudochenkov/sshpass/sshpass`), `molecule` and the collection `containers.podman`.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd mail_msmtp
MOLECULE_TART_IMAGE='debian' molecule test
```
