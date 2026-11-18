The role installs the systemd units `pki-update@.service` and `pki-update@.timer` and enables the timer `pki-update@<pki_service>.timer`.
The timer runs every four hours by default and restarts the service if its certificate is newer than the start of the service,
so every renewal causes exactly one restart.

Services that read their certificate only at the start, e.g. OpenSMTPD copying it with `ExecStartPre`, use the renewed certificate without a run of their role.
The modification time of the certificate is used, links are followed (e.g. `live` of certbot pointing to `archive`),
`pki_easyrsa_deploy` and certbot write a new file on every renewal.

### Behavior

`pki-update@<service>.service` is a oneshot unit, `ExecCondition` decides about the restart:

- the service is not active: nothing happens
- the certificate does not exist: the unit fails and is listed by `systemctl --failed`
- the certificate is newer than `ActiveEnterTimestamp` of the service: `systemctl restart <service>.service`

The service and the certificate are set in `pki-update@<service>.service.d/override.conf`,
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

### Validation

The role checks before any change:

- `pki_service` is the name of a service without `.service` of letters, digits, `_`, `.` and `-`
- `pki_certificate` is an absolute path of letters, digits, `_`, `.`, `@`, `+`, `/` and `-`, it is written unquoted to `Environment=`
- `pki_schedule` is a string without line breaks

The certificate does not need to exist when the role runs, the check of the timer reports a missing certificate.

### Check mode

The role needs no packages, in check mode it reports the units and overrides it would write, the timer is not started.

### Migration

The role is new, there are no former variables.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs with Debian 13 on a macOS controller.
`prepare` creates the service `molecule-pki` (`sleep infinity`) and its certificate.
`check` runs `converge` with `--check` on the VMs where the role never ran.

| Platform | Test case |
|---|---|
| `molecule-pki-update-default` | The mandatory values only, the certificate is a file |
| `molecule-pki-update` | The certificate is a link of certbot to the archive, an own schedule |

`side_effect` runs the role with an invalid name of the service, a relative path of the certificate and a line break in the schedule
and checks that it fails with the expected message and the overrides are unchanged (tasks marked `expect ERROR`).
On `molecule-pki-update` it changes the schedule, the timer has to restart.
`verify` checks the overrides and the timer, runs the check with a certificate older than the start of the service (no restart),
with a renewed certificate (one restart, a second check does not restart again) and with a missing certificate (the unit fails).

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd pki_update
MOLECULE_TART_IMAGE='debian' molecule test
```
