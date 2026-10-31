The role runs the [restic REST server](https://github.com/restic/rest-server) as podman quadlet.
The repositories are stored in `restic_server_home`, mounted as `/data` into the container.

### Users

The role manages the users of the server in `restic_server_home/.htpasswd` (bcrypt, mode `0600`) with `htpasswd` from `apache2-utils` on the host.
Passwords are passed to `htpasswd` via stdin and are only changed when they differ.
Users that are not declared anymore are removed.

```yaml
restic_server_users:
  - name: 'alice'
    password: "{{ vault_restic_server_alice }}"
  - name: 'bob'
    password: "{{ vault_restic_server_bob }}"
```

At least one user is required unless `DISABLE_AUTHENTICATION` is set in `restic_server_environment`.
`PASSWORD_FILE` must not be set, the role manages `/data/.htpasswd`.

### Environment

The server is configured with `restic_server_environment`, see the [Docker documentation of the rest server](https://github.com/restic/rest-server#docker):

```yaml
restic_server_environment:
  OPTIONS: '--append-only --private-repos --prometheus'
```

| Option in `OPTIONS` | Description |
|---|---|
| `--append-only` | Backups can be added, but not deleted or changed |
| `--private-repos` | Every user can only access the repositories below `/<username>` |
| `--prometheus` | Metrics on `/metrics`, the user `metrics` is required unless `--prometheus-no-auth` is set |

### Restarts

A running container is restarted when users or the quadlet unit changed.
The first start of the container does not trigger an additional restart.

### Clients

The credentials of the server can be passed to restic via environment variables, so they do not appear in the repository URL:

```shell
export RESTIC_REST_USERNAME='alice'
export RESTIC_REST_PASSWORD='...'
export RESTIC_PASSWORD='...'
restic -r rest:https://backup.example.org/alice init
```

### Migration from the single variables

| Former variable | Now |
|---|---|
| `restic_server_append_only: true` | `--append-only` in `OPTIONS` |
| `restic_server_private_repos: true` | `--private-repos` in `OPTIONS` |

Users created manually with `create_user` are removed by the role unless they are declared in `restic_server_users`.

### Tests

The molecule scenario `default` runs the role in one [tart](https://tart.run) VM `molecule-restic-server` on a macOS controller, the base VM has to be Debian 13.
The base VM is cloned and the clone is deleted afterwards, the base VM itself is never changed.
The playbooks creating and destroying the VM are shared by all tart scenarios and live in `.molecule/tart/` in the repository root.

| Step | What happens |
|---|---|
| `prepare` | sets up podman and the network `podman-molecule` with the role `container_podman`, pulls the image and installs `restic` and `curl` |
| `converge`, `idempotence` | users `alice` and `bob`, `OPTIONS: '--append-only --private-repos'` |
| `side_effect` | checks the first run, then runs the role again: `bob` is removed, `alice` gets a new password |
| `verify` | checks the second run |

Both checks cover the quadlet unit, the users and hashes in `.htpasswd`, the service and the answer `401` without credentials.
Every valid user initializes its private repository, backs up a file and lists the snapshot, deleting the snapshot has to fail because of `--append-only`.
Rejected credentials (wrong password, removed user, repository of another user) must not access a repository.
The passwords in `molecule/default/test_cases.yml` are test passwords only.
The VM needs access to Docker Hub.

Requirements on the controller: `tart`, `sshpass` (`brew install hudochenkov/sshpass/sshpass`), `molecule` and the collection `containers.podman`.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd backup_restic_server
MOLECULE_TART_IMAGE='debian' molecule test
```
