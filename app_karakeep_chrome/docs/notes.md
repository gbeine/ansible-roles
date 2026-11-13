The headless Chrome of Karakeep runs in the container image `ghcr.io/karakeep-app/karakeep-chrome`
(`release` by default, `karakeep_chrome_version` sets the tag) as podman quadlet.
The image contains Google Chrome on amd64 and Chromium on arm64 and runs as `nobody` (65534).
Chrome listens with its DevTools on port 9222, the workers of Karakeep crawl websites with it, `app_karakeep` connects with `BROWSER_WEB_URL=http://<karakeep_chrome_ip>:9222`.
Chrome keeps no data, the role creates no directories.

### Configuration

The image reads no environment variables, Chrome is configured with its flags.
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

The container runs with an init that reaps the processes of Chrome (`RunInit=true`, `init: true` of the compose file).
The init is `catatonit` on the host, the role `container_podman` installs it.

### Secrets

Chrome needs no secrets. The DevTools have no authentication, everybody who reaches port 9222 controls the browser,
so Chrome must only be reachable from the network of Karakeep and must not be published.

### Allowed variables

The role only allows `TZ` in the environment of the container, it is set from `karakeep_chrome_timezone`.
This prevents unexpected behavior by accident, e.g. by a variable meant for another image.
The check uses the environment of the container after merging `karakeep_chrome_container`.
The list is taken from `docker/chrome/Dockerfile` and `docker/chrome/entrypoint.sh` of Karakeep v0.34.1, which read no variables.

### Container

The flags (`command`), the init, ports, additional hosts (`etc_hosts`) and dependencies (`requires`) are changed with `karakeep_chrome_container`,
it is merged over the default of the container. The merge is not recursive.
Labels are set with `karakeep_chrome_labels`.

### Validation

The role checks before any change:

- `karakeep_chrome_container.command` is a list of strings without line breaks
- only `TZ` is set in the environment of the container

If `karakeep_chrome_container` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Restart and updates

Chrome is restarted if it was running and the quadlet unit changed, e.g. after changing the flags, otherwise it is started and enabled.
If the start fails, the role shows the journal of the service.
Afterwards the role waits up to 120 seconds for `/json/version` of the DevTools and shows the journal if Chrome does not answer.
Updates of the image are done by `container_update` with `karakeep_chrome_autoupdate_enabled: true` and `karakeep_chrome_autoupdate_schedule`,
without `karakeep_chrome_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

The role is new, there are no former variables.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root. The VMs need access to `ghcr.io`.

| Platform | Test case |
|---|---|
| `molecule-karakeep-chrome-default` | Only the mandatory variables and the default flags |
| `molecule-karakeep-chrome` | IPv6, labels and an additional flag `--lang=de-DE` |

`prepare` creates the podman network and pulls the image.
`side_effect` runs the role with `karakeep_chrome_container` not a dictionary, the flags as string, a flag that is no string, a line break in a flag
and an unknown environment variable and checks that it fails with the expected message and the quadlet unit is unchanged (tasks marked `expect ERROR`),
then it changes the size of the window on `molecule-karakeep-chrome`, the quadlet unit changes and Chrome has to restart.
`verify` checks the quadlet unit with the init, the service, the addresses, the user, the flags and the environment of the container,
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
