Node-RED runs in the official container image [nodered/node-red](https://nodered.org/docs/getting-started/docker) as podman quadlet.
The role writes its `settings.js` and the users of the editor, see the [configuration of Node-RED](https://nodered.org/docs/user-guide/runtime/configuration).
`nodered_home` is mounted to `/data`, the image starts Node-RED with `--userDir /data`, it contains `settings.js`, the flows, the credentials and the installed nodes.
Node-RED runs as the user `node-red` (uid 1000) of the image and listens on port 1880 (`uiPort`).

### Configuration

`nodered_config` contains the options of `settings.js`, see `settings.js` of Node-RED.
It is merged recursively over the default of the role, the active options of `settings.js` of Node-RED 5.0.9 with `uiPort: 1880`.

- a dictionary is a section, e.g. `logging` or `editorTheme`
- a string, a number, a boolean or a list is written as value of the option, lists replace the former value
- `null` removes the option, Node-RED uses its default then

`settings.js` is JavaScript, booleans are values of the options (e.g. `flowFilePretty: false`), so `false` does not remove an option like in the roles writing `key=value` files.
The role writes the options as JSON into `settings.js`, options that need JavaScript (functions or `require`) cannot be set.

```yaml
nodered_config:
  lang: 'de'
  logging:
    console:
      level: 'warn'
  editorTheme:
    projects:
      enabled: true
  httpNodeAuth:
    user: 'flows'
    pass: '$2b$10$...'
```

`httpNodeAuth` and `httpStaticAuth` need a bcrypt hash as `pass`, e.g. created with `node-red admin hash-pw`.
`settings.js` is readable by the user of Node-RED only (0600), `nodered_home` is 0700.

### Users

`nodered_users` sets the users of the editor and the admin API (`adminAuth`), every user has a `name` and `permissions`, `*` (the default) or `read`.
The passwords are set with `nodered_passwords`, at least 8 characters. Without users the editor is not protected, like Node-RED without `adminAuth`.

```yaml
nodered_users:
  - name: 'admin'
  - name: 'viewer'
    permissions: 'read'
nodered_passwords:
  admin: "{{ vault_nodered_admin_password }}"
  viewer: "{{ vault_nodered_viewer_password }}"
```

Node-RED reads the passwords as bcrypt hashes, the role creates them with its module `app_nodered_users` (`library/`), the passwords are an option with `no_log`.
The salt is derived from the name and the password, so the hash and `settings.js` only change with them and Node-RED only restarts after a change.
The host of the role needs `python3-bcrypt`, the role installs it if users are set.

### Secrets

`nodered_secrets` is a list with `name`, `data` and `target`, the only target is `credentialSecret`, the key Node-RED encrypts the credentials of the flows with.

```yaml
nodered_secrets:
  - name: 'nodered_credential_secret'
    data: "{{ vault_nodered_credential_secret }}"
    target: 'credentialSecret'
```

Node-RED reads the secrets only from `settings.js`, it reads no variables of the environment or files for them.
The role creates a podman secret, mounts it to `/run/secrets/<name>` and `settings.js` reads the file on start,
so the key is neither part of the quadlet unit, nor of the environment of the container, nor of `settings.js`.
Without `credentialSecret` Node-RED creates a key in `<nodered_home>/.config.runtime.json`, the credentials can only be read with this key.

### Allowed variables

The role only allows the options of `app_nodered__config_allowed` in `nodered_config`, the variables of `app_nodered__environment_allowed`
and the secret `credentialSecret`, it stops before any change if unknown options, variables or secrets are set.
This prevents unexpected behavior by accident, e.g. by a typo, an option Node-RED does not know or a password in the environment.

The options are generated from the options of the first level of `settings.js` of Node-RED 5.0.9, the active and the commented ones.
`userDir`, `credentialSecret` and `adminAuth` are set by the role, `https`, `httpsRefreshInterval`, `httpAdminMiddleware`, `httpNodeMiddleware`
and `webSocketNodeVerifyClient` need JavaScript and are not allowed. TLS is done by a reverse proxy.
The booleans of the first level (`app_nodered__config_booleans`) only allow `true` and `false`.

The variables are generated from `process.env` of Node-RED 5.0.9 and the Dockerfile and `entrypoint.sh` of node-red-docker v5.0.9.
`PORT` is not allowed, `uiPort` is set in `settings.js`, `NODE_RED_DISABLE_TELEMETRY` is not allowed, Node-RED disables the telemetry with any value,
`telemetry.enabled` is set in `nodered_config`. `NODE_RED_ENABLE_PROJECTS`, `NODE_RED_ENABLE_SAFE_MODE` and `NODE_RED_ENABLE_TOURS` are booleans.
New versions of Node-RED may add options and variables, the lists are generated again.
The check uses the container after merging `nodered_container`, so variables set with `nodered_container.environment` are checked as well.

### Container

Ports, volumes, additional hosts (`etc_hosts`) and dependencies (`requires`) are changed with `nodered_container`, it is merged over the default of the container.
The merge is not recursive, `nodered_container.volumes` replaces `/data`, `nodered_container.environment` replaces the environment including `nodered_environment`.
The role waits until Node-RED answers on `uiPort`, it shows the log of the service otherwise.

### Validation

The role checks before any change:

- `nodered_secrets` is a list of entries with `name`, `data` and `target` with unique names and targets
- the options of `nodered_config` are known and not set by the role, the booleans are `true` or `false`, values have no line breaks
- `nodered_users` is a list with valid and unique names and the permissions `*` or `read`, every user has a password with at least 8 characters,
  `nodered_passwords` has no passwords of unknown users
- the booleans of the environment are `true` or `false`, values have no line breaks, `credentialSecret` is not set in `nodered_environment`
- only allowed environment variables and secrets are set in the container

If `nodered_container` or `nodered_config` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Restart and updates

Node-RED reads `settings.js` and the secrets only on start, it is restarted if it was running and a secret, `settings.js` or the quadlet unit changed,
otherwise it is started and enabled. A changed password changes the hash in `settings.js` and restarts Node-RED.
Updates of the image are done by `container_update` with `nodered_autoupdate_enabled: true` and `nodered_autoupdate_schedule`,
without `nodered_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

- `settings.js` was created by Node-RED and changed by hand, the role writes it now. Move the options of an existing `settings.js` to `nodered_config`,
  the users of `adminAuth` to `nodered_users` and `nodered_passwords`.
- If `credentialSecret` was set in the former `settings.js`, set the same value as secret, otherwise the credentials cannot be read.
  Without the secret the key of `<nodered_home>/.config.runtime.json` stays valid, if the secret is set later it has to be this key.
- `nodered_container.exec_start_pre` is removed.
- `nodered_ip`, `nodered_ipv6`, `nodered_network`, `nodered_hostname`, `nodered_timezone`, `nodered_home`, `nodered_labels`, `nodered_version`
  and `nodered_autoupdate_enabled` stay, `nodered_environment`, `nodered_config`, `nodered_secrets`, `nodered_users`, `nodered_passwords`
  and `nodered_autoupdate_schedule` are new.
- `nodered_container` was merged, it still is, the environment is checked against the allowed variables now.
- The volumes `/etc/localtime` and `/etc/timezone` are removed, the timezone is set by podman and `TZ`.
- The service is not stopped on every run anymore, `podman___update_mode` is removed.
- The tag `app_nodered` stays, the tag `app` is added.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-nodered-default` | Only the mandatory variables, without users, the editor is not protected |
| `molecule-nodered` | IPv6, labels, options of `settings.js`, the secret `credentialSecret`, an administrator and a user with read permissions |

`prepare` creates the podman network and pulls the image.
`side_effect` runs the role with `nodered_container` not a dictionary, a secret without `target`, an unknown secret, an unknown option, `adminAuth` in `nodered_config`,
an invalid boolean, a line break in a value, a user without password, a short password, invalid permissions and an unknown environment variable
and checks that it fails with the expected message and the quadlet unit and `settings.js` are unchanged (tasks marked `expect ERROR`),
then it changes the password of the administrator on `molecule-nodered`, `settings.js` changes and Node-RED has to restart.
`verify` checks the quadlet unit with the secret as file, mode and owner of `settings.js` without passwords and without the credential secret,
the service, the addresses and the environment of the container, the flows without login on `molecule-nodered-default`,
and on `molecule-nodered` the refused flows without login, the login with the changed and the refused former password,
the refused deployment of the user with read permissions, the options in the settings of the admin API
and that Node-RED did not create its own credential secret.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd app_nodered
MOLECULE_TART_IMAGE='debian' molecule test
```
