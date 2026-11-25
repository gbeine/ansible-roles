Pocket ID runs in the container image [ghcr.io/pocket-id/pocket-id](https://github.com/pocket-id/pocket-id/pkgs/container/pocket-id) (`latest` by default) as podman quadlet `pocket-id`.
Pocket ID is an OIDC provider, the users log in with passkeys. The role creates the first admin once and manages groups, users and OIDC clients
with the API of Pocket ID (module `security_pocketid_api`).

### Configuration

```yaml
pocketid_home: '/srv/container/pocket-id'
pocketid_ip: '192.168.99.80'
pocketid_network: 'podman99'
pocketid_hostname: 'pocket-id'
pocketid_timezone: 'Europe/Berlin'
pocketid_environment:
  APP_URL: 'https://id.example.org'
  TRUST_PROXY: true
pocketid_secrets:
  - name: 'pocketid_encryption_key'
    data: "{{ vault_pocketid_encryption_key }}"
    target: 'ENCRYPTION_KEY'
  - name: 'pocketid_static_api_key'
    data: "{{ vault_pocketid_static_api_key }}"
    target: 'STATIC_API_KEY'
pocketid_admin:
  username: 'admin'
  email: 'admin@example.org'
```

Pocket ID reads its configuration only from the environment (`backend/internal/common/env_config.go` of Pocket ID v2.19.3),
it has no configuration file, the `.env` it would read in `/app` is not part of the image. `pocketid_environment` is merged over the default of the role,
`ANALYTICS_DISABLED` and `VERSION_CHECK_DISABLED` are `true`, the image is updated by `container_update`.
`APP_URL` is mandatory, it is the public URL of Pocket ID without a path and the issuer of the tokens.
Booleans may be given as YAML booleans, the role passes them as `true` or `false`, `null` removes a variable of the default.
The variables are described in the [documentation of Pocket ID](https://pocket-id.org/docs/configuration/environment-variables).

The settings of the application (name, SMTP, LDAP, passkeys, …) are stored in the database and changed in the web interface.
With `UI_CONFIG_DISABLED: true` Pocket ID reads them from the environment instead, e.g. `APP_NAME`, `SMTP_HOST` or `LDAP_URL`,
the passwords `SMTP_PASSWORD` and `LDAP_BIND_PASSWORD` are secrets.

The data, the SQLite database `pocket-id.db` and the uploads, are kept in `<pocketid_home>/data`, mounted to `/app/data`.
The entrypoint of the image runs Pocket ID as `PUID`/`PGID` (1000) and changes the owner of `/app/data`, the role creates the directory for this user.
PostgreSQL is used with the secret `DB_CONNECTION_STRING` (`postgres://user:password@host:5432/database`).

### Secrets

`pocketid_secrets` is a list of podman secrets with `name`, `data` and `target`, the target is the variable of Pocket ID.
Pocket ID reads them from the file of `<target>_FILE` (`options:"file"` in `env_config.go` and `sensitive:"true"` in `appconfig/model.go`),
the role mounts every secret as `/run/secrets/<name>` (owner 1000, mode `0400`) and sets the file variable, the values are not part of the environment.

| Target | Description |
|---|---|
| `ENCRYPTION_KEY` | Mandatory, encrypts the data of Pocket ID, at least 16 characters, e.g. `openssl rand -base64 32` |
| `STATIC_API_KEY` | Mandatory, the API key of the role, at least 16 characters |
| `DB_CONNECTION_STRING` | The connection to PostgreSQL with its password |
| `SMTP_PASSWORD` | The password of the SMTP server, with `UI_CONFIG_DISABLED` |
| `LDAP_BIND_PASSWORD` | The password of the LDAP bind DN, with `UI_CONFIG_DISABLED` |
| `S3_SECRET_ACCESS_KEY` | The key of S3 with `FILE_BACKEND: s3` |
| `MAXMIND_LICENSE_KEY` | The license of the GeoLite database |

Secrets are strings without line breaks, Pocket ID reads `ENCRYPTION_KEY` from its file without removing a line break.
A changed `ENCRYPTION_KEY` makes the encrypted data unreadable.
`STATIC_API_KEY` grants the rights of an admin to everybody who knows it, the role needs it to manage the admin, the groups, the users and the clients.
No target and no file variable may be set in `pocketid_environment`.

### TLS

`pocketid_tls` sets the certificate of a realm deployed on the host by `pki_easyrsa_deploy` or `pki_certbot`, Pocket ID serves HTTPS on port 1411 then:

```yaml
pocketid_tls:
  realm: 'id.example.org'
  # optional, the realms of common_globals by default, e.g. /opt/certbot/etc/live for pki_certbot
  dir: '/opt/certbot/etc/live'
```

`ExecStartPre` of the quadlet unit copies `fullchain.pem` (`0644`) and `privkey.pem` (`0600`) of `<dir>/<realm>` with `install` to `<pocketid_home>/tls`
(`0700`) at every start, owned by the user of Pocket ID (1000), `install` follows the links of the realm.
The directory is mounted read-only to `/app/tls`, the role sets `TLS_CERT_FILE` and `TLS_KEY_FILE`, they must not be set in `pocketid_environment`.
The files of the realm have to exist before the role runs, in check mode missing files are only reported.
The copies only change at a start, the timer of `pki_update` (`pki-update@pocket-id.timer`) checks the certificate and the key of the realm
and restarts Pocket ID if they are newer than the start, `pocketid_pki_update_enabled` (`true`) and `pocketid_pki_update_schedule` (`*-*-* 00/4:00:00`) control it.
Without `pocketid_tls` Pocket ID serves HTTP for a reverse proxy, e.g. Traefik with `pocketid_labels`, set `TRUST_PROXY` then.

### Admin

Until the first user exists, everybody who reaches `/setup` may create the first admin of Pocket ID.
The role creates `pocketid_admin` after the first start through the API, the setup is closed then. Between the start and the creation
Pocket ID is reachable for a few seconds, start it without labels of a reverse proxy if this matters.
`pocketid_admin` takes `username`, `email` and optionally `first_name`, `last_name`, `display_name` and `locale`.
The admin is created once, an existing admin keeps its values and is only made an admin again.

The admin has no passkey yet, the login link of the admin is created on the host, it is valid for one hour:

```shell
podman exec --user 1000:1000 pocket-id /app/pocket-id one-time-access-token admin
```

The role never shows a login link.

### Groups, users and clients

The role manages the listed entries through the API, entries with `state: absent` are removed,
other entries, e.g. created in the web interface or by LDAP, are not touched. Only the listed values are compared and changed.

```yaml
pocketid_groups:
  - name: 'grafana-admins'
    friendly_name: 'Grafana Admins'
pocketid_users:
  - username: 'jane'
    email: 'jane@example.org'
    first_name: 'Jane'
    last_name: 'Doe'
    groups: [ 'grafana-admins' ]
pocketid_clients:
  - id: 'grafana'
    name: 'Grafana'
    callback_urls: [ 'https://grafana.example.org/login/generic_oauth' ]
    groups: [ 'grafana-admins' ]
    secret: "{{ vault_pocketid_grafana_secret }}"
  - id: 'spa'
    name: 'Single page application'
    callback_urls: [ 'https://app.example.org/callback' ]
    public: true
    pkce: true
```

- Groups take `name`, `friendly_name` (the name by default) and `state`.
- Users take `username`, `email` (see below), `first_name`, `last_name`, `display_name`, `locale`, `admin`, `disabled`, `groups` (the names of groups of `pocketid_groups`) and `state`.
- Clients take `id` (the client ID), `name`, `description`, `callback_urls`, `logout_callback_urls`, `launch_url`, `public`, `pkce`, `skip_consent`,
  `requires_reauthentication`, `groups` (the allowed groups, the client is restricted to them if the list is not empty), `secret` and `state`.

Pocket ID requires an email for every user as long as `REQUIRE_USER_EMAIL` is true, the default. The role only knows the setting
from the environment, i.e. with `UI_CONFIG_DISABLED: true` and `REQUIRE_USER_EMAIL: false` the admin and the users may omit `email`.
If the setting was changed in the UI, the role still requires an email.

Pocket ID only keeps a hash of the secret of a client. The role checks the secret with the introspection of Pocket ID (HTTP Basic, `200` for the right secret, `401` for an unknown one, other answers stop the role),
an unknown secret is created and replaces the former secrets of the client. Secrets have at least 16 printable ASCII characters.
The users log in with passkeys, the role sets no passwords.

### Allowed variables

The role only allows the variables in `security_pocketid__environment_allowed` and the secrets listed above,
it stops before any change if unknown variables or secrets are set.
This prevents unexpected behavior by accident, e.g. by a typo or a password that has to be passed as secret.
The list is generated from `env_config.go` and `appconfig/model.go` of Pocket ID v2.19.3 and `PUID` and `PGID` of `scripts/docker/entrypoint.sh`,
without the secrets, `APP_ENV` (set by the image), `PORT`, `HOST`, `UNIX_SOCKET`, `UNIX_SOCKET_MODE` and `SYSTEMD_SOCKET` (the role uses port 1411),
`TLS_CERT`, `TLS_KEY`, `TLS_CERT_FILE` and `TLS_KEY_FILE` (set with `pocketid_tls`), the experimental `EXPERIMENTAL_*` and the former
`EMAIL_LOGIN_NOTIFICATION_ENABLED` and `EMAIL_VERIFICATION_ENABLED`, new versions of the image may add variables.
The check uses the environment of the container after merging `pocketid_container`.

### Container

Ports, volumes, additional hosts (`etc_hosts`) and the dependencies are changed with `pocketid_container`, it is merged over the default of the container.
The dependencies of the quadlet unit are lists: `requires`, `wants`, `after`, `part_of` and `binds_to` are units,
`requires_mounts_for` are paths. They are written to `[Unit]` as `Requires=`, `Wants=`, `After=`, `PartOf=`, `BindsTo=` and `RequiresMountsFor=`.
The merge is not recursive, `pocketid_container.environment` replaces the environment including `pocketid_environment` and the file variables,
`pocketid_container.volumes` replaces the data and the certificate, `pocketid_container.secrets` the secrets.
The container publishes no ports by default, a reverse proxy uses the address of the container.

```yaml
pocketid_container:
  wants: [ 'postgresql.service' ]
  after: [ 'postgresql.service' ]
```

### Validation

The role checks before any change:

- `pocketid_secrets` is a list of entries with `name`, `data` and `target` and unique names, every target is known and set once,
  `ENCRYPTION_KEY` and `STATIC_API_KEY` are set with at least 16 characters, no secret contains a line break or is empty
- `APP_URL` is set and an http or https URL without a path
- no secret, no file variable and no variable of the role is set in `pocketid_environment`
- the values are strings, numbers or booleans without line breaks, the booleans of Pocket ID are `true` or `false`
- `pocketid_admin` has a valid username and known keys
- the admin and every present user have an email, unless `UI_CONFIG_DISABLED` and `REQUIRE_USER_EMAIL: false` are set in `pocketid_environment`
- `pocketid_groups`, `pocketid_users` and `pocketid_clients` are lists of dictionaries with known keys, valid and unique names, usernames and client IDs,
  booleans, lists, `state` `present` or `absent`, groups of users and clients are present in `pocketid_groups`, secrets of clients have at least 16 printable ASCII characters
- only allowed environment variables without line breaks and allowed secrets are set in the container
- `pocketid_tls` is a dictionary with a valid realm and an absolute `dir`, the files of the realm exist
- `pocketid_home` is an absolute path

If `pocketid_container` or `pocketid_environment` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Check mode

The role runs with `--check`, also on a host where it never ran, and reports the directories, the secrets, the quadlet unit and the timer of `pki_update`.
The start, the wait for Pocket ID and the API do not run in check mode.

### Restart and updates

Pocket ID is restarted if it was running and a secret or the quadlet unit changed, e.g. after changing `pocketid_environment`,
otherwise it is started and enabled. Changes of the admin, the groups, the users and the clients need no restart.
If the start fails, the role shows the journal of the service. Afterwards the role waits up to 120 seconds for `/healthz` and shows the journal otherwise.
A renewed certificate restarts Pocket ID by the timer of `pki_update` (see TLS).
Updates of the image are done by `container_update` with `pocketid_autoupdate_enabled: true` and `pocketid_autoupdate_schedule`,
without `pocketid_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

The role is new, there are no former variables.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root. The VMs need access to ghcr.io and docker.io.

| Platform | Test case |
|---|---|
| `molecule-pocketid-default` | Only the mandatory variables with SQLite, an admin with email |
| `molecule-pocketid` | PostgreSQL, IPv6, labels, `UI_CONFIG_DISABLED` with `APP_NAME` and the secret `SMTP_PASSWORD`, an admin with name and email, groups, a user, a confidential client with secret and allowed group, a public client with PKCE, absent entries, the certificate of a realm |

`prepare` creates the podman network, pulls the images and starts PostgreSQL on `molecule-pocketid`, it creates a CA and the certificate of the realm
with openssl on the controller and deploys the realm in the structure of `pki_easyrsa_deploy`.
`check` runs `converge` with `--check` on the new VMs.
`side_effect` runs the role with `pocketid_container` and `pocketid_environment` not a dictionary, `pocketid_secrets` not a list, a secret without target,
an unknown secret, without `ENCRYPTION_KEY` or `STATIC_API_KEY`, a short `ENCRYPTION_KEY`, `ENCRYPTION_KEY` in the environment, without `APP_URL`, `APP_URL` with a path,
an unknown variable, a boolean as string, a line break, an invalid username of the admin, an admin and a user without email, an unknown group of a user, a client with a short secret and an unknown key,
`pocketid_tls` not a dictionary, a realm without certificate and a relative home
and checks that it fails with the expected message and the quadlet unit is unchanged (tasks marked `expect ERROR`),
then it changes `APP_NAME` on `molecule-pocketid`, the quadlet unit changes and Pocket ID has to restart, `molecule-pocketid-default` runs again without a change
and must not restart, the API changes nothing on both.
`verify` checks the quadlet unit with the volumes, the mounted secrets without their values and `ExecStartPre`, the environment with the file variables,
the service without automatic restarts, the directories, the certificate with `openssl s_client` and the CA of the realm, `/healthz`,
the closed setup, the issuer of the discovery, the admin, the groups, the users and the clients through the API, the secret of the client
with the introspection (the right secret answers `200`, a wrong one `401`) and the login link of the admin by `one-time-access-token`.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd security_pocketid
MOLECULE_TART_IMAGE='debian' molecule test
```
