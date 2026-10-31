The role installs the systemd units `container-update@.service` and `container-update@.timer` and enables the timer `container-update@<container_name>.timer` for one container.
It is usually included by the container roles, e.g. with `traefik_autoupdate_enabled: true`, but can also be used directly:

```yaml
- name: 'Enable autoupdate on container'
  ansible.builtin.include_role:
    name: 'container_update'
  vars:
    container_name: 'traefik'
    container_image: 'docker.io/traefik:v3'
    container_schedule: '*-*-* 03:30:00'
```

| Variable | Default | Description |
|---|---|---|
| `container_name` | – | Name of the systemd unit of the container, without the timer only the templates are installed |
| `container_image` | – | Image of the container, required |
| `container_schedule` | `*-*-* 00/4:00:00` | `OnCalendar` of the timer, replaces the default schedule |
| `container_pushover_key`, `container_pushover_token` | – | Pushover user key and app token for notifications |

### How the update works

The timer starts `container-update@<container_name>.service` with a random delay of up to 30 minutes.
The service compares the digest of the local image with the remote one and only pulls the image and restarts the container if they differ:

- for multi-arch images the digest of the manifest for the host architecture in the index is used,
- for single-arch images the digest of the manifest itself.

If the image does not exist locally, it is pulled.

### Notifications

With `container_pushover_key` and `container_pushover_token` the role writes `/etc/systemd/container-update.env` (mode `0600`) and the unit `container-update-notify-failure@.service`.
Successful updates and failures are sent to Pushover.
Without the credentials both files are removed again.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The base VM is cloned for every platform and the clones are deleted afterwards, the base VM itself is never changed.
The playbooks creating and destroying the VMs are shared by all tart scenarios and live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-container-update` | Default schedule, without Pushover |
| `molecule-container-update-pushover` | Own schedule, with Pushover (test credentials, never used) |

`prepare` installs podman with the role `container_podman` and starts the test container `molupd` (`docker.io/library/alpine:3`) as quadlet.
`verify` checks the unit files and their modes, the environment file, the schedule of the timer (exactly one `OnCalendar`), the environment and `OnFailure` of the service,
and runs the update once: the image is up to date, so the container must not be restarted.
The VMs need access to Docker Hub.

Requirements on the controller: `tart`, `sshpass` (`brew install hudochenkov/sshpass/sshpass`), `molecule` and the collection `containers.podman`.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd container_update
MOLECULE_TART_IMAGE='debian' molecule test
```
