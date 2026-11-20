GitLab Runner runs in the container image [gitlab/gitlab-runner](https://hub.docker.com/r/gitlab/gitlab-runner) (`latest` by default, `gitlab_runner_version` sets the tag) as podman quadlet.
`gitlab_runner_home` is mounted as `/etc/gitlab-runner`, it contains `config.toml` of the runner (root, `0700`).
The socket of podman on the host (`/run/podman/podman.sock`) is mounted as `/var/run/docker.sock`,
the docker executor runs the jobs in containers of the podman of the host. `container_podman` enables `podman.socket`,
the quadlet unit wants and starts after `podman.socket`.

### Configuration

`config.toml` belongs to the runner: `gitlab-runner register` writes the runner to it and the runner reloads and updates it itself.
The role creates `config.toml` without runners (`concurrent = 1`) if it does not exist and never changes it afterwards.

The role registers the runner once, if `gitlab_runner_secrets` contains the authentication token of the runner (`glrt-…`, the target `token`)
and `config.toml` contains no `[[runners]]` entry:

1. it writes `gitlab_runner_config` as template of the runner to `register.toml` in the home directory,
2. runs `gitlab-runner register --non-interactive --url <gitlab_runner_url> --name <gitlab_runner_hostname> --executor <executor> --template-config register.toml`
   once in the container `gitlab-runner-init` of the image with the home directory and the network of the role,
3. removes `register.toml` and `gitlab-runner-init`, also if the registration failed.

`gitlab_runner_config` is one `[[runners]]` entry of `config.toml` as dictionary, merged recursively over the default of the role,
the docker executor with the image `alpine:latest`. The template is only used by the registration,
a changed template, URL or token does not change a registered runner.
To register the runner again, remove the runner in GitLab and `config.toml` in the home directory and run the role with a new token.

```yaml
gitlab_runner_url: 'https://gitlab.example.org'
gitlab_runner_config:
  executor: 'docker'
  environment: [ 'GIT_DEPTH=10' ]
  docker:
    image: 'alpine:3.20'
    privileged: false
    volumes: [ '/cache' ]
gitlab_runner_secrets:
  - name: 'gitlab_runner_token'
    data: "{{ vault_gitlab_runner_token }}"
    target: 'token'
```

Without the token the role does not register the runner, the runner starts without runners and waits.
It can be registered later with the token, or by hand with `podman exec -it gitlab-runner gitlab-runner register`.

The docker executor uses the socket of podman, privileged jobs (e.g. Docker-in-Docker) need `privileged: true` and a podman that allows them.

### Secrets

`gitlab_runner_secrets` is a list with `name`, `data` and `target`, the only target is `token`, the authentication token of the runner created in GitLab.
`config.toml` cannot read the token from a file and `gitlab-runner register` cannot read it from a file either,
so the token is a podman secret passed with `type=env,target=CI_SERVER_TOKEN` to the container of the registration only.
It is neither part of the quadlet unit nor of the environment of the runner, `register` writes it to `config.toml` (`0600`).

### Allowed variables

The role only allows the options of a `[[runners]]` entry in `gitlab_runner_config`, the executors of GitLab Runner,
the environment variables in `app_gitlab_runner__environment_allowed` and the target `token`, it stops before any change if unknown names are set.
This prevents unexpected behavior by accident, e.g. by a typo or a token in the environment.

The options and the executors are generated from `docs/configuration/advanced-configuration.md` of GitLab Runner v19.6.0,
the content of the subsections (e.g. `docker`, `cache`, `kubernetes`) is not checked. `name`, `url` and `token` are set by the role.
The environment is generated from the entrypoint of the image, the flags of `run` and `log/configuration.go`:
`TZ`, `CA_CERTIFICATES_PATH`, `LISTEN_ADDRESS`, `LOG_SYSLOG`, `LOG_FORMAT`, `LOG_LEVEL` and `RUNNER_DEBUG`.
`gitlab_runner_environment` has no default, without it the quadlet unit has no environment.

### Container

Ports, volumes, additional hosts (`etc_hosts`) and the dependencies are changed with `gitlab_runner_container`, it is merged over the default of the container.
The dependencies of the quadlet unit are lists: `requires`, `wants`, `after`, `part_of` and `binds_to` are units,
`requires_mounts_for` are paths. They are written to `[Unit]` as `Requires=`, `Wants=`, `After=`, `PartOf=`, `BindsTo=` and `RequiresMountsFor=`.
The default wants and starts after `podman.socket`.
The merge is not recursive, `gitlab_runner_container.volumes` replaces the home directory and the socket, `wants` and `after` replace `podman.socket`.

```yaml
gitlab_runner_container:
  wants: [ 'podman.socket', 'network-online.target' ]
  after: [ 'podman.socket', 'network-online.target' ]
```

### Validation

The role checks before any change:

- `gitlab_runner_config` and `gitlab_runner_container` are dictionaries, merging them with the defaults fails otherwise
- `gitlab_runner_config` only contains options of `[[runners]]`, not `name`, `url` or `token`, an allowed executor and no values with line breaks
- `gitlab_runner_secrets` is a list of entries with name, data and target, the names and targets are unique, the target is `token`, the data a string without line breaks
- `gitlab_runner_url` is an http or https URL, it is set if the token is set
- `gitlab_runner_home` is an absolute path
- only allowed environment variables are set in the container, their values contain no line breaks

### Check mode

The role runs with `--check`, also on a host where it never ran, and reports the home directory, `config.toml`, the secret and the quadlet unit.
The registration and the start do not run in check mode.

### Restart and updates

GitLab Runner is restarted if it was running and the quadlet unit changed, otherwise it is started and enabled.
The runner reloads `config.toml` itself, the registration needs no restart. If the start fails, the role stops with the last lines of the journal.
Updates of the image are done by `container_update` with `gitlab_runner_autoupdate_enabled: true` and `gitlab_runner_autoupdate_schedule`,
without `gitlab_runner_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

The former role imported the role `podman`, which does not exist anymore, so it failed. It is a quadlet unit now.

- `gitlab_runner_hostname` is mandatory, the default `gitlab-runner.localhost` is removed, it is the name of the runner in GitLab as well.
- `gitlab_runner_docker_sock` is replaced by `gitlab_runner_container.volumes`, the default is the socket of podman instead of `/var/run/docker.sock`.
- `gitlab_runner_hosts` is `gitlab_runner_container.etc_hosts`.
- `gitlab_runner_ip`, `gitlab_runner_network` and `gitlab_runner_home` stay, an existing `config.toml` with runners is kept and not registered again.
- `gitlab_runner_timezone` is mandatory, `gitlab_runner_url`, `gitlab_runner_config`, `gitlab_runner_secrets`, `gitlab_runner_ipv6`, `gitlab_runner_labels`,
  `gitlab_runner_environment`, `gitlab_runner_version` and `gitlab_runner_autoupdate_*` are new.
- The container was started with `restart_policy: always`, the former container `gitlab-runner` has to be removed before the first run (`podman rm -f gitlab-runner`).
- The tag `app` is added to `app_gitlab_runner`.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root, `molecule-gitlab-runner` gets 6 GB and 4 CPUs for GitLab.

| Platform | Test case |
|---|---|
| `molecule-gitlab-runner-default` | Only the mandatory variables, without token the runner is not registered |
| `molecule-gitlab-runner` | IPv6, labels, the environment and the registration at GitLab with the token and a template |

`prepare` creates the podman network and pulls the image, on `molecule-gitlab-runner` it starts GitLab CE, waits until it is ready
and creates an instance runner with `gitlab-rails runner`, its token is the secret of the test case.
`check` runs `converge` with `--check` on the new VMs.
`side_effect` runs the role with `gitlab_runner_container` and `gitlab_runner_config` not a dictionary, an unknown option, the token in the template,
an unknown executor, a line break in the template, an unknown secret, a token without `gitlab_runner_url`, an unknown environment variable,
a line break in the environment and a relative home and checks that it fails with the expected message and the quadlet unit and `config.toml` are unchanged
(tasks marked `expect ERROR`), then it changes the environment and the template on `molecule-gitlab-runner`,
the runner has to restart without a second registration, `molecule-gitlab-runner-default` runs again without a change and must not restart.
`verify` checks the quadlet unit with the socket of podman and without the token, `config.toml` with the runner and the options of the first template,
the removed template and container of the registration, the service without automatic restarts, the addresses, the time zone and the environment,
`gitlab-runner verify` in the container and that GitLab reports the runner as online.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd app_gitlab_runner
MOLECULE_TART_IMAGE='debian' molecule test
```
