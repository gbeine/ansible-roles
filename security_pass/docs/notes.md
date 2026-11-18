pass runs in the container image `c0d3cr.io/container/pass` as podman quadlet.
The image is based on the [linuxserver.io](https://www.linuxserver.io) Alpine base image and contains `pass`, `gpg-agent` and `git`.
The password store is in `<pass_home>/.password-store`, the GnuPG home in `<pass_home>/.gnupg`, both are mounted as `/config`.
The container has no network, it is used with `podman exec`, e.g.:

```shell
podman exec -it -u abc pass pass show example.org
```

### Configuration

pass and the gpg-agent have no configuration file in the image, the image is configured with the environment.
The files in `/config` belong to `PUID` and `PGID` (default `911`), the base image changes the owner at the start.
`pass_environment` is merged over the default, e.g. for another user and the cache durations of the gpg-agent in seconds:

```yaml
pass_environment:
  PUID: '1000'
  PGID: '1000'
  GNUPAGENT_DEFAULT_CACHE_TTL: '900'       # default of the image
  GNUPAGENT_MAX_CACHE_TTL: '7776000'       # default of the image
  GNUPAGENT_DEFAULT_CACHE_TTL_SSH: '1800'  # default of the image
  GNUPAGENT_MAX_CACHE_TTL_SSH: '7776000'   # default of the image
```

### Secrets

pass has no secrets in the container, the password store is encrypted with GnuPG.

### Allowed variables

`pass_environment` and `pass_container.environment` only take the variables of `security_pass__environment_allowed`:
`PUID`, `PGID`, `TZ` and `UMASK` of the base image and the four `GNUPAGENT_*` variables the image passes to the gpg-agent.
`PASSWORD_STORE_DIR` and `GNUPGHOME` are not allowed, they point to the volume `/config`.
The lists prevent unexpected behavior by accident, e.g. a typo that the image would ignore.

### Container

Volumes, additional hosts (`etc_hosts`) and the dependencies of the quadlet unit (`requires`, `wants`, `after`, `part_of`, `binds_to`,
`requires_mounts_for`) are changed with `pass_container`, it is merged over the default of the container, the merge is not recursive:

```yaml
pass_container:
  requires_mounts_for:
    - '/opt'
```

### Validation

The role checks before any change:

- `pass_environment` and `pass_container` are dictionaries, merging them with the default fails otherwise
- the former variables `pass_uid` and `pass_gid` are not set
- the values of `pass_environment` contain no line breaks
- `pass_autoupdate_enabled` is a boolean
- only allowed variables are set in the environment of the container

### Check mode

The role runs with `--check`, also on a host where it never ran, and compares the quadlet unit. The start of pass does not run in check mode.

### Restart and updates

pass is restarted if it was running and the quadlet unit changed, e.g. by a changed environment variable, otherwise it is started and enabled.
Updates of the image are done by `container_update` with `pass_autoupdate_enabled: true` and optionally `pass_autoupdate_schedule`,
without `pass_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

| Before | Now |
|---|---|
| `pass_uid` | `pass_environment.PUID` |
| `pass_gid` | `pass_environment.PGID` |
| `podman___update_mode` | `pass_autoupdate_enabled` |

Changed behavior:

- the role rejects `pass_uid`, `pass_gid` and variables of the environment that are not allowed,
- the tags are `security` and `security_pass`.

### Tests

The molecule scenario `default` uses tart with two VMs with Debian 13, the VMs need access to `c0d3cr.io`.

| Platform | Test case |
|---|---|
| `molecule-pass-default` | The mandatory values only, the cache durations of the image |
| `molecule-pass` | `PUID` and `PGID` `1000`, `GNUPAGENT_MAX_CACHE_TTL` and the dependencies `after` and `requires_mounts_for` |

`prepare` installs podman with `container_podman` and pulls the image, `check` runs `converge` with `--check` on the VMs where the role never ran.
`side_effect` runs the role with `pass_environment` not a dictionary, an unknown variable, a line break, the former variable `pass_uid`,
`pass_autoupdate_enabled` no boolean and an unknown variable in `pass_container.environment` and checks that it fails with the expected message
and the quadlet unit is unchanged (tasks marked `expect ERROR`), then it changes `GNUPAGENT_MAX_CACHE_TTL` on `molecule-pass`, pass has to restart,
on `molecule-pass-default` the role runs again without a change and pass must not restart.
`verify` checks the quadlet unit, that the container is only attached to the network `none` without an IP address,
the environment and the owner of `/config` in the container and runs `pass version`.

```
cd security_pass
MOLECULE_TART_IMAGE='debian' molecule test
```
