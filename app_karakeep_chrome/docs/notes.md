The headless Chrome of Karakeep runs in the container image `ghcr.io/karakeep-app/karakeep-chrome`
(`release` by default, `karakeep_chrome_version` sets the tag) as podman quadlet.
The image contains Google Chrome on amd64 and Chromium on arm64 and runs as `nobody` (65534).
Chrome listens with its DevTools on port 9222, the workers of Karakeep crawl websites with it, `app_karakeep` connects with `BROWSER_WEB_URL=http://<karakeep_chrome_ip>:9222`.
Chrome keeps no data, the role creates no directories.

### Configuration

Chrome is configured with its flags. The environment of the container is set with `karakeep_chrome_environment`,
without it the container has no environment. The time zone of the container is `karakeep_chrome_timezone`,
Chrome reads it from `/etc/localtime`, the image sets no `TZ` and the role sets no default for it.
The flags are the command of the container, the default of the role are the flags of the compose file of Karakeep:
`--disable-gpu`, `--disable-dev-shm-usage`, `--hide-scrollbars`, `--disable-blink-features=AutomationControlled` and `--window-size=1440,900`.
The entrypoint of the image adds the flags of the headless mode and of the DevTools.

The flags are changed with `karakeep_chrome_container.command`, a list of strings that replaces the default:

```yaml
karakeep_chrome_container:
  command:
    - '--disable-gpu'
    - '--disable-dev-shm-usage'
    - '--hide-scrollbars'
    - '--disable-blink-features=AutomationControlled'
    - '--window-size=1440,900'
    - '--lang=de-DE'
```

The entrypoint of the image starts Chrome with `--no-sandbox` unless `KARAKEEP_CHROME_SANDBOX` is `true`.
The sandbox of Chrome needs unprivileged user namespaces in the container,
see the [README of the image](https://github.com/karakeep-app/karakeep/blob/main/docker/chrome/README.md#sandbox).
The value is the string `true` or `false`, YAML booleans are rejected:

```yaml
karakeep_chrome_environment:
  KARAKEEP_CHROME_SANDBOX: 'true'
```

The container runs with an init that reaps the processes of Chrome (`RunInit=true`, `init: true` of the compose file).
The init is `catatonit` on the host, the role `container_podman` installs it.

### Secrets

Chrome needs no secrets. The DevTools have no authentication, everybody who reaches port 9222 controls the browser,
so Chrome must only be reachable from the network of Karakeep and must not be published.

### Allowed variables

The role only allows `KARAKEEP_CHROME_SANDBOX` and `TZ` in the environment of the container (`app_karakeep_chrome__environment_allowed`).
This prevents unexpected behavior by accident, e.g. by a variable meant for another image.
The check uses the environment of the container after merging `karakeep_chrome_container`.
The list is taken from `docker/chrome/Dockerfile` and `docker/chrome/entrypoint.sh` of Karakeep v0.35.0, new versions of the image may add variables.

### Container

The flags (`command`), the init, ports, additional hosts (`etc_hosts`) and the dependencies are changed with `karakeep_chrome_container`,
it is merged over the default of the container. The merge is not recursive,
`karakeep_chrome_container.environment` replaces the environment including `karakeep_chrome_environment`.
The dependencies of the quadlet unit are lists: `requires`, `wants`, `after`, `part_of` and `binds_to` are units,
`requires_mounts_for` are paths. They are written to `[Unit]` as `Requires=`, `Wants=`, `After=`, `PartOf=`, `BindsTo=` and `RequiresMountsFor=`.
Labels are set with `karakeep_chrome_labels`.

```yaml
karakeep_chrome_container:
  wants: [ 'network-online.target' ]
  after: [ 'network-online.target' ]
```

### Validation

The role checks before any change:

- `karakeep_chrome_container.command` is a list of strings without line breaks
- `karakeep_chrome_environment` is a dictionary, `KARAKEEP_CHROME_SANDBOX` is the string `true` or `false`, values contain no line breaks
- only allowed environment variables without line breaks are set in the container

If `karakeep_chrome_container` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Check mode

The role runs with `--check`, also on a host where it never ran, and reports the quadlet unit.
The start and the wait for the DevTools do not run in check mode.

### Restart and updates

Chrome is restarted if it was running and the quadlet unit changed, e.g. after changing the flags, otherwise it is started and enabled.
If the start fails, the role shows the error and the journal of the service.
Afterwards the role waits up to 120 seconds for `/json/version` of the DevTools and shows the journal if Chrome does not answer.
Updates of the image are done by `container_update` with `karakeep_chrome_autoupdate_enabled: true` and `karakeep_chrome_autoupdate_schedule`,
without `karakeep_chrome_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

The role sets no default for `TZ` anymore, the time zone of the container is `karakeep_chrome_timezone`.
If needed, `TZ` is set in `karakeep_chrome_environment`.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root. The VMs need access to `ghcr.io`.

| Platform | Test case |
|---|---|
| `molecule-karakeep-chrome-default` | Only the mandatory variables and the default flags, without environment |
| `molecule-karakeep-chrome` | IPv6, labels, an additional flag `--lang=de-DE` and `KARAKEEP_CHROME_SANDBOX: 'false'` |

`prepare` creates the podman network and pulls the image.
`check` runs `converge` with `--check` on the new VMs.
`side_effect` runs the role with `karakeep_chrome_container` not a dictionary, the flags as string, a flag that is no string, a line break in a flag,
an unknown environment variable, `karakeep_chrome_environment` not a dictionary, an invalid value and a YAML boolean of `KARAKEEP_CHROME_SANDBOX` and a line break in a value and checks that it fails with the expected message and the quadlet unit is unchanged (tasks marked `expect ERROR`),
then it changes the size of the window on `molecule-karakeep-chrome`, the quadlet unit changes and Chrome has to restart,
`molecule-karakeep-chrome-default` runs again without a change and must not restart.
`verify` checks the quadlet unit with the init, the service without automatic restarts, the addresses, the user, the flags,
the time zone and the environment of the container without `TZ`,
reads the version of the DevTools and opens and closes a tab.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd app_karakeep_chrome
MOLECULE_TART_IMAGE='debian' molecule test
```
