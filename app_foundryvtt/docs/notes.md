Foundry VTT runs in the container image `c0d3cr.io/container/foundry` as podman quadlet, `foundryvtt_version` is the tag of the image, e.g. `14.369` or `14`.
The image contains the Node.js release of Foundry VTT and starts it with `node /foundry/main.js --dataPath=/data --headless`, it listens on port 30000.
`foundryvtt_home` is mounted to `/data`, it contains `Config`, `Data` and `Logs` of Foundry VTT.
The image runs as user `99` without a group, the role runs the container as `99:100` and creates the home with this owner and mode `0750`.
The role installs one instance, `tasks/loop.yml` installs several (see Multiple instances).

The license, the end user license agreement and the administrator password are set in the setup of Foundry VTT on the first start.
The license is signed online for the instance and stored in `Config/license.json`, the password is stored as hash in `Config/admin.txt`, the role touches neither file.

### Configuration

Foundry VTT manages its options itself, the role never writes `Config/options.json`.
Foundry VTT creates the file on the first start and saves the options of the setup to it, e.g. the hostname, the proxy, UPnP and the language.
The data path (`--dataPath=/data`) and the port 30000 of the container are set by the image, the ports of the host are set with `foundryvtt_container.publish`.

### Secrets

The role has no secrets. The administrator password is not an option of `options.json`, Foundry VTT stores its hash in `Config/admin.txt` when it is set in the setup.

### Allowed variables

The role only allows the environment variables in `app_foundryvtt__environment_allowed`, it stops before any change if unknown variables are set.
This prevents unexpected behavior by accident, e.g. by a typo.
The list is generated from `dist` of Foundry VTT 14.369 and the `Dockerfile` of the image, new releases may add variables.
The environment only takes `TZ`, `NODE_OPTIONS` and the variables read by Foundry VTT
(`FOUNDRY_ACME_DIRECTORY`, `FOUNDRY_IP_SERVICE`, `FOUNDRY_PACKAGE_DETAILS_URL`, `FOUNDRY_PACKAGE_INDEX_URL`, `FOUNDRY_PACKAGE_OWNED_URL`).
`FOUNDRY_DATA`, `FOUNDRY_HOME` and `FOUNDRY_VTT_DATA_PATH` are set by the image and its command, `PUID` and `GUID` of the image have no effect.
`foundryvtt_environment` has no default, without it the quadlet unit has no environment.
The check uses the environment of the container after merging `foundryvtt_container`, so variables set with `foundryvtt_container.environment` are checked as well.

### Container

The container is named `foundryvtt`, every instance needs its own name in `foundryvtt_container.name`.
`backup_foundryvtt` finds the containers with the filter `foundry-.*` by default, e.g. `foundry-team`.
No port is published, Foundry VTT is reached with a reverse proxy, e.g. Traefik with `foundryvtt_labels`, or with `foundryvtt_container.publish`.
Ports, volumes, additional hosts (`etc_hosts`) and the dependencies are changed with `foundryvtt_container`, it is merged over the default of the container.
The dependencies of the quadlet unit are lists: `requires`, `wants`, `after`, `part_of` and `binds_to` are units,
`requires_mounts_for` are paths. They are written to `[Unit]` as `Requires=`, `Wants=`, `After=`, `PartOf=`, `BindsTo=` and `RequiresMountsFor=`.
The merge is not recursive, `foundryvtt_container.volumes` replaces `/data`.

```yaml
foundryvtt_container:
  name: 'foundry-team'
  publish: [ '30000:30000' ]
  wants: [ 'network-online.target' ]
  after: [ 'network-online.target' ]
```

### Validation

The role checks before any change:

- `foundryvtt_container` is a dictionary, merging it with the default fails otherwise
- `foundryvtt_home` is an absolute path
- only allowed environment variables are set in the container, their values contain no line breaks

### Check mode

The role runs with `--check` without failing, also on a host where it never ran before.
It reports the changes of the home directory and the quadlet unit, the service is neither started nor restarted.

### Restart and updates

Foundry VTT is restarted if it was running and the quadlet unit changed, otherwise it is started and enabled.
If the start fails, the role stops with the last lines of the journal of the service.
Updates of the image are done by `container_update` with `foundryvtt_autoupdate_enabled: true` and `foundryvtt_autoupdate_schedule`,
without `foundryvtt_autoupdate_schedule` the schedule of `container_update` is used.
A tag like `14` follows the builds of the major release, a tag like `14.369` stays on the build.

