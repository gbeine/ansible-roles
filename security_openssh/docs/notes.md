The OpenSSH server runs in the container image [linuxserver/openssh-server](https://docs.linuxserver.io/images/docker-openssh-server/) (`latest` by default) as podman quadlet `openssh`.
sshd runs as one unprivileged user, `<home>/config` is mounted to `/config` and keeps the configuration, the host keys, `authorized_keys` and the logs.

### Configuration

```yaml
openssh_home: '/srv/container/openssh'
openssh_ip: '192.168.99.62'
openssh_network: 'podman99'
openssh_hostname: 'openssh'
openssh_timezone: 'Europe/Berlin'
openssh_environment:
  PUBLIC_KEY: 'ssh-ed25519 AAAA... backup@example.org'
  USER_NAME: 'backup'
openssh_config:
  AllowTcpForwarding: false
  ClientAliveInterval: 30
```

The image is configured with `openssh_environment`, it is merged over the default of the role (`TZ`, `PUID` and `PGID` 1000):

- `PUBLIC_KEY` is mandatory, the image adds it to `/config/.ssh/authorized_keys` at every start,
  `PUBLIC_KEY_FILE`, `PUBLIC_KEY_DIR` and `PUBLIC_KEY_URL` add further keys from files in the container or from a URL
- `USER_NAME` is the user to log in (`linuxserver.io` by default), `PUID` and `PGID` its IDs
- `LISTEN_PORT` is the port of sshd (2222 by default), the default of the container publishes it on the same port of the host
- `PASSWORD_ACCESS: true` allows the login with the password, `SUDO_ACCESS: true` allows sudo, with the password of the user if it is set
- `UMASK` is the umask of sftp, `LOG_STDOUT: true` logs to the journal instead of `/config/logs`

The image only adds keys to `authorized_keys`, it never removes them.
A key removed from the environment is still allowed to log in until it is removed from `<home>/config/.ssh/authorized_keys`.

`openssh_config` contains options of sshd, the role writes them to `<home>/config/sshd/sshd_config.d/ansible.conf`,
the image includes this directory before its own options, so these options take precedence:

- a string or number writes `Option value`, a list writes one line per element
- `true` and `false` write `yes` and `no`, sshd has no options without value
- `null` removes the option

`Port` and `PasswordAuthentication` are set by the image with `LISTEN_PORT` and `PASSWORD_ACCESS`,
`PidFile` and `HostKey` belong to the image and `Include` and `Match` would change the meaning of the following options,
they must not be set in `openssh_config`.

### Secrets

The secrets are set with `openssh_secrets`, every entry needs `name`, `data` and `target`, the only target is `USER_PASSWORD`, the password of the user.
The image reads it from the file of `USER_PASSWORD_FILE`, the role mounts the secret to `/run/secrets/<name>` and sets the file variable.
Neither `USER_PASSWORD` nor `USER_PASSWORD_FILE` may be set in `openssh_environment`.
Without password the image sets a random password, the password is needed for `PASSWORD_ACCESS` and for sudo with password.

```yaml
openssh_secrets:
  - name: 'openssh_user_password'
    data: "{{ vault_openssh_user_password }}"
    target: 'USER_PASSWORD'
```

### Allowed variables

The role only allows the environment variables in `security_openssh__environment_allowed` and the secret `USER_PASSWORD`,
it stops before any change if unknown variables or secrets are set.
This prevents unexpected behavior by accident, e.g. by a typo or a password in the environment.
The list is generated from the init scripts of docker-openssh-server and its base image,
`DOCKER_MODS` is not allowed, it downloads and runs code at every start of the container.
The check uses the environment of the container after merging `openssh_container`, so variables set with `openssh_container.environment` are checked as well.

### Container

Ports, volumes, additional hosts (`etc_hosts`) and dependencies (`requires`) are changed with `openssh_container`, it is merged over the default of the container.
The merge is not recursive, `publish` and `volumes` replace the values of the default completely,
`openssh_container.environment` replaces the environment including `openssh_environment`, use `openssh_environment` instead.

```yaml
openssh_container:
  publish:
    - '22:2222'
  volumes:
    - '/srv/container/openssh/config:/config'
    - '/srv/backup:/backup'
```

### Validation

The role checks before any change:

- `openssh_secrets` is a list of entries with `name`, `data` and `target` and unique names, only `USER_PASSWORD` is a target
- `PUBLIC_KEY` is set, no secret or file variable is set in `openssh_environment`, no secret contains a line break
- `SUDO_ACCESS`, `PASSWORD_ACCESS` and `LOG_STDOUT` are `true` or `false`, `PUID`, `PGID` and `LISTEN_PORT` are numbers,
  `USER_NAME` is a name of a user and not `root`, `UMASK` is an octal umask and no value contains a line break
- `openssh_config` is a dictionary of options named by letters and digits, without the options of the image and the role,
  with strings, numbers, booleans, `null` or lists of them without line breaks
- only allowed environment variables are set in the container
- sshd accepts the options of `openssh_config`, `sshd -t` checks the file in a container of the image without network before it is replaced

If `openssh_container` or `openssh_environment` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Restart and updates

OpenSSH is restarted if it was running and the secret, the options of sshd or the quadlet unit changed, otherwise it is started and enabled.
If the start fails, the role shows the journal of the service.
Afterwards the role waits up to 120 seconds until sshd sends its banner and shows the journal otherwise.
The role creates `<home>/config`, `<home>/config/sshd` and `sshd_config.d` with the owners and modes the image sets at every start, so the role stays idempotent.
Updates of the image are done by `container_update` with `openssh_autoupdate_enabled: true` and `openssh_autoupdate_schedule`,
without `openssh_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

| Former variable | Replacement |
|---|---|
| `openssh_home`, `openssh_ip`, `openssh_ipv6`, `openssh_network`, `openssh_hostname`, `openssh_timezone`, `openssh_autoupdate_enabled` | Unchanged |
| `openssh_public_key` | `PUBLIC_KEY` of `openssh_environment` |
| `openssh_user_name` | `USER_NAME` of `openssh_environment` |
| `openssh_public_port` | `openssh_container.publish`, e.g. `[ '22:2222' ]` |
| `openssh_volumes` | `openssh_container.volumes`, together with `<home>/config:/config` |
| none | `openssh_environment`, `openssh_secrets`, `openssh_config`, `openssh_container`, `openssh_labels`, `openssh_version`, `openssh_autoupdate_schedule` |
| `podman___update_mode` | Removed, updates are done by `container_update` |

Changed behavior:

- `/etc/localtime` and `/etc/timezone` are no longer mounted, the time zone is set with `openssh_timezone` and `TZ`,
  the quadlet unit changes once and OpenSSH restarts
- `openssh_container` is merged over the default of the container, the former role ignored it
- the role creates `<home>/config/sshd/sshd_config.d`, the image includes it from now on
- the environment, the secrets and the options of sshd are checked before any change
- the role restarts OpenSSH if the secret, the options of sshd or the quadlet unit changed and waits until sshd answers
- the tags are `security` and `security_openssh`

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root. The VMs need access to lscr.io.

| Platform | Test case |
|---|---|
| `molecule-openssh-default` | Only the mandatory variables, the user `linuxserver.io` on port 2222 |
| `molecule-openssh` | IPv6, labels, the user `molecule` on port 2022, sudo with the password as file, `UMASK` and options of sshd |

`prepare` creates the podman network, installs the ssh client, creates a key pair and pulls the image,
`converge` adds the public key of the key pair as `PUBLIC_KEY`.
`side_effect` runs the role with `openssh_container` not a dictionary, `openssh_secrets` not a list, a secret without target, an unknown secret,
without `PUBLIC_KEY`, the password and its file variable in the environment, `DOCKER_MODS`, invalid values of the environment,
`openssh_config` not a dictionary, invalid options and an option unknown to sshd
and checks that it fails with the expected message and the quadlet unit and the options of sshd are unchanged (tasks marked `expect ERROR`),
then it changes an option of sshd on `molecule-openssh`, the file of `sshd_config.d` changes and OpenSSH has to restart.
`verify` checks the quadlet unit without the mounts of the time zone and without the password, the service, the environment,
the owners and modes of the directories and of the options of sshd, the effective configuration of sshd (`sshd -T`),
logs in with the key, checks that the login with a password is denied and on `molecule-openssh` runs sudo with the password read from the file of the secret.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd security_openssh
MOLECULE_TART_IMAGE='debian' molecule test
```
