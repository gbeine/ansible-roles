FileRise runs in the container image [error311/filerise-docker](https://hub.docker.com/r/error311/filerise-docker)
(`latest` by default, `filerise_version` sets the tag) as podman quadlet. Apache serves the web interface on port 80 of the container.
`filerise_home` contains the directories `uploads`, `users` and `metadata`, they are mounted to `/var/www/uploads`, `/var/www/users` and `/var/www/metadata`.
The role installs one instance, `tasks/loop.yml` installs several (see Multiple instances).

### Configuration

FileRise is configured with environment variables in `filerise_environment`, it is merged over the default of the role.
The image has no configuration file for the options: `config/config.php` is part of the code, `start.sh` of the image writes
the environment into it at every start and the code reads the other variables with `getenv()`.

The default of the role sets `TIMEZONE` to `filerise_timezone`, it is the time zone of PHP, without it FileRise uses America/New_York.
`PUID` and `PGID` are `99` and `100` like in the image, `start.sh` runs Apache as `www-data` with these ids,
the role creates the directories in `filerise_home` with this owner and mode `0775`, like `start.sh` sets them at every start.
The time zone of the container is set by podman with `filerise_timezone`, `TZ` is not needed.

```yaml
filerise_environment:
  PUID: '1000'
  PGID: '1000'
  TOTAL_UPLOAD_SIZE: '10G'
  DATE_TIME_FORMAT: 'd.m.Y H:i'
  SHARE_URL: 'https://files.example.org/api/file/share.php'
  FR_TRUSTED_PROXIES: '10.89.0.0/24'
```

`SECURE` is only set if it is given, without it FileRise uses the protocol of the request.
`TOTAL_UPLOAD_SIZE` is `5G` in the image.

### Secrets

`filerise_secrets` is a list of podman secrets with `name`, `data` and `target`, no secret is required.

| Target | Passed as |
|---|---|
| `FR_PRO_LICENSE`, the license of FileRise Pro | file `/run/secrets/<name>`, the role sets `FR_PRO_LICENSE_FILE` |
| `PERSISTENT_TOKENS_KEY`, the key of the persistent tokens | environment variable `PERSISTENT_TOKENS_KEY` |
| `FR_ENCRYPTION_MASTER_KEY`, the master key of the encryption at rest | environment variable `FR_ENCRYPTION_MASTER_KEY` |

The license is mounted with the owner `PUID`/`PGID` and mode `0400`, FileRise reads it from `FR_PRO_LICENSE_FILE`.
`PERSISTENT_TOKENS_KEY` and `FR_ENCRYPTION_MASTER_KEY` are passed with `type=env`, FileRise reads them only with `getenv()`,
`start.sh` reads the key of the persistent tokens otherwise only from the fixed file `metadata/persistent_tokens.key`.
Without the secret `start.sh` creates the key in `metadata/persistent_tokens.key` and keeps it.
The secrets are not part of the quadlet unit, podman sets them when the container starts.
Neither a target nor `FR_PRO_LICENSE_FILE` may be set in `filerise_environment`.

```yaml
filerise_secrets:
  - name: 'filerise_tokens_key'
    data: "{{ vault_filerise_tokens_key }}"
    target: 'PERSISTENT_TOKENS_KEY'
```

### Allowed variables

The role only allows the environment variables in `app_filerise__environment_allowed` and the secrets listed in Secrets,
it stops before any change if unknown variables or secrets are set.
This prevents unexpected behavior by accident, e.g. by a typo or a variable that has to be passed as secret.
The check uses the environment of the container after merging `filerise_container`.

The list is generated from `start.sh`, `config/config.php` and the code below `src` of FileRise v3.45.0, new versions may add variables.
The variables of the tests (`FR_TEST_*`, `FR_DAV_TEST_*`), the internal variables (`FR_AUTH_BYPASS_*`, `FR_PORTAL_GET_AUTH_*`, `FR_ROOT`,
`PERSISTENT_TOKENS_KEY_SOURCE`) and the variables of the web server are not allowed.

### Container

The container is named `filerise`, every instance needs its own name in `filerise_container.name`.
Ports, volumes, additional hosts (`etc_hosts`) and the dependencies are changed with `filerise_container`, it is merged over the default of the container.
The dependencies of the quadlet unit are lists: `requires`, `wants`, `after`, `part_of` and `binds_to` are units,
`requires_mounts_for` are paths. They are written to `[Unit]` as `Requires=`, `Wants=`, `After=`, `PartOf=`, `BindsTo=` and `RequiresMountsFor=`.

```yaml
filerise_container:
  publish:
    - '8080:80'
  wants: [ 'network-online.target' ]
  after: [ 'network-online.target' ]
```

The merge is not recursive, `volumes` replaces the directories of the default, `environment` replaces `filerise_environment`.
For a reverse proxy, e.g. Traefik, the labels are set with `filerise_labels`.

### Validation

The role checks before any change:

- `filerise_secrets` is a list of entries with `name`, `data` and `target` and unique names, only the targets of Secrets are used
- neither a target nor `FR_PRO_LICENSE_FILE` is set in `filerise_environment`
- `filerise_home` is an absolute path, `PUID` and `PGID` are numbers
- only allowed environment variables are set in the container, the values contain no line breaks

If `filerise_container` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Check mode

The role runs with `--check` without failing, also on a host where it never ran before.
It reports the changes of the directories, the secrets and the quadlet unit, the service is neither started nor restarted.

### Restart and updates

FileRise is restarted if it was running and a secret or the quadlet unit changed, otherwise it is started and enabled.
If the start fails, the role stops with the last lines of the journal of the service.
Updates of the image are done by `container_update` with `filerise_autoupdate_enabled: true` and `filerise_autoupdate_schedule`,
without `filerise_autoupdate_schedule` the schedule of `container_update` is used.

### Multiple instances

`tasks/loop.yml` runs the role for every entry of `filerise_instances`. Every entry takes the variables without the prefix `filerise_`,
missing keys fall back to the defaults of the role. Every instance needs its own home, container name and secret names.

Include `tasks/loop.yml` in the play instead of the role:

```yaml
- name: 'Configure host.example.org'
  become: 'yes'
  hosts: 'host23'
  tasks:
    - tags: [ 'app_filerise' ]
      ansible.builtin.include_tasks:
        file: 'roles/app_filerise/tasks/loop.yml'
```

The instances are defined in `filerise_instances`, e.g. in the host variables:

```yaml
filerise_instances:
  - home: '/opt/filerise-team'
    hostname: 'filerise-team'
    ip: '10.89.0.21'
    network: 'podman'
    timezone: 'Europe/Berlin'
    container:
      name: 'filerise-team'
  - home: '/opt/filerise-family'
    hostname: 'filerise-family'
    ip: '10.89.0.22'
    ipv6: 'fd00:89::22'
    network: 'podman'
    timezone: 'Europe/Berlin'
    container:
      name: 'filerise-family'
    environment:
      PUID: '1034'
      PGID: '1034'
    secrets:
      - name: 'filerise_family_tokens_key'
        data: "{{ vault_filerise_family_tokens_key }}"
        target: 'PERSISTENT_TOKENS_KEY'
```

### Migration

- `filerise_containers` is replaced by the variables of one instance or by `filerise_instances` with `tasks/loop.yml`,
  the keys of an entry keep their meaning: `name` is `container.name`, `hostname`, `ip`, `ipv6`, `labels`, `etc_hosts` and `publish` are `labels` and `container`.
- `uploads_dir`, `users_dir` and `metadata_dir` are replaced by `home` with the directories `uploads`, `users` and `metadata`.
  Move the former directories below the new home, or keep them with `filerise_container.volumes`.
- `uid` and `gid` of an entry are `PUID` and `PGID` in `filerise_environment`, the former role did not pass them to the container, the image used 99 and 100.
- `filerise_secure` is `SECURE` in `filerise_environment`, the former role always set `SECURE: 'false'`.
- `filerise_upload_size` is `TOTAL_UPLOAD_SIZE` in `filerise_environment`, the default `5G` of the image is the former default.
- `environment` and `secrets` of an entry are `environment` and `secrets` of the instance, the secrets are checked now.
- The directories had mode `0755` and were changed recursively, the role creates them with `0775` like `start.sh` of the image and changes only the directories, `start.sh` changes the ownership of the files.
- `podman___update_mode` is not evaluated anymore, the role neither stops the container nor pulls the image or recreates the container.
- The tag `app` is added to `app_filerise`.
- The dependencies in `filerise_container`, `filerise_autoupdate_enabled` and `filerise_autoupdate_schedule` are new.

### Tests

The molecule scenarios run the role in [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-filerise-default` | Only the mandatory variables, `PUID` 99 and `PGID` 100 of the image |
| `molecule-filerise` | IPv6, labels, dependencies, own `PUID` and `PGID`, `DATE_TIME_FORMAT`, `PERSISTENT_TOKENS_KEY` in the environment and the license as file |
| `molecule-filerise-loop` | Scenario `loop`, two instances with `tasks/loop.yml`, one with IPv4 only, one with IPv6, own `PUID` and the license |

`check` runs `converge` with `--check` on the new VMs.
`prepare` creates the podman network and pulls the image.
`side_effect` runs the role with `filerise_container` not a dictionary, a secret without target, an unknown secret,
`PERSISTENT_TOKENS_KEY` and `FR_PRO_LICENSE_FILE` in the environment, an unknown variable and a line break in the environment,
a relative `filerise_home` and `PUID` not a number and checks that it fails with the expected message and the quadlet unit is unchanged (tasks marked `expect ERROR`),
then it changes the key of the persistent tokens on `molecule-filerise`, FileRise has to restart, `molecule-filerise-default` runs again without a change and must not restart.
`verify` checks every instance: the quadlet unit with only the secrets of the instance, the dependencies and without `TZ` and the files of the host,
the service without automatic restarts, the directories with their owner and mode, the addresses, the environment and the time zone,
the license file and the key in the container, creates the administrator, logs in with it with the form login and checks that a wrong password is rejected.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd app_filerise
MOLECULE_TART_IMAGE='debian' molecule test
MOLECULE_TART_IMAGE='debian' molecule test -s loop
```
