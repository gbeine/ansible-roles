zot runs in the container image `ghcr.io/project-zot/zot` (`latest` by default, `zot_version` sets the tag, e.g. `v2.1.23`) as podman quadlet.
The image is multi-arch, it is built from `distroless` without a shell and runs zot as root.
zot listens on port 5000, it serves the OCI distribution API, the web interface and the health checks `/livez`, `/readyz` and `/startupz`.
The configuration and the users are kept in `<zot_home>/etc`, mounted read-only as `/etc/zot`,
the images in `<zot_home>/data`, mounted as `/var/lib/registry`.

### Configuration

zot reads its configuration only from `config.json`, it reads no environment variables.
`zot_config` is merged recursively over the default of the role, lists are replaced.
The default sets `distSpecVersion`, enables `dedupe` and `gc` of the storage, the realm `zot`, the log level `info`
and the extensions `search` and `ui`, the web interface needs the search. The scans of CVEs are disabled.
The keys are described in the [configuration of zot](https://zotregistry.dev/latest/admin-guide/admin-configuration/).

```yaml
zot_config:
  http:
    externalUrl: 'https://registry.example.org'
    accessControl:
      adminPolicy:
        users: [ 'admin' ]
        actions: [ 'read', 'create', 'update', 'delete' ]
      metrics:
        users: [ 'admin' ]
      repositories:
        '**':
          policies:
            - users: [ 'ci' ]
              actions: [ 'read', 'create', 'update' ]
          anonymousPolicy: [ 'read' ]
  extensions:
    sync:
      enable: true
      registries:
        - urls: [ 'https://docker.io/library' ]
          onDemand: true
          content:
            - prefix: '**'
              destination: '/docker.io'
```

The role sets `http.address` (`0.0.0.0`), `http.port` (`5000`), `storage.rootDirectory` (`/var/lib/registry`),
`http.auth.htpasswd.path` (`/etc/zot/htpasswd`) with users in `zot_users` and the paths of the files of the secrets,
they must not be set in `zot_config`.

The login is mandatory: `zot_users` has users or `zot_config.http.auth` has `ldap`, `openid`, `bearer` or `mtls`.
Reading without login is allowed with `anonymousPolicy` of the repositories.
Without `accessControl` every user who logs in may read, push and delete.
With `accessControl` only the users in `accessControl.metrics.users` may read the metrics, `adminPolicy` does not include them.

### Users

`zot_users` is a dictionary of the users of htpasswd by their names, each user has a `password` of 8 to 72 characters, bcrypt only uses 72 bytes.
The names must not contain a colon, the rights of the users are set in `zot_config.http.accessControl`.

```yaml
zot_users:
  admin:
    password: "{{ vault_zot_admin_password }}"
  ci:
    password: "{{ vault_zot_ci_password }}"
```

The module `app_zot_htpasswd` writes `htpasswd` with all users of `zot_users`, users missing there are removed.
It keeps the bcrypt hash of a password if it matches the password and hashes new passwords with bcrypt (`$2y$`),
so the file only changes if a user or a password changes. The passwords are an option with `no_log`.
zot watches the file and reads it again when it changes, a changed user needs no restart.
The role installs `python3-bcrypt` for the module.

### Secrets

`zot_secrets` is a list of podman secrets with `name`, `data` and `target`. `data` is a string or a dictionary, a dictionary is written as JSON.

zot reads its secrets from files, the role mounts them as `/run/secrets/<name>.json` and sets their paths in the configuration.
zot reads these files with viper, which knows their format only by the extension. The key of TLS is PEM, it is mounted as `/run/secrets/<name>` without extension.

| Target | Key of the configuration | Content |
|---|---|---|
| `ZOT_LDAP_CREDENTIALS` | `http.auth.ldap.credentialsFile` | `bindDN`, `bindPassword` |
| `ZOT_SESSION_KEYS` | `http.auth.sessionKeysFile` | `hashKey`, `encryptKey` |
| `ZOT_SYNC_CREDENTIALS` | `extensions.sync.credentialsFile` | `{"<registry>": {"username": …, "password": …}}` |
| `ZOT_OPENID_GITHUB_CREDENTIALS`, `ZOT_OPENID_GOOGLE_CREDENTIALS`, `ZOT_OPENID_GITLAB_CREDENTIALS`, `ZOT_OPENID_OIDC_CREDENTIALS` | `http.auth.openid.providers.<provider>.credentialsFile` | `clientid`, `clientsecret` |
| `ZOT_TLS_KEY` | `http.tls.key` | The private key of the certificate |

The SDKs of the storage drivers S3 and Azure read their secrets only from the environment, so `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`
and `AZURE_CLIENT_SECRET` are passed with `type=env,target=<target>`.

Secrets must not be part of `zot_config`: `credentialsFile`, `sessionKeysFile`, `clientsecret`, `accesskey`, `secretkey` and `accountkey`
are rejected anywhere in `zot_config`, LDAP needs `ZOT_LDAP_CREDENTIALS` and every provider of OpenID its secret.

```yaml
zot_secrets:
  - name: 'zot_session_keys'
    data:
      hashKey: "{{ vault_zot_hash_key }}"
      encryptKey: "{{ vault_zot_encrypt_key }}"
    target: 'ZOT_SESSION_KEYS'
```

### Allowed variables

zot reads no environment variables, the role only allows `TZ` and the variables of the SDKs of S3 and Azure
(`AWS_ACCESS_KEY_ID`, `AWS_PROFILE`, `AWS_REGION`, `AZURE_CLIENT_CERTIFICATE_PATH`, `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`) in `zot_environment`
and the secrets listed above. This prevents unexpected behavior by accident, e.g. by a variable meant for another image.
The check uses the environment and the secrets of the container after merging `zot_container`.
The list is taken from `examples/README.md` of zot v2.1.23.
The keys of the configuration are checked by zot itself, see Validation.

### Container

Ports, volumes, additional hosts (`etc_hosts`) and dependencies (`requires`) are changed with `zot_container`, it is merged over the default of the container.
The merge is not recursive, `zot_container.volumes` replaces the configuration and the storage.
For a reverse proxy, e.g. Traefik, the labels are set with `zot_labels`, large images need long timeouts and no limit of the size of the body.
The directories belong to root with the mode `0750`, `config.json` and `htpasswd` with the mode `0600`.

### Validation

The role checks before any change:

- `zot_secrets` is a list of entries with `name`, `data` and `target` and unique names
- a login is configured, LDAP and OpenID have their secrets
- `zot_config` contains no key set by the role and no secret
- the environment contains no secret and no line breaks
- the users have valid names and passwords of 8 to 72 characters
- only allowed environment variables and secrets are set in the container
- `zot verify` accepts the configuration, zot rejects e.g. unknown keys (`… has invalid keys`)

For `zot verify` the role pulls the image and writes the configuration and the secrets to a temporary directory in `/run` (tmpfs, mode `0700`),
runs the image without network with `verify` and removes the directory afterwards, also if the verification failed.
If zot rejects the configuration, the role shows the last lines of zot.

If `zot_config` or `zot_container` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Restart and updates

zot is restarted if it was running and a secret, `config.json` or the quadlet unit changed, otherwise it is started and enabled.
zot only reloads parts of a changed configuration itself, so the role restarts it. Changed users need no restart.
If the start fails, the role shows the journal of the service.
Afterwards the role waits up to 120 seconds for `/readyz` and shows the journal if zot does not answer.
Updates of the image are done by `container_update` with `zot_autoupdate_enabled: true` and `zot_autoupdate_schedule`,
without `zot_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

The role is new, there are no former variables.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root. The VMs need access to `ghcr.io` and Docker Hub.

| Platform | Test case |
|---|---|
| `molecule-zot-default` | Only the mandatory variables and one user |
| `molecule-zot` | IPv6, labels, access control with a reader and anonymous reading of `public`, the keys of the sessions and the metrics |

`prepare` creates the podman network, installs `curl`, `skopeo` and `python3-bcrypt` and pulls the image.
`side_effect` runs the role with `zot_config` not a dictionary, a secret without `target`, without login, the port in `zot_config`,
a client secret in `zot_config`, LDAP without its secret, an unknown secret, an unknown variable, a colon in the name of a user,
a short password and an unknown key of zot rejected by `zot verify`
and checks that it fails with the expected message and the quadlet unit, `config.json` and `htpasswd` are unchanged (tasks marked `expect ERROR`),
then it changes the log level and the password of the reader on `molecule-zot`, `config.json` and `htpasswd` change and zot has to restart.
`verify` checks the quadlet unit with the secret, the service, the addresses, the environment, the files with their modes,
the bcrypt hashes of `htpasswd` matching the passwords, the values of the role in `config.json` without secrets,
the health check and the web interface, copies `busybox` into the registry with skopeo as administrator,
reads its tags as administrator (200), without login and with a wrong password (401) and the catalog.
On `molecule-zot` the reader reads the image with its password but not with its former one and must not push,
`public/busybox` is read without login, `molecule/busybox` not, and the metrics answer.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd app_zot
MOLECULE_TART_IMAGE='debian' molecule test
```
