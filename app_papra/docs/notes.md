Papra runs in the container image `ghcr.io/papra-hq/papra` (`latest` by default, the rootless image, `papra_version` sets the tag) as podman quadlet.
It listens on port 1221 and runs as the user `nonroot` (999) of the image. `<papra_home>` is mounted to `/app/app-data`,
it contains the SQLite database (`db`), the documents (`documents`) and the configuration file. Papra migrates the database on every start.

### Configuration

Papra is configured with its configuration file, the options are set in `papra_config`, merged recursively over the default of the role (empty).
The keys are the options of Papra as nested dictionaries, see the [configuration of Papra](https://docs.papra.app/self-hosting/configuration),
e.g. `auth.isRegistrationEnabled` is `auth: { isRegistrationEnabled: false }`. `appBaseUrl`, the public URL of Papra, is mandatory.
Booleans are YAML booleans, `null` removes an option.

```yaml
papra_config:
  appBaseUrl: 'https://papra.example.org'
  auth:
    isRegistrationEnabled: false
  documents:
    ocrLanguages: 'deu,eng'
```

The role writes `<papra_home>/papra.config.mjs`, Papra reads it from `PAPRA_CONFIG_DIR` (`/app/app-data`) on the start.
The options of the file take precedence over the environment (figue merges the file over the environment).
The file is JavaScript, so it reads the secrets from their files, a JSON or YAML file could not.
`papra_environment` only takes `TZ` and `NODE_OPTIONS`, without it the container has no environment.
The time zone of the container is `papra_timezone`, the image sets no `TZ` and Papra does not read it.

### Secrets

`papra_secrets` is a list of podman secrets with `name`, `data` and `target`, the target is the path of the option, e.g. `auth.secret`.
The secrets are mounted as files to `/run/secrets/<name>` (owner 999, mode `0400`), `papra.config.mjs` reads them with `readFileSync`
and sets the option, neither the quadlet unit nor the configuration file contains them.
`auth.secret` is mandatory and needs at least 32 characters, it signs the sessions, e.g. from `openssl rand -hex 48`.
The allowed targets are listed in `app_papra__secrets_allowed`, e.g. `database.encryptionKey`, `documentsStorage.drivers.s3.secretAccessKey`,
`emails.drivers.smtp.password` or `ai.adapters.openai.apiKey`, none of them may be set in `papra_config`.

```yaml
papra_secrets:
  - name: 'papra_auth_secret'
    data: "{{ vault_papra_auth_secret }}"
    target: 'auth.secret'
```

### Administrator

Papra has no administrator of its own, the first user who signs up becomes the administrator (`auth.firstUserAsAdmin`).
The role signs in as `papra_admin` (`name`, `email` and `password`) after the start and signs it up if the sign-in is refused,
the requests use the origin of `appBaseUrl`. Between the first start and the sign-up another user could sign up first,
keep Papra unreachable until the first run of the role finished.
A changed password in `papra_admin` does not change the user, the role fails then, the password is changed in Papra.
The sign-up needs `auth.isRegistrationEnabled`, disable it after the first run if no other users sign up.

```yaml
papra_admin:
  name: 'Admin'
  email: 'admin@example.org'
  password: "{{ vault_papra_admin_password }}"
```

### Allowed options

The role only allows the options in `app_papra__config_allowed`, the secrets in `app_papra__secrets_allowed`
and the environment variables `TZ` and `NODE_OPTIONS`, it stops before any change if unknown options, secrets or variables are set.
This prevents unexpected behavior by accident, e.g. by a typo or an option that has to be passed as secret.
The lists are generated from `papra-config-schema.json` of Papra 26.7.1, new versions of the image may add options.
Not allowed are `env`, `version`, `gitCommitSha` and `gitCommitDate`, set by the image, and `auth.providers.customs`,
it contains the client secrets of the providers in JSON and cannot be passed as secret.

### Container

Ports, volumes, additional hosts (`etc_hosts`) and the dependencies are changed with `papra_container`, it is merged over the default of the container.
The dependencies of the quadlet unit are lists: `requires`, `wants`, `after`, `part_of` and `binds_to` are units,
`requires_mounts_for` are paths. They are written to `[Unit]` as `Requires=`, `Wants=`, `After=`, `PartOf=`, `BindsTo=` and `RequiresMountsFor=`.
The merge is not recursive, `papra_container.volumes` replaces the data directory and the configuration file.
For a reverse proxy, e.g. Traefik, the labels are set with `papra_labels`.

```yaml
papra_container:
  wants: [ 'network-online.target' ]
  after: [ 'network-online.target' ]
```

### Validation

The role checks before any change:

- `papra_secrets` is a list of entries with `name`, `data` and `target` with unique names and targets
- `papra_config` is a dictionary with known options and without secrets, `appBaseUrl` is an http or https URL,
  booleans are YAML booleans, strings contain no line breaks
- the targets of the secrets are known, `auth.secret` is set and has at least 32 characters, the secrets contain no line breaks
- `papra_environment` is a dictionary with `TZ` or `NODE_OPTIONS` without line breaks
- `papra_admin` has a name, a valid email and a password of at least 8 characters

If `papra_container` or `papra_config` is no dictionary, merging it fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Check mode

The role runs with `--check`, also on a host where it never ran, and reports the directories, the secrets, the configuration file and the quadlet unit.
The start, the wait for Papra and the administrator do not run in check mode.

### Restart and updates

Papra reads the configuration and the secrets only on start, it is restarted if it was running and the configuration file,
a secret or the quadlet unit changed, otherwise it is started and enabled. If the start fails, the role shows the error and the journal of the service.
Afterwards the role waits until `/api/health` reports `isEverythingOk` and shows the journal otherwise.
Updates of the image are done by `container_update` with `papra_autoupdate_enabled: true` and `papra_autoupdate_schedule`,
without `papra_autoupdate_schedule` the schedule of `container_update` is used. Papra migrates the database on the start.

### Migration

- `papra_config` is new, the options were set with `papra_container.environment` before, e.g. `APP_BASE_URL` is `appBaseUrl`,
  `AUTH_IS_REGISTRATION_ENABLED` is `auth.isRegistrationEnabled`.
- The targets of `papra_secrets` are the paths of the options now, e.g. `AUTH_SECRET` is `auth.secret`, the secrets are files instead of variables.
- `papra_admin` is new and mandatory, an existing administrator signs in with it.
- `/etc/localtime` and `/etc/timezone` are not mounted anymore, the time zone is set by podman with `papra_timezone`.
- `podman___update_mode` is not evaluated anymore, the role neither stops the container nor pulls the image or recreates the container.
- `papra_labels` has no default anymore, `papra_environment` and `papra_autoupdate_schedule` are new, the tags are `app` and `app_papra`.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root. The VMs need access to `ghcr.io`.

| Platform | Test case |
|---|---|
| `molecule-papra-default` | Only the mandatory variables, `appBaseUrl`, `auth.secret` and the administrator |
| `molecule-papra` | IPv6, labels, `NODE_OPTIONS`, nested options, a boolean and the secret `intakeEmails.webhookSecret` |

`prepare` creates the podman network and pulls the image.
`check` runs `converge` with `--check` on the new VMs.
`side_effect` runs the role with `papra_container`, `papra_config` and `papra_environment` not a dictionary, an unknown option,
a secret in the configuration, without `appBaseUrl`, a string as boolean, a line break in an option, a secret without `target`, a short `auth.secret`,
an unknown secret, an option in the environment and an administrator without password
and checks that it fails with the expected message and the quadlet unit and the configuration file are unchanged (tasks marked `expect ERROR`),
then it changes `documents.ocrLanguages` on `molecule-papra`, the configuration file changes, the quadlet unit not, and Papra has to restart,
`molecule-papra-default` runs again without a change, the administrator is not signed up again and Papra must not restart.
`verify` checks the quadlet unit and the configuration file without secrets, the owner and the mode of the configuration file,
the service without automatic restarts, the addresses, the time zone and the environment, the health check,
the sign-in of the administrator, a refused wrong password and the permissions of the administrator.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd app_papra
MOLECULE_TART_IMAGE='debian' molecule test
```
