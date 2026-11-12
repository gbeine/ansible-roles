HedgeDoc runs in the container image of [linuxserver.io](https://docs.linuxserver.io/images/docker-hedgedoc/) as podman quadlet and is configured with environment variables.
See the [configuration of HedgeDoc](https://docs.hedgedoc.org/configuration/) for all `CMD_*` variables.
`hedgedoc_home` is mounted to `/config`, it contains `config.json`, the uploads and the sqlite database.
The image runs HedgeDoc as the user `abc` with the uid and gid of `hedgedoc_uid` and `hedgedoc_gid` (defaults to `hedgedoc_uid`), HedgeDoc listens on port 3000.

### Configuration

All variables are set with `hedgedoc_environment`, which is merged over the defaults of the role (`PUID`, `PGID` and `TZ`).
`CMD_DOMAIN` is mandatory. Booleans may be written as YAML booleans, the role passes them as `true` and `false`.

```yaml
hedgedoc_environment:
  CMD_DOMAIN: 'pad.example.org'
  CMD_PROTOCOL_USESSL: true
  CMD_ALLOW_ANONYMOUS: false
  CMD_OAUTH2_PROVIDERNAME: 'SSO'
  CMD_OAUTH2_CLIENT_ID: 'hedgedoc'
  CMD_OAUTH2_AUTHORIZATION_URL: 'https://sso.example.org/authorize'
  CMD_OAUTH2_TOKEN_URL: 'https://sso.example.org/token'
  CMD_OAUTH2_USER_PROFILE_URL: 'https://sso.example.org/userinfo'
```

Without `DB_HOST` HedgeDoc uses sqlite in `<hedgedoc_home>/hedgedoc.sqlite`.
With `DB_HOST` the image builds the URL of the database from `CMD_DB_DIALECT`, `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_NAME` and the secret `DB_PASS`,
all of them are mandatory then and `CMD_DB_DIALECT` is `postgres`, `mariadb` or `mysql`.
The image puts `DB_PASS` into the URL without encoding, so it may only contain letters, digits and `. _ ~ -`.

```yaml
hedgedoc_environment:
  CMD_DOMAIN: 'pad.example.org'
  CMD_DB_DIALECT: 'postgres'
  DB_HOST: 'postgres'
  DB_PORT: 5432
  DB_USER: 'hedgedoc'
  DB_NAME: 'hedgedoc'
```

The role manages no users, users log in with OAuth2, LDAP, SAML or another provider, or register themselves with `CMD_ALLOW_EMAIL_REGISTER`.

### Secrets

Variables carrying secrets are passed as podman secrets with `hedgedoc_secrets` and must not be set in `hedgedoc_environment`.
Every secret has a `name`, the `data` and the `target`, the usual name of the variable, e.g. `DB_PASS`.
The role creates the secret with `podman secret create`, mounts it to `/run/secrets/<name>` and sets `FILE__<target>`,
the linuxserver image reads the variable from this file at the start, so the secret is neither part of the quadlet unit nor of the environment of the container.

```yaml
hedgedoc_secrets:
  - name: 'hedgedoc_session_secret'
    data: "{{ vault_hedgedoc_session_secret }}"
    target: 'CMD_SESSION_SECRET'
  - name: 'hedgedoc_db_pass'
    data: "{{ vault_hedgedoc_db_pass }}"
    target: 'DB_PASS'
```

`CMD_SESSION_SECRET` is mandatory, HedgeDoc creates a random one otherwise and all sessions end with a restart.
Allowed targets are `CMD_SESSION_SECRET`, `DB_PASS`, `CMD_DB_URL`, `CMD_DB_PASSWORD`, `CMD_S3_SECRET_ACCESS_KEY`, `CMD_MINIO_SECRET_KEY`,
`CMD_AZURE_CONNECTION_STRING`, the `CMD_*_CLIENTSECRET` of Facebook, GitHub, GitLab, Mattermost, Dropbox and Google,
`CMD_TWITTER_CONSUMERSECRET`, `CMD_OAUTH2_CLIENT_SECRET` and `CMD_LDAP_BINDCREDENTIALS`.

### Allowed variables

The role only allows the environment variables in `app_hedgedoc__environment_allowed` and the secrets above,
it stops before any change if unknown variables or secrets are set.
This prevents unexpected behavior by accident, e.g. by a typo or a variable that has to be passed as secret.
The allowed variables are `PUID`, `PGID`, `TZ` and `UMASK` of the linuxserver image, `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_NAME` and `CMD_CONFIG_FILE`
of the image, the `CMD_*` variables of HedgeDoc, generated from `lib/config/environment.js` of HedgeDoc 1.12.0 without the secrets,
and the file variables of the secrets (`FILE__<target>`). New versions of HedgeDoc may add variables, the list in `defaults/main.yml` is generated again.
The check uses the environment and the secrets of the container after merging `hedgedoc_container`,
so variables set with `hedgedoc_container.environment` are checked as well.

### Container

Ports, volumes, additional hosts (`etc_hosts`) and dependencies (`requires`) are changed with `hedgedoc_container`, it is merged over the default of the container.
The merge is not recursive, `hedgedoc_container.volumes` replaces `/config`, `hedgedoc_container.environment` replaces the environment including `hedgedoc_environment`.
The role waits until `/status` of HedgeDoc answers, HedgeDoc migrates the database on the first start, it shows the log of the service otherwise.

### Validation

The role checks before any change:

- `hedgedoc_secrets` is a list of entries with `name`, `data` and `target` with unique names
- `CMD_DOMAIN` and the secret `CMD_SESSION_SECRET` are set, `DB_HOST` has the other variables of the database and the secret `DB_PASS`
  with the allowed characters, `CMD_DB_DIALECT` has an allowed value
- neither a secret nor its file variable is set in `hedgedoc_environment`
- the booleans of HedgeDoc are `true` or `false`, values have no line breaks
- only allowed environment variables and secrets are set in the container

If `hedgedoc_container` is no dictionary, merging it with the default fails before anything changes.

### Restart and updates

HedgeDoc is restarted if it was running and a secret or the quadlet unit changed, e.g. after changing `hedgedoc_environment`, otherwise it is started and enabled.
Updates of the image are done by `container_update` with `hedgedoc_autoupdate_enabled: true` and `hedgedoc_autoupdate_schedule`,
without `hedgedoc_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

The single variables are replaced by `hedgedoc_environment` and `hedgedoc_secrets`:

| Former variable | Now |
|---|---|
| `hedgedoc_db_host`, `hedgedoc_db_port`, `hedgedoc_db_user`, `hedgedoc_db_name` | `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_NAME` |
| `hedgedoc_db_dialect` | `CMD_DB_DIALECT`, set `postgres` explicitly, the image uses `mariadb` otherwise |
| `hedgedoc_db_pass` | secret `DB_PASS` |
| `hedgedoc_session_secret` | secret `CMD_SESSION_SECRET` |
| `hedgedoc_oauth2_client_secret` | secret `CMD_OAUTH2_CLIENT_SECRET` |
| `hedgedoc_domain`, `hedgedoc_port`, `hedgedoc_protocol_usessl`, `hedgedoc_url_addport`, `hedgedoc_allow_origin` | `CMD_DOMAIN`, `CMD_PORT`, `CMD_PROTOCOL_USESSL`, `CMD_URL_ADDPORT`, `CMD_ALLOW_ORIGIN` |
| `hedgedoc_hsts_*`, `hedgedoc_csp_*` | `CMD_HSTS_*`, `CMD_CSP_*`, `hedgedoc_csp_report_uri` is `CMD_CSP_REPORTURI` |
| `hedgedoc_cookie_policy`, `hedgedoc_rate_limit_new_notes`, `hedgedoc_session_life` | `CMD_COOKIE_POLICY`, `CMD_RATE_LIMIT_NEW_NOTES`, `CMD_SESSION_LIFE` |
| `hedgedoc_allow_gravatar`, `hedgedoc_allow_anonymous`, `hedgedoc_allow_anonymous_edits` | `CMD_ALLOW_GRAVATAR`, `CMD_ALLOW_ANONYMOUS`, `CMD_ALLOW_ANONYMOUS_EDITS` |
| `hedgedoc_allow_free_url`, `hedgedoc_require_free_url_authentication` | `CMD_ALLOW_FREEURL`, `CMD_REQUIRE_FREEURL_AUTHENTICATION` |
| `hedgedoc_disable_note_creation`, `hedgedoc_default_permission`, `hedgedoc_enable_uploads` | `CMD_DISABLE_NOTE_CREATION`, `CMD_DEFAULT_PERMISSION`, `CMD_ENABLE_UPLOADS` |
| `hedgedoc_email`, `hedgedoc_allow_email_register` | `CMD_EMAIL`, `CMD_ALLOW_EMAIL_REGISTER` |
| `hedgedoc_oauth2_*` | `CMD_OAUTH2_*`, e.g. `hedgedoc_oauth2_user_profile_url` is `CMD_OAUTH2_USER_PROFILE_URL` |
| `hedgedoc_labels`, `hedgedoc_version`, `hedgedoc_uid`, `hedgedoc_gid`, `hedgedoc_autoupdate_enabled` | stay |

- The former role set many variables with defaults (e.g. `CMD_ALLOW_GRAVATAR: true`, `CMD_HSTS_MAX_AGE: 31536000`), the role sets none of them now,
  HedgeDoc uses its own defaults. Set the variables that differ from the defaults of HedgeDoc.
- OAuth2 was mandatory, it is optional now. The secret of OAuth2 was only created together with all other secrets if `hedgedoc_oauth2_user_profile_url` was defined,
  the condition applied to the whole list of secrets, this is fixed.
- The secrets were passed as `type=env`, they are mounted as files now, the podman secrets `hedgedoc_db_pass`, `hedgedoc_session_secret` and
  `hedgedoc_oauth2_client_secret` keep their names in the examples above.
- The role created `<hedgedoc_home>/uploads`, the image creates and links it itself.
- The volumes `/etc/localtime` and `/etc/timezone` are removed, the timezone is set by podman and `TZ`.
- The service is not stopped on every run anymore, `podman___update_mode` is removed.
- The tag `app_hedgedoc` stays, the tag `app` is added.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-hedgedoc-default` | Only the mandatory variables, sqlite |
| `molecule-hedgedoc` | IPv6, labels, PostgreSQL with the secret `DB_PASS`, no anonymous notes, OAuth2 with the secret `CMD_OAUTH2_CLIENT_SECRET` |

`prepare` creates the podman network, pulls the image and starts PostgreSQL on `molecule-hedgedoc`.
`side_effect` runs the role with `hedgedoc_container` not a dictionary, a secret without `target`, without the session secret,
the session secret in the environment, without `CMD_DOMAIN`, `DB_HOST` without `DB_PASS` and without `CMD_DB_DIALECT`, an invalid boolean,
a line break in a value, an unknown environment variable and an unknown secret
and checks that it fails with the expected message and the quadlet unit is unchanged (tasks marked `expect ERROR`),
then it changes `CMD_ALLOW_GRAVATAR` on `molecule-hedgedoc`, the quadlet unit changes and HedgeDoc has to restart.
`verify` checks the quadlet unit with the secrets as files, the service, the addresses and the environment of the container, `/status`,
a note created without login and readable on `molecule-hedgedoc-default`, the refused note without login and the login with OAuth2 on `molecule-hedgedoc`
and the tables of HedgeDoc in PostgreSQL.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd app_hedgedoc
MOLECULE_TART_IMAGE='debian' molecule test
```
