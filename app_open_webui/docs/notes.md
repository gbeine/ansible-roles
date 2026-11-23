Open WebUI runs in the container image `ghcr.io/open-webui/open-webui` (`0.13` by default, `open_webui_version` sets the tag) as podman quadlet.
It listens on port 8080 and runs as root. The data (`webui.db`, uploads, caches and the vector database) is kept in `<open_webui_home>/data`,
mounted as `/app/backend/data`.

### Configuration

Open WebUI is configured with environment variables in `open_webui_environment`, it has no configuration file.
On the first start Open WebUI stores most of the values in its database, afterwards the database takes precedence and the values are changed
in the administration. With `ENABLE_PERSISTENT_CONFIG: 'false'` the environment takes precedence on every start.
Booleans are the strings `'true'` or `'false'`, YAML booleans are rejected.
The time zone of the container is `open_webui_timezone`, the image sets no `TZ` and the role sets no default for it.
The variables are described in the [documentation of Open WebUI](https://docs.openwebui.com/reference/env-configuration).

```yaml
open_webui_environment:
  WEBUI_URL: 'https://chat.example.org'
  OLLAMA_BASE_URL: 'http://ollama:11434'
  ENABLE_SIGNUP: 'false'
```

Without internet access set `OFFLINE_MODE: 'true'`, Open WebUI does not download the embedding models then.

### Secrets

`open_webui_secrets` is a list of podman secrets with `name`, `data` and `target`, the usual name of the variable.
`WEBUI_SECRET_KEY` is mandatory, it signs the sessions. Without it `start.sh` of the image creates a new key outside of the data directory
with every new container and all sessions become invalid. `start.sh` reads it from the file `WEBUI_SECRET_KEY_FILE`,
so it is mounted as file to `/run/secrets/<name>` and the role sets `WEBUI_SECRET_KEY_FILE`.
Open WebUI reads all other secrets, e.g. `OPENAI_API_KEY`, `DATABASE_URL` or `OAUTH_CLIENT_SECRET`, only from the environment,
they are passed with `type=env,target=<target>` and are not part of the quadlet unit.
The allowed targets are `WEBUI_SECRET_KEY` and `app_open_webui__secrets_env`, none of them and no file variable may be set in `open_webui_environment`.

```yaml
open_webui_secrets:
  - name: 'open_webui_secret_key'
    data: "{{ vault_open_webui_secret_key }}"
    target: 'WEBUI_SECRET_KEY'
  - name: 'open_webui_openai_api_key'
    data: "{{ vault_openai_api_key }}"
    target: 'OPENAI_API_KEY'
```

### Administrator

Without users the first user who signs up becomes the administrator. The role creates the administrator of `open_webui_admin`
(`name`, `email` and `password`) on the first deployment, Open WebUI disables the signup afterwards.
Open WebUI creates the administrator from `WEBUI_ADMIN_EMAIL`, `WEBUI_ADMIN_NAME` and `WEBUI_ADMIN_PASSWORD` on its start if there is no user,
so the role starts Open WebUI once in the container `open-webui-init` with these variables, the password as podman secret
`<container name>_admin_password` in the environment of this container only, waits until `/ready` of this container answers and removes the container.
The quadlet unit never contains these variables.

The initialization only runs if `<open_webui_home>/data/webui.db` and the quadlet unit do not exist.
With an external database (secret `DATABASE_URL`) there is no `webui.db`, the quadlet unit shows the first deployment then.
A changed password in `open_webui_admin` does not change the administrator, the password is changed in Open WebUI.

```yaml
open_webui_admin:
  name: 'Admin'
  email: 'admin@example.org'
  password: "{{ vault_open_webui_admin_password }}"
```

### Allowed variables

The role only allows the environment variables in `app_open_webui__environment_allowed` and the secrets listed above,
it stops before any change if unknown variables or secrets are set.
This prevents unexpected behavior by accident, e.g. by a typo or a variable that has to be passed as secret.
The check uses the environment and the secrets of the container after merging `open_webui_container`.
The lists are generated from the variables read by `backend/` and `start.sh` of Open WebUI v0.13.4, new versions of the image may add variables.
Not allowed are `WEBUI_ADMIN_*` of the initialization, `WEBUI_SECRET_KEY_FILE` set by the role, `SPACE_ID` and `ADMIN_USER_*` of Hugging Face Spaces
and the variables of the build of the image (`DOCKER`, `USE_*_DOCKER`, `WEBUI_BUILD_HASH`).

### Container

Ports, volumes, additional hosts (`etc_hosts`) and the dependencies are changed with `open_webui_container`, it is merged over the default of the container.
The dependencies of the quadlet unit are lists: `requires`, `wants`, `after`, `part_of` and `binds_to` are units,
`requires_mounts_for` are paths. They are written to `[Unit]` as `Requires=`, `Wants=`, `After=`, `PartOf=`, `BindsTo=` and `RequiresMountsFor=`.
The merge is not recursive, `open_webui_container.volumes` replaces the data directory,
`open_webui_container.environment` replaces the environment including `open_webui_environment` and `WEBUI_SECRET_KEY_FILE`.
For a reverse proxy, e.g. Traefik, the labels are set with `open_webui_labels`.

```yaml
open_webui_container:
  wants: [ 'network-online.target' ]
  after: [ 'network-online.target' ]
```

### Validation

The role checks before any change:

- `open_webui_secrets` is a list of entries with `name`, `data` and `target` and unique names, `WEBUI_SECRET_KEY` is set
- `open_webui_environment` is a dictionary without secrets, file variables and `WEBUI_ADMIN_*`, booleans are the strings `true` or `false`,
  secrets and values contain no line breaks
- `open_webui_admin` has a name, a valid email and a password of at least 8 characters without line breaks
- only allowed environment variables without line breaks and allowed secrets are set in the container

If `open_webui_container` or `open_webui_environment` is no dictionary, the role fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Check mode

The role runs with `--check`, also on a host where it never ran, and reports the directories, the secrets and the quadlet unit.
The initialization, the start and the wait for Open WebUI do not run in check mode.

### Restart and updates

Open WebUI is restarted if it was running and a secret or the quadlet unit changed, otherwise it is started and enabled.
If the start fails, the role shows the error and the journal of the service.
Afterwards the role waits until `/ready` answers, Open WebUI answers it after its startup, and shows the journal if Open WebUI does not answer.
Updates of the image are done by `container_update` with `open_webui_autoupdate_enabled: true` and `open_webui_autoupdate_schedule`,
without `open_webui_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

- The data directory is `<open_webui_home>/data` instead of `<open_webui_home>`, move the content of `<open_webui_home>` to `<open_webui_home>/data`
  before the first run, or set `open_webui_container.volumes`.
- `open_webui_secrets` needs a `target` for every entry, the secret key is the target `WEBUI_SECRET_KEY`,
  formerly the image created a key with every new container.
- `open_webui_admin` is new and mandatory. An existing installation has a database and a quadlet unit, the initialization does not run.
- `open_webui_environment` is new, the variables were set with `open_webui_container.environment` before.
- The default of `open_webui_version` is `0.13` instead of `main`.
- `/etc/localtime` and `/etc/timezone` are not mounted anymore, the time zone is set by podman with `open_webui_timezone`.
- `podman___update_mode` is not evaluated anymore, the role neither stops the container nor pulls the image or recreates the container.
- `open_webui_labels` has no default anymore, `open_webui_autoupdate_schedule` is new, the tags are `app` and `app_open_webui`.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root. The VMs need access to `ghcr.io`, the image is large.
Open WebUI loads torch and the embedding models, the VMs get 6 GB of memory and 4 CPUs.

| Platform | Test case |
|---|---|
| `molecule-open-webui-default` | Only the mandatory variables, the secret key and the administrator, SQLite |
| `molecule-open-webui` | IPv6, labels, `OFFLINE_MODE`, `ENABLE_OLLAMA_API`, `WEBUI_NAME` and the secret `OPENAI_API_KEY` |

`prepare` creates the podman network and pulls the image.
`check` runs `converge` with `--check` on the new VMs.
`side_effect` runs the role with `open_webui_container` and `open_webui_environment` not a dictionary, a secret without `target`,
without `WEBUI_SECRET_KEY`, `OPENAI_API_KEY` and the password of the administrator in the environment, an invalid boolean, a YAML boolean,
a line break in a value, an unknown environment variable, an unknown secret and an administrator without password
and checks that it fails with the expected message and the quadlet unit is unchanged (tasks marked `expect ERROR`),
then it changes `WEBUI_NAME` on `molecule-open-webui`, the quadlet unit changes and Open WebUI has to restart,
`molecule-open-webui-default` runs again without a change, the initialization does not run again and Open WebUI must not restart.
`verify` checks the quadlet unit without secrets, without the password and the variables of the administrator,
the service without automatic restarts, the addresses, the time zone and the environment, that `open-webui-init` was removed and the database exists,
the health check, the sign-in of the administrator with the role `admin`, a refused wrong password and the refused signup of another user.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd app_open_webui
MOLECULE_TART_IMAGE='debian' molecule test
```
