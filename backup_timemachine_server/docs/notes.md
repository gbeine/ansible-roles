The role runs [mbentley/timemachine](https://github.com/mbentley/docker-timemachine), a Samba based Time Machine server, as podman quadlet.
It supports the single user mode and the multi user mode of the image.

### Environment

The image is configured with environment variables, see the [list of variables](https://github.com/mbentley/docker-timemachine#optional-variables-for-smb).
All variables are set with `timemachine_server_environment`, which is merged over the defaults of the role.
The role checks the required variables before it changes anything:

| Variable | Default of the role |
|---|---|
| `TM_USERNAME` | `timemachine` |
| `TM_GROUPNAME` | `timemachine` |
| `TM_UID` | `1000` |
| `TM_GID` | `1000` |
| `VOLUME_SIZE_LIMIT` | `0` (no limit) |
| `WORKGROUP` | `WORKGROUP` |
| `SET_PERMISSIONS` | `false` |

Variables carrying secrets are passed as podman secrets with `timemachine_server_secrets` (`name`, `data`, `target`) and must not be set in `timemachine_server_environment`.
`target` is the usual name of the variable, the only secret of the image is `PASSWORD`.
The role creates the secret with `podman secret create`, mounts it to `/run/secrets/<name>` and sets `PASSWORD_FILE`,
so the password is neither part of the quadlet unit nor of the environment of the container.

### Single user mode

Without `timemachine_server_users` the image creates one user from the environment.
The password is required and has to be a secret with the target `PASSWORD`, otherwise the image would use its default password `timemachine`:

```yaml
timemachine_server_environment:
  TM_USERNAME: 'gerrit'
  SHARE_NAME: 'TimeMachine'
  VOLUME_SIZE_LIMIT: '2 T'
timemachine_server_secrets:
  - name: 'timemachine_password'
    data: "{{ vault_timemachine_password }}"
    target: 'PASSWORD'
```

### Multi user mode

Every entry in `timemachine_server_users` becomes a file `<TM_USERNAME>.conf` in `timemachine_server_home/external`, mounted as `EXTERNAL_CONF` into the container.
Every entry needs `TM_USERNAME`, `TM_GROUPNAME`, `SHARE_NAME`, `VOLUME_SIZE_LIMIT`, `TM_UID` and `TM_GID`, values are quoted for the shell.
The passwords are set in `timemachine_server_passwords` with the username as key and written to `<username>.pw`.
The image only reads the `.conf` files, so the role adds `PASSWORD_FILE` to the `.conf` file of every user with an entry in `timemachine_server_passwords`.
A user may also set `PASSWORD` or `PASSWORD_FILE` in its entry, but `PASSWORD` is stored in plain text in the `.conf` file.

```yaml
timemachine_server_users:
  - TM_USERNAME: 'alice'
    TM_GROUPNAME: 'alice'
    SHARE_NAME: 'alice'
    VOLUME_SIZE_LIMIT: '1 T'
    TM_UID: 1001
    TM_GID: 1001
  - TM_USERNAME: 'bob'
    TM_GROUPNAME: 'bob'
    SHARE_NAME: 'bob'
    VOLUME_SIZE_LIMIT: '500 G'
    TM_UID: 1002
    TM_GID: 1002
timemachine_server_passwords:
  alice: "{{ vault_timemachine_alice }}"
  bob: "{{ vault_timemachine_bob }}"
```

`.conf` and `.pw` files of users that are not declared anymore are removed.
Switching to the single user mode removes all of them.

### Network

Without `timemachine_server_network` the container runs in the host network, so Avahi can announce the shares to the Macs.
Samba or Avahi must not run on the host in that case.
With a podman network and `timemachine_server_ip` the shares are not discovered automatically, set `ADVERTISED_HOSTNAME` or connect with `smb://<address>/<share>`.
`timemachine_server_interfaces` restricts the interfaces Avahi uses.

The storage below `timemachine_server_home/opt` must support extended attributes.
The users have their own passwords, a secret with the target `PASSWORD` is not allowed in the multi user mode,
the image would use it for every user without own password.

### Allowed variables

The role only allows the environment variables in `backup_timemachine_server__environment_allowed` and the secret with the target `PASSWORD`,
it stops before any change if unknown variables or secrets are set.
This prevents unexpected behavior by accident, e.g. by a typo or a variable that has to be passed as secret.
The check uses the environment and the secrets of the container after merging `timemachine_server_container`,
so variables set with `timemachine_server_container.environment` are checked as well.
The allowed variables are the variables of the image for SMB (`entrypoint.sh` and README of mbentley/docker-timemachine) without `PASSWORD`, and the file variable `PASSWORD_FILE`.
The role sets `PASSWORD_FILE` from `timemachine_server_secrets`, it must not be set in `timemachine_server_environment`.
The variables of the AFP variant of the image are not allowed.

### Validation

The role checks before any change that `timemachine_server_secrets` is a list of entries with `name`, `data` and `target` and unique names,
that the required variables are set, that neither a secret nor its file variable is set in `timemachine_server_environment`,
that the password is a secret in the single user mode and not in the multi user mode, that every user is complete
and that only allowed variables and secrets are used.
If `timemachine_server_container` is no dictionary, merging it with the default fails before anything changes.

### Restarts and updates

A running container is restarted when users, passwords, secrets, the Avahi configuration or the quadlet unit changed.
The first start of the container does not trigger an additional restart.
Updates of the image are done by `container_update` with `timemachine_server_autoupdate_enabled: true` and `timemachine_server_autoupdate_schedule`.

### Migration from the single variables

| Former variable | Now |
|---|---|
| `timemachine_server_advertised_hostname` | `ADVERTISED_HOSTNAME` |
| `timemachine_server_username` | `TM_USERNAME` |
| `timemachine_server_groupname` | `TM_GROUPNAME` |
| `timemachine_server_volume_size` | `VOLUME_SIZE_LIMIT` |
| `timemachine_server_workgroup` | `WORKGROUP` |

In the single user mode a secret with the target `PASSWORD` is required now.
In the multi user mode the passwords from `timemachine_server_passwords` were written to `.pw` files, but not used by the image; they are used now via `PASSWORD_FILE`.

The secret of the password is mounted as file and read with `PASSWORD_FILE`, before it was passed as environment variable `PASSWORD`, `timemachine_server_secrets` stays the same.
`podman___update_mode` is not evaluated anymore, the role neither stops the container nor pulls the image or recreates the container,
the configuration files are always written.
The tags are `backup` and `backup_timemachine_server`.

### Tests

The molecule scenario `default` runs the role in one [tart](https://tart.run) VM `molecule-timemachine` on a macOS controller, the base VM has to be Debian 13.
The base VM is cloned and the clone is deleted afterwards, the base VM itself is never changed.
The playbooks creating and destroying the VM are shared by all tart scenarios and live in `.molecule/tart/` in the repository root.

| Step | What happens |
|---|---|
| `prepare` | sets up podman and the network `podman-molecule` with the role `container_podman`, pulls the image and installs `smbclient` |
| `converge`, `idempotence` | multi user mode with the users `alice` and `bob` in the podman network on `10.89.0.10` |
| `side_effect` | checks the multi user mode, runs the role with `timemachine_server_container` not a dictionary, `timemachine_server_secrets` not a list, the secret of the password together with users, `PASSWORD_FILE` in the environment, an unknown environment variable in `timemachine_server_environment` and in `timemachine_server_container.environment` and an unknown secret and checks that it fails with the expected message and the quadlet unit is unchanged (tasks marked `expect ERROR`), then runs the role again in the single user mode with the user `molecule` and the password as secret |
| `verify` | checks the single user mode |

Both checks cover the quadlet unit with the mounted secret, the user files, the service, the environment of the container with `PASSWORD_FILE` and without password,
a login with `smbclient` that has to list the shares, and a login with invalid credentials that has to be rejected.
The passwords in `molecule/default/test_cases.yml` are test passwords only.
The VM needs access to Docker Hub.

Requirements on the controller: `tart`, `sshpass` (`brew install hudochenkov/sshpass/sshpass`), `molecule` and the collection `containers.podman`.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd backup_timemachine_server
MOLECULE_TART_IMAGE='debian' molecule test
```
