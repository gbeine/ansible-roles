Forgejo Runner runs in the container image [forgejo/runner](https://code.forgejo.org/forgejo/-/packages/container/runner) (`13` by default) as podman quadlet.
See [code.forgejo.org](https://code.forgejo.org/forgejo/-/packages/container/runner/versions) for the values of `forgejo_runner_version`.
`forgejo_runner_home` is mounted to `/data`, the home of the runner, it contains `config.yml` and the cache.
The container runs `forgejo-runner daemon --config /data/config.yml` as the user `forgejo_runner_uid` and the group `forgejo_runner_gid` (defaults to `forgejo_runner_uid`),
the image uses `1000:1000`.

### Configuration

`forgejo_runner_config` is the content of `config.yml` as dictionary, it is merged recursively over the default of the role
and written with `to_nice_yaml` to `<forgejo_runner_home>/config.yml` (mode `0640`).
The default keeps the values of the former role: `log.level` and `log.job_level` `info`, `runner.capacity` `1`, `runner.timeout` `3h`,
`cache.enabled` `true`, `container.privileged` `false`, `container.valid_volumes` `[]` and `container.force_pull` `false`.
All other options use the defaults of the runner, see `internal/pkg/config/config.example.yaml` of Forgejo Runner.
Values of `forgejo_runner_config` are written as they are: a list stays a list (e.g. `runner.labels`), `runner.envs` is a dictionary of variables of the jobs.

```yaml
forgejo_runner_keys:
  connections: [ 'forgejo' ]

forgejo_runner_config:
  runner:
    capacity: 2
    labels: [ 'debian:docker://node:20-bookworm' ]
  container:
    docker_host: 'automount'
  server:
    connections:
      forgejo:
        url: 'https://git.example.org/'
        uuid: '35663065-3164-3263-3362-346135393638'

forgejo_runner_secrets:
  - name: 'forgejo_runner_token'
    data: '5f0e1d2c3b4a59687706f5e4d3c2b1a098765432'
    target: 'server.connections.forgejo.token'
```

The runner needs Docker (or the docker socket of podman) only for labels with `docker://`, labels with `:host` run the jobs in the container of the runner.
The socket is mounted with `forgejo_runner_container.volumes` and set with `container.docker_host` or `DOCKER_HOST`.

### Connections

The runner connects to the Forgejo instances in `server.connections.<name>`, the role does not use `.runner` and `forgejo-runner register`.
Every connection has `url`, `uuid` and the token, optional `labels` (instead of `runner.labels`) and `fetch_interval`.
The runner is registered once in Forgejo with a secret of 40 hexadecimal characters, the secret is the token:

```shell
forgejo forgejo-cli actions register --secret 5f0e1d2c3b4a59687706f5e4d3c2b1a098765432 --name runner --labels debian
```

The command does nothing if the runner already exists.
The UUID of the runner is made from the bytes of the first 16 characters of the secret, e.g. with Python:

```shell
python3 -c "import uuid; print(uuid.UUID(bytes=b'5f0e1d2c3b4a5968'))"
```

A runner registered with the web interface or `forgejo-runner register` has the UUID and the token in `.runner` (`uuid` and `token`).

### Options with keys

The names of the connections are free keys of `server.connections`, they are declared in `forgejo_runner_keys`.
The keys contain letters, digits, `_` and `-`.

| Family | Generated names |
|---|---|
| `connections` | the options `server.connections.<name>.url`, `uuid`, `labels`, `fetch_interval` and the secret `server.connections.<name>.token` |

Every declared connection needs `url`, `uuid` and the secret of its token, a connection in `forgejo_runner_config` without its name in `forgejo_runner_keys` is an unknown option.

```yaml
forgejo_runner_keys:
  connections: [ 'forgejo', 'codeberg' ]
```

### Secrets

The secrets are entries of `forgejo_runner_secrets` with `name`, `data` and `target`, the role creates them with `podman secret`
and mounts them as files `/run/secrets/<name>` (owner `forgejo_runner_uid`, mode `0400`).
The target is the path of the option in `config.yml`, the role writes the reference to the file instead of the value:

| Target | Written to `config.yml` |
|---|---|
| `server.connections.<name>.token` | `server.connections.<name>.token_url: file:/run/secrets/<name of the secret>` |
| `cache.secret` | `cache.secret_url: file:/run/secrets/<name of the secret>` |

The targets, `token_url` and `cache.secret_url` must not be set in `forgejo_runner_config`.
A changed secret restarts the running service.

### Allowed variables

The role only allows the options in `app_forgejo_runner__config_allowed`, the secrets in `app_forgejo_runner__secrets_allowed`
and the environment variables in `app_forgejo_runner__environment_allowed`, it stops before any change if unknown names are set.
This prevents unexpected behavior by accident, e.g. by a typo or an option that has to be passed as secret.
The options are generated from `internal/pkg/config/config.example.yaml` of Forgejo Runner v13.2.2 without the secrets and the options set by the role
(`runner.file`, `runner.env_file`, `cache.secret_url`), the options of the connections are generated from `forgejo_runner_keys`.
New versions of the runner may add options, the lists are generated again.
The environment only takes `TZ` and the variables of the Docker client (`DOCKER_HOST`, `DOCKER_CERT_PATH`, `DOCKER_TLS_VERIFY`),
the options of the runner are set in `config.yml`.
`forgejo_runner_environment` has no default, without it the quadlet unit has no environment.
The check uses the environment of the container after merging `forgejo_runner_container`, so variables set with `forgejo_runner_container.environment` are checked as well.

### Container

Volumes (e.g. the docker socket), additional hosts (`etc_hosts`) and the dependencies are changed with `forgejo_runner_container`, it is merged over the default of the container.
The dependencies of the quadlet unit are lists: `requires`, `wants`, `after`, `part_of` and `binds_to` are units,
`requires_mounts_for` are paths. They are written to `[Unit]` as `Requires=`, `Wants=`, `After=`, `PartOf=`, `BindsTo=` and `RequiresMountsFor=`.
The merge is not recursive, `forgejo_runner_container.volumes` replaces `/data`, `forgejo_runner_container.environment` replaces `forgejo_runner_environment`.

```yaml
forgejo_runner_container:
  volumes:
    - '/opt/forgejo-runner:/data'
    - '/run/podman/podman.sock:/var/run/docker.sock'
  wants: [ 'podman.socket' ]
  after: [ 'podman.socket' ]
```

### Validation

The role checks before any change:

- `forgejo_runner_config` and `forgejo_runner_container` are dictionaries, merging them with the defaults fails otherwise
- `forgejo_runner_keys` is a dictionary of known families with lists of valid and unique keys
- `forgejo_runner_secrets` is a list of entries with `name`, `data` and `target` with unique and valid names
- `forgejo_runner_config` only contains allowed options, neither secrets nor the options of the role, and no line breaks in the values
- at least one connection is declared, every connection has `url`, `uuid` and the secret of its token
- `forgejo_runner_home` is an absolute path, `forgejo_runner_uid` and `forgejo_runner_gid` are numbers
- only allowed environment variables and secrets are set in the container, the values of the environment contain no line breaks

### Check mode

The role runs with `--check` without failing, also on a host where it never ran before.
It reports the changes of the directory, `config.yml`, the secrets and the quadlet unit, the service is neither started nor restarted.

### Restart and updates

The runner is restarted if it was running and `config.yml`, a secret or the quadlet unit changed, otherwise it is started and enabled.
If the start fails, the role stops with the last lines of the journal of the service.
Updates of the image are done by `container_update` with `forgejo_runner_autoupdate_enabled: true` and `forgejo_runner_autoupdate_schedule`,
without `forgejo_runner_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

The setup mode is removed, the runner is configured with `server.connections` instead of `.runner`.
Take `uuid` and `token` from `<forgejo_runner_home>/.runner` of an existing installation, the uuid goes to `server.connections.<name>.uuid`,
the token to the secret `server.connections.<name>.token`, the address of Forgejo to `server.connections.<name>.url`.
The labels of `.runner` go to `runner.labels` or `server.connections.<name>.labels`, `.runner` can be removed afterwards.

| Former variable | Now |
|---|---|
| `forgejo_runner_setup` | removed, the runner starts as daemon with the connections |
| `forgejo_runner_docker_host` | `forgejo_runner_config.container.docker_host` or `DOCKER_HOST` in `forgejo_runner_environment`, no longer mandatory |
| `forgejo_runner_log_level` | `forgejo_runner_config.log.level` |
| `forgejo_runner_log_job_level` | `forgejo_runner_config.log.job_level` |
| `forgejo_runner_container_environment` | `forgejo_runner_config.runner.envs` |
| `forgejo_runner_container_privileged` | `forgejo_runner_config.container.privileged` |
| `forgejo_runner_container_valid_volumes` | `forgejo_runner_config.container.valid_volumes` |
| `forgejo_runner_container_force_pull` | `forgejo_runner_config.container.force_pull` |
| `forgejo_runner_user` | removed, it was not used |
| `forgejo_runner_home`, `forgejo_runner_ip`, `forgejo_runner_ipv6`, `forgejo_runner_network`, `forgejo_runner_hostname`, `forgejo_runner_timezone`, `forgejo_runner_uid`, `forgejo_runner_gid`, `forgejo_runner_version`, `forgejo_runner_container`, `forgejo_runner_autoupdate_enabled` | stay |

- The default of `forgejo_runner_version` changes from `12` to `13`.
- `config.yml` is written with `to_nice_yaml` instead of a template, `.env` is removed (`runner.env_file` is not set).
- The command of the container was `--config ' /data/config.yml'` with a leading space, it is `--config /data/config.yml` now.
- The variables `USER_UID` and `USER_GID` are removed, the image does not read them, the user is set with `forgejo_runner_uid`.
- `forgejo_runner_config`, `forgejo_runner_secrets`, `forgejo_runner_keys`, `forgejo_runner_environment`, `forgejo_runner_labels` and `forgejo_runner_autoupdate_schedule` are new.
- The volumes `/etc/localtime` and `/etc/timezone` are removed, the timezone is set by podman.
- The dependencies `requires`, `wants`, `after`, `part_of`, `binds_to` and `requires_mounts_for` of `forgejo_runner_container` are new.
- The service is not stopped on every run anymore, `podman___update_mode` is removed.
- The tag `app_forgejo_runner` stays, the tag `app` is added.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-forgejo-runner-default` | Only the mandatory variables and one connection with the label in `runner.labels` |
| `molecule-forgejo-runner` | IPv6, labels, dependencies, options, labels of the connection, `runner.envs`, the secret `cache.secret` and `DOCKER_HOST` |

`prepare` creates the podman network, pulls the images, starts Forgejo with SQLite and registers the runner with `forgejo-cli actions register`.
`check` runs `converge` with `--check` on the new VMs.
`side_effect` runs the role with `forgejo_runner_container` and `forgejo_runner_config` not a dictionary, `forgejo_runner_keys` not a dictionary,
an unknown family, an invalid key, a secret without `target`, a connection missing in `forgejo_runner_keys`, a connection without `uuid`,
a connection without the secret of its token, no connection, the token in `forgejo_runner_config`, `runner.file`, an unknown option, a line break in a value,
an unknown environment variable, an unknown secret, a line break in `forgejo_runner_container.environment` and a relative home
and checks that it fails with the expected message and the quadlet unit and `config.yml` are unchanged (tasks marked `expect ERROR`),
then it changes `runner.capacity` on `molecule-forgejo-runner`, the runner has to restart,
`molecule-forgejo-runner-default` runs again without a change and must not restart.
`verify` checks the quadlet unit with the secrets as files and without their values, the command, the user and the dependencies,
`config.yml` with `token_url` and without the token, its mode and owner, the service without automatic restarts,
the addresses, the environment, the user and the time zone of the container
and that the runner declared its labels to Forgejo (`declared successfully` in the journal).

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd app_forgejo_runner
MOLECULE_TART_IMAGE='debian' molecule test
```
