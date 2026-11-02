pass runs in the container image `c0d3.sh/container/pass-docker` as podman quadlet.
The image is based on the [linuxserver.io](https://www.linuxserver.io) Alpine base image and contains `pass`, `gpg-agent` and `git`.
The password store is in `<pass_home>/.password-store`, the GnuPG home in `<pass_home>/.gnupg`, both are mounted as `/config`.
The container has no network, it is used with `podman exec`, e.g.:

```shell
podman exec -it -u abc pass pass show example.org
```

### Environment

The files in `/config` belong to `pass_uid` and `pass_gid` (default `911`), they are passed as `PUID` and `PGID` to the base image.
Further variables are set with `pass_environment`, e.g. the cache durations of the gpg-agent in seconds:

```yaml
pass_environment:
  GNUPAGENT_DEFAULT_CACHE_TTL: '900'
  GNUPAGENT_MAX_CACHE_TTL: '7776000'
  GNUPAGENT_DEFAULT_CACHE_TTL_SSH: '1800'
  GNUPAGENT_MAX_CACHE_TTL_SSH: '7776000'
```

### Restart and updates

pass is restarted if it was running and the quadlet unit changed, e.g. by a changed environment variable.
Updates of the image are done by `container_update` with `pass_autoupdate_enabled: true` and optionally `pass_autoupdate_schedule`,
without `pass_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

| Before | Now |
|---|---|
| `podman___update_mode` | `pass_autoupdate_enabled` |

### Tests

The molecule scenario `default` uses tart with one VM `molecule-pass`.
`prepare` installs podman with `container_podman`, `side_effect` changes `GNUPAGENT_MAX_CACHE_TTL` and checks that pass was restarted.
`verify` checks the quadlet unit, that the container is only attached to the network `none` without an IP address, the environment in the container and runs `pass version`.
The VM needs access to `c0d3.sh`.

```
cd security_pass
MOLECULE_TART_IMAGE='debian' molecule test
```