### Multiple instances

`tasks/loop.yml` runs the role for every entry of `foundryvtt_instances`. Every entry takes the variables without the prefix `foundryvtt_`,
missing keys fall back to the defaults of the role. Every instance needs its own home and container name.

Include `tasks/loop.yml` in the play instead of the role:

```yaml
- name: 'Configure host.example.org'
  become: 'yes'
  hosts: 'host23'
  tasks:
    - tags: [ 'app_foundryvtt' ]
      ansible.builtin.include_tasks:
        file: 'roles/app_foundryvtt/tasks/loop.yml'
```

The instances are defined in `foundryvtt_instances`, e.g. in the host variables:

```yaml
foundryvtt_instances:
  - home: '/opt/foundry-team'
    hostname: 'foundry-team'
    ip: '10.89.0.31'
    network: 'podman'
    timezone: 'Europe/Berlin'
    version: '14'
    container:
      name: 'foundry-team'
  - home: '/opt/foundry-family'
    hostname: 'foundry-family'
    ip: '10.89.0.32'
    ipv6: 'fd00:89::32'
    network: 'podman'
    timezone: 'Europe/Berlin'
    version: '13'
    container:
      name: 'foundry-family'
    environment:
      NODE_OPTIONS: '--max-old-space-size=2048'
```

### Migration

- `foundryvtt_name` is replaced by `foundryvtt_container.name`, the default is `foundryvtt`.
  Set the former name, e.g. `foundry-team`, to keep the service and the filter of `backup_foundryvtt`.
- `foundryvtt_containers` and `foundryvtt_volumes` are removed, the former role did not use them.
- `foundryvtt_ipv6` and `foundryvtt_labels` are optional now.
- `/etc/timezone` and `/etc/localtime` of the host are not mounted anymore, the time zone is set by podman with `foundryvtt_timezone`.
- The container runs as `99:100`, the former container ran as `99:0` because the image has no group.
  The role creates `foundryvtt_home` with owner `99:100` and mode `0750`, the former role did not create it.
- The entries of `foundryvtt_instances` take `network`, `timezone`, `container`, `environment`,
  `autoupdate_enabled` and `autoupdate_schedule`, the former `tasks/loop.yml` did not pass them, `name` is `container.name`.
- `podman___update_mode` is not evaluated anymore, the role neither stops the container nor pulls the image or recreates the container.
- The tag `app` is added to `app_foundryvtt`.
- `foundryvtt_autoupdate_schedule` has no default anymore, without it the schedule of `container_update` is used,
  the former role passed `0 0 * * *` without it.
- The dependencies in `foundryvtt_container` are new.

### Tests

The molecule scenarios run the role in [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root. The VMs need access to `c0d3cr.io`.

| Platform | Test case |
|---|---|
| `molecule-foundryvtt-default` | Only the mandatory variables |
| `molecule-foundryvtt` | IPv6, labels, dependencies, own container name and `NODE_OPTIONS` |
| `molecule-foundryvtt-loop` | Scenario `loop`, two instances with `tasks/loop.yml`, one with IPv4 only, one with IPv6 |

`check` runs `converge` with `--check` on the new VMs.
`prepare` creates the podman network and pulls the image.
`side_effect` runs the role with `foundryvtt_container` not a dictionary, an unknown environment variable, `FOUNDRY_DATA`,
a line break in the environment and a relative home
and checks that it fails with the expected message and the quadlet unit and `options.json` are unchanged (tasks marked `expect ERROR`),
then it changes `NODE_OPTIONS` on `molecule-foundryvtt`, Foundry VTT has to restart,
`molecule-foundryvtt-default` runs again without a change and must not restart.
`verify` checks every instance: the quadlet unit with the user, the volume and the dependencies and without the time zone files of the host,
the home with its owner and mode, `options.json` created by Foundry VTT, the service without automatic restarts,
the addresses, the environment and the time zone of the container and `/api/status` of Foundry VTT with the release of the image.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd app_foundryvtt
MOLECULE_TART_IMAGE='debian' molecule test
MOLECULE_TART_IMAGE='debian' molecule test -s loop
```
