The role installs the systemd units `pki-update@.service` and `pki-update@.timer` and enables the timer `pki-update@<pki_service>.timer`.
The timer runs every four hours by default and restarts the service if one of its certificates is newer than the start of the service,
so every renewal causes exactly one restart.
`pki_certificate` is the path of a certificate or a list of paths, e.g. for a service with the certificates of several realms.

Services that read their certificate only at the start, e.g. OpenSMTPD copying it with `ExecStartPre`, use the renewed certificate without a run of their role.
The modification time of the certificate is used, links are followed (e.g. `live` of certbot pointing to `archive`),
`pki_easyrsa_deploy` and certbot write a new file on every renewal.

### Behavior

`pki-update@<service>.service` is a oneshot unit, `ExecCondition` decides about the restart:

- the service is not active: nothing happens
- a certificate does not exist: the unit fails and is listed by `systemctl --failed`, also if another certificate was renewed
- a certificate is newer than `ActiveEnterTimestamp` of the service: `systemctl restart <service>.service`

The service and the certificates (`PKI_CERTIFICATES`, separated by spaces) are set in `pki-update@<service>.service.d/override.conf`,
the schedule in `pki-update@<service>.timer.d/override.conf` (`OnCalendar` of systemd).

### Example

Roles include the role for their service, e.g. `mail_opensmtpd`:

```yaml
- name: 'Restart OpenSMTPD after a renewal of the certificate'
  ansible.builtin.include_role:
    name: 'pki_update'
  vars:
    pki_service: 'opensmtpd'
    pki_certificate: '/opt/certbot/etc/live/mx.example.org/fullchain.pem'
    pki_schedule: '*-*-* 00/4:00:00'
```

A service with several certificates, e.g. Traefik with the certificates of two realms:

```yaml
- name: 'Restart Traefik after a renewal of a certificate'
  ansible.builtin.include_role:
    name: 'pki_update'
  vars:
    pki_service: 'traefik'
    pki_certificate:
      - '/etc/pki/realms/example.org/fullchain.pem'
      - '/etc/pki/realms/example.net/fullchain.pem'
```

### Validation

The role checks before any change:

- `pki_service` is the name of a service without `.service` of letters, digits, `_`, `.` and `-`
- `pki_certificate` is an absolute path or a non-empty list of unique absolute paths of letters, digits, `_`, `.`, `@`, `+`, `/` and `-`,
  they are written separated by spaces to `Environment=`
- `pki_schedule` is a string without line breaks

The certificates do not need to exist when the role runs, the check of the timer reports a missing certificate.

### Check mode

The role needs no packages, in check mode it reports the units and overrides it would write, the timer is not started.

### Migration

The role is new, there are no former variables.

Changed behavior:

- `pki_certificate` takes a list of certificates, the override of the service sets `PKI_CERTIFICATES` instead of `PKI_CERTIFICATE`,
  `pki-update@.service` and the overrides change once, the services are not restarted

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs with Debian 13 on a macOS controller.
`prepare` creates the service `molecule-pki` (`sleep infinity`) and its certificate.
`check` runs `converge` with `--check` on the VMs where the role never ran.

| Platform | Test case |
|---|---|
| `molecule-pki-update-default` | The mandatory values only, the certificate is a file |
| `molecule-pki-update` | Two certificates, the first is a link of certbot to the archive, an own schedule |

`side_effect` runs the role with an invalid name of the service, a relative path of the certificate and in the list, an empty list,
a duplicate certificate and a line break in the schedule
and checks that it fails with the expected message and the overrides are unchanged (tasks marked `expect ERROR`).
On `molecule-pki-update` it changes the schedule, the timer has to restart.
`verify` checks the overrides and the timer, runs the check with certificates older than the start of the service (no restart),
with a renewed last certificate (one restart, a second check does not restart again) and with a missing first certificate (the unit fails).

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd pki_update
MOLECULE_TART_IMAGE='debian' molecule test
```
