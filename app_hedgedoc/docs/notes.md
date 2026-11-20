HedgeDoc runs in the container image of [linuxserver.io](https://docs.linuxserver.io/images/docker-hedgedoc/) as podman quadlet.
`hedgedoc_home` is mounted to `/config`, it contains `config.json`, the uploads and the sqlite database.
The image runs HedgeDoc as the user `abc` with the uid and gid of `hedgedoc_uid` and `hedgedoc_gid` (defaults to `hedgedoc_uid`),
HedgeDoc listens on port 3000 or `hedgedoc_config.port`.

### Configuration

`hedgedoc_config` is the section `production` of `<hedgedoc_home>/config.json`, the image sets `NODE_ENV=production` and `CMD_CONFIG_FILE=/config/config.json`.
The options are the options of the [configuration of HedgeDoc](https://docs.hedgedoc.org/configuration/) in camelCase as in `lib/config/default.js`,
nested options are dictionaries (e.g. `oauth2`, `csp`, `ldap`). `hedgedoc_config` is merged recursively over the default of the role, which is empty.
`domain` is mandatory. Booleans are YAML booleans, strings like `'true'` are rejected, HedgeDoc would read every string as true.
An option set to `null` on the first level is left out of `config.json`.

```yaml
hedgedoc_config:
  domain: 'pad.example.org'
  protocolUseSSL: true
  allowAnonymous: false
  oauth2:
    providerName: 'SSO'
    clientID: 'hedgedoc'
    authorizationURL: 'https://sso.example.org/authorize'
    tokenURL: 'https://sso.example.org/token'
    userProfileURL: 'https://sso.example.org/userinfo'
```

The role writes `config.json` (owner `hedgedoc_uid`, `0640`), the image only copies its own `config.json` if the file does not exist.
HedgeDoc reads `config.json` first and the `CMD_*` variables of the environment afterwards, the environment takes precedence.
The role sets no `CMD_*` variable except the file variables of the secrets and `CMD_DB_DIALECT`.

The database is set with the environment of the image, not with `config.json`:
the image sets `CMD_DB_URL` itself and overrides `db` and `dbURL` of `config.json`, so the role rejects them.
Without `DB_HOST` HedgeDoc uses sqlite in `<hedgedoc_home>/hedgedoc.sqlite`.
With `DB_HOST` the image builds the URL of the database from `CMD_DB_DIALECT`, `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_NAME` and the secret `DB_PASS`,
all of them are mandatory then and `CMD_DB_DIALECT` is `postgres`, `mariadb` or `mysql`.
The image puts `DB_PASS` into the URL without encoding, so it may only contain letters, digits and `. _ ~ -`.

```yaml
hedgedoc_environment:
  CMD_DB_DIALECT: 'postgres'
  DB_HOST: 'postgres'
  DB_PORT: '5432'
  DB_USER: 'hedgedoc'
  DB_NAME: 'hedgedoc'
```

`hedgedoc_environment` is merged over the default of the role (`PUID` and `PGID`), it only takes the variables of the image.
The role manages no users, users log in with OAuth2, LDAP, SAML or another provider, or register themselves with `allowEmailRegister`.

### Secrets

`config.json` cannot read files, HedgeDoc reads the secrets from its `CMD_*` variables and the linuxserver image reads every variable from the file in `FILE__<variable>`.
So the secrets are podman secrets mounted as files and passed with the file variables next to `config.json`, the environment takes precedence over `config.json`
(`lib/config/index.js` of HedgeDoc 1.12.0 merges the environment after the file).
Every secret has a `name`, the `data` and the `target`, the usual name of the variable, e.g. `DB_PASS`.
The role creates the secret with `podman secret create`, mounts it to `/run/secrets/<name>` and sets `FILE__<target>`,
the image reads the variable from this file at the start, so the secret is neither part of the quadlet unit, of the environment of the container nor of `config.json`.

```yaml
hedgedoc_secrets:
  - name: 'hedgedoc_session_secret'
    data: "{{ vault_hedgedoc_session_secret }}"
    target: 'CMD_SESSION_SECRET'
  - name: 'hedgedoc_db_pass'
    data: "{{ vault_hedgedoc_db_pass }}"
    target: 'DB_PASS'
  - name: 'hedgedoc_oauth2_client_secret'
    data: "{{ vault_hedgedoc_oauth2_client_secret }}"
    target: 'CMD_OAUTH2_CLIENT_SECRET'
```

`CMD_SESSION_SECRET` is mandatory, HedgeDoc creates a random one otherwise and all sessions end with a restart.
Allowed targets are `CMD_SESSION_SECRET`, `DB_PASS`, `CMD_DB_URL`, `CMD_DB_PASSWORD`, `CMD_S3_SECRET_ACCESS_KEY`, `CMD_MINIO_SECRET_KEY`,
`CMD_AZURE_CONNECTION_STRING`, the `CMD_*_CLIENTSECRET` of Facebook, GitHub, GitLab, Mattermost, Dropbox and Google,
`CMD_TWITTER_CONSUMERSECRET`, `CMD_OAUTH2_CLIENT_SECRET` and `CMD_LDAP_BINDCREDENTIALS`.
The options of these secrets (e.g. `sessionSecret`, `oauth2.clientSecret`, `ldap.bindCredentials`) must not be set in `hedgedoc_config`,
passwords are never written to `config.json`.

### Allowed variables

The role only allows the options of HedgeDoc in `hedgedoc_config`, the variables of the image in the environment and the secrets above,
it stops before any change if unknown names are set.
This prevents unexpected behavior by accident, e.g. by a typo or a password in `config.json` or the environment.

- The options (`app_hedgedoc__config_allowed`) are generated from `lib/config/default.js` and `lib/config/environment.js` of HedgeDoc 1.12.0,
  only the first level is checked, the content of nested options (e.g. `oauth2`, `csp`) is not. The booleans are the options read with `toBooleanConfig`.
- The environment (`app_hedgedoc__environment_allowed`) contains `PUID`, `PGID`, `TZ` and `UMASK` of the linuxserver image,
  `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_NAME` and `CMD_DB_DIALECT` of the database and the file variables of the secrets (`FILE__<target>`).
  The other `CMD_*` variables are options of HedgeDoc and set with `hedgedoc_config`.
- The check uses the environment and the secrets of the container after merging `hedgedoc_container`,
  so variables set with `hedgedoc_container.environment` are checked as well.

### Container

Ports, volumes, additional hosts (`etc_hosts`) and the dependencies are changed with `hedgedoc_container`, it is merged over the default of the container.
The dependencies of the quadlet unit are lists: `requires`, `wants`, `after`, `part_of` and `binds_to` are units,
`requires_mounts_for` are paths. They are written to `[Unit]` as `Requires=`, `Wants=`, `After=`, `PartOf=`, `BindsTo=` and `RequiresMountsFor=`.
The merge is not recursive, `hedgedoc_container.volumes` replaces `/config`, `hedgedoc_container.environment` replaces the environment including `hedgedoc_environment`
and the file variables of the secrets.

```yaml
hedgedoc_container:
  wants: [ 'network-online.target' ]
  after: [ 'network-online.target' ]
```

The role waits until `/status` of HedgeDoc answers, HedgeDoc migrates the database on the first start, it shows the log of the service otherwise.

### Validation

The role checks before any change:

- `hedgedoc_config` and `hedgedoc_container` are dictionaries
- `hedgedoc_secrets` is a list of entries with `name`, `data` and `target` with unique names and targets, the data contain no line breaks
- `hedgedoc_config` only contains options of HedgeDoc, `domain` is set, neither `db`, `dbURL` nor the options of the secrets are set,
  the booleans are `true` or `false` and the values contain no line breaks
- the secret `CMD_SESSION_SECRET` is set, `DB_HOST` has the other variables of the database and the secret `DB_PASS`
  with the allowed characters, `CMD_DB_DIALECT` has an allowed value
- neither a secret nor its file variable is set in `hedgedoc_environment`, the environment contains no YAML booleans
- only allowed environment variables and secrets are set in the container, their values contain no line breaks
- `hedgedoc_home` is an absolute path

### Check mode

The role runs with `--check`, also on a host where it never ran, and reports the home directory, `config.json`, the secrets and the quadlet unit.
The start and the wait for HedgeDoc do not run in check mode.

### Restart and updates

HedgeDoc reads `config.json` and the secrets only at the start.
It is restarted if it was running and `config.json`, a secret or the quadlet unit changed, otherwise it is started and enabled.
If the start fails, the role stops with the last lines of the journal.
Updates of the image are done by `container_update` with `hedgedoc_autoupdate_enabled: true` and `hedgedoc_autoupdate_schedule`,
without `hedgedoc_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

The options of HedgeDoc moved from the environment to `config.json`, the database and the secrets stay in the environment.
The `CMD_*` variables are unknown variables of `hedgedoc_environment` now, the role stops if one of them is set.

The single variables of the first version of the role:

| Former variable | Now |
|---|---|
| `hedgedoc_db_host`, `hedgedoc_db_port`, `hedgedoc_db_user`, `hedgedoc_db_name` | `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_NAME` in `hedgedoc_environment` |
| `hedgedoc_db_dialect` | `CMD_DB_DIALECT` in `hedgedoc_environment`, set `postgres` explicitly, the image uses `mariadb` otherwise |
| `hedgedoc_db_pass` | secret `DB_PASS` |
| `hedgedoc_session_secret` | secret `CMD_SESSION_SECRET` |
| `hedgedoc_oauth2_client_secret` | secret `CMD_OAUTH2_CLIENT_SECRET` |
| `hedgedoc_domain`, `hedgedoc_port`, `hedgedoc_protocol_usessl`, `hedgedoc_url_addport` | `domain`, `port`, `protocolUseSSL`, `urlAddPort` |
| `hedgedoc_allow_origin` | removed, HedgeDoc 1.12.0 has no such option |
| `hedgedoc_hsts_*` | `hsts`, e.g. `hsts.enable`, `hsts.maxAgeSeconds`, `hsts.includeSubdomains`, `hsts.preload` |
| `hedgedoc_csp_*` | `csp`, e.g. `csp.enable`, `csp.reportURI`, `csp.addDisqus` |
| `hedgedoc_cookie_policy`, `hedgedoc_rate_limit_new_notes`, `hedgedoc_session_life` | `cookiePolicy`, `rateLimitNewNotes`, `sessionLife` |
| `hedgedoc_allow_gravatar`, `hedgedoc_allow_anonymous`, `hedgedoc_allow_anonymous_edits` | `allowGravatar`, `allowAnonymous`, `allowAnonymousEdits` |
| `hedgedoc_allow_free_url`, `hedgedoc_require_free_url_authentication` | `allowFreeURL`, `requireFreeURLAuthentication` |
| `hedgedoc_disable_note_creation`, `hedgedoc_default_permission`, `hedgedoc_enable_uploads` | `disableNoteCreation`, `defaultPermission`, `enableUploads` |
| `hedgedoc_email`, `hedgedoc_allow_email_register` | `email`, `allowEmailRegister` |
| `hedgedoc_oauth2_*` | `oauth2`, see the table below, e.g. `hedgedoc_oauth2_user_profile_url` is `oauth2.userProfileURL` |
| `hedgedoc_labels`, `hedgedoc_version`, `hedgedoc_uid`, `hedgedoc_gid`, `hedgedoc_autoupdate_enabled` | stay |

The `CMD_*` variables of `hedgedoc_environment`, generated from `lib/config/environment.js` of HedgeDoc 1.12.0, map to these options of `hedgedoc_config`:

| Former variable | Now |
|---|---|
| `CMD_SOURCE_URL` | `sourceURL` |
| `CMD_DOMAIN` | `domain` |
| `CMD_URL_PATH` | `urlPath` |
| `CMD_HOST` | `host` |
| `CMD_PORT` | `port` |
| `CMD_PATH` | `path` |
| `CMD_LOGLEVEL` | `loglevel` |
| `CMD_URL_ADDPORT` | `urlAddPort` |
| `CMD_USESSL` | `useSSL` |
| `CMD_HSTS_ENABLE` | `hsts.enable` |
| `CMD_HSTS_MAX_AGE` | `hsts.maxAgeSeconds` |
| `CMD_HSTS_INCLUDE_SUBDOMAINS` | `hsts.includeSubdomains` |
| `CMD_HSTS_PRELOAD` | `hsts.preload` |
| `CMD_CSP_ENABLE` | `csp.enable` |
| `CMD_CSP_REPORTURI` | `csp.reportURI` |
| `CMD_CSP_ADD_DISQUS` | `csp.addDisqus` |
| `CMD_CSP_ADD_GOOGLE_ANALYTICS` | `csp.addGoogleAnalytics` |
| `CMD_CSP_ALLOW_FRAMING` | `csp.allowFraming` |
| `CMD_CSP_ALLOW_PDF_EMBED` | `csp.allowPDFEmbed` |
| `CMD_RATE_LIMIT_NEW_NOTES` | `rateLimitNewNotes` |
| `CMD_RATE_LIMIT_USER` | `rateLimitUser` |
| `CMD_RATE_LIMIT_USING_CLOUDFLARE` | `rateLimitUsingCloudflare` |
| `CMD_COOKIE_POLICY` | `cookiePolicy` |
| `CMD_PROTOCOL_USESSL` | `protocolUseSSL` |
| `CMD_ALLOW_ANONYMOUS` | `allowAnonymous` |
| `CMD_ALLOW_ANONYMOUS_EDITS` | `allowAnonymousEdits` |
| `CMD_ALLOW_FREEURL` | `allowFreeURL` |
| `CMD_REQUIRE_FREEURL_AUTHENTICATION` | `requireFreeURLAuthentication` |
| `CMD_DISABLE_NOTE_CREATION` | `disableNoteCreation` |
| `CMD_ENABLE_UPLOADS` | `enableUploads` |
| `CMD_FORBIDDEN_NOTE_IDS` | `forbiddenNoteIDs` |
| `CMD_DEFAULT_PERMISSION` | `defaultPermission` |
| `CMD_DB_URL` | stays a secret |
| `CMD_DB_USERNAME` | the database is set with `DB_*` in `hedgedoc_environment` |
| `CMD_DB_PASSWORD` | stays a secret |
| `CMD_DB_HOST` | the database is set with `DB_*` in `hedgedoc_environment` |
| `CMD_DB_PORT` | the database is set with `DB_*` in `hedgedoc_environment` |
| `CMD_DB_DATABASE` | the database is set with `DB_*` in `hedgedoc_environment` |
| `CMD_DB_DIALECT` | stays in `hedgedoc_environment` |
| `CMD_SESSION_SECRET` | stays a secret |
| `CMD_SESSION_LIFE` | `sessionLife` |
| `CMD_TOOBUSY_LAG` | `tooBusyLag` |
| `CMD_DOCUMENT_MAX_LENGTH` | `documentMaxLength` |
| `CMD_IMAGE_UPLOAD_TYPE` | `imageUploadType` |
| `CMD_IMGUR_CLIENTID` | `imgur.clientID` |
| `CMD_S3_ACCESS_KEY_ID` | `s3.accessKeyId` |
| `CMD_S3_SECRET_ACCESS_KEY` | stays a secret |
| `CMD_S3_REGION` | `s3.region` |
| `CMD_S3_ENDPOINT` | `s3.endpoint` |
| `CMD_S3_BUCKET` | `s3bucket` |
| `CMD_S3_FOLDER` | `s3folder` |
| `CMD_S3_PUBLIC_FILES` | `s3publicFiles` |
| `CMD_MINIO_ACCESS_KEY` | `minio.accessKey` |
| `CMD_MINIO_SECRET_KEY` | stays a secret |
| `CMD_MINIO_ENDPOINT` | `minio.endPoint` |
| `CMD_MINIO_SECURE` | `minio.secure` |
| `CMD_MINIO_PORT` | `minio.port` |
| `CMD_LUTIM_URL` | `lutim.url` |
| `CMD_AZURE_CONNECTION_STRING` | stays a secret |
| `CMD_AZURE_CONTAINER` | `azure.container` |
| `CMD_FACEBOOK_CLIENTID` | `facebook.clientID` |
| `CMD_FACEBOOK_CLIENTSECRET` | stays a secret |
| `CMD_TWITTER_CONSUMERKEY` | `twitter.consumerKey` |
| `CMD_TWITTER_CONSUMERSECRET` | stays a secret |
| `CMD_GITHUB_CLIENTID` | `github.clientID` |
| `CMD_GITHUB_CLIENTSECRET` | stays a secret |
| `CMD_GITLAB_BASEURL` | `gitlab.baseURL` |
| `CMD_GITLAB_CLIENTID` | `gitlab.clientID` |
| `CMD_GITLAB_CLIENTSECRET` | stays a secret |
| `CMD_GITLAB_SCOPE` | `gitlab.scope` |
| `CMD_MATTERMOST_BASEURL` | `mattermost.baseURL` |
| `CMD_MATTERMOST_CLIENTID` | `mattermost.clientID` |
| `CMD_MATTERMOST_CLIENTSECRET` | stays a secret |
| `CMD_OAUTH2_PROVIDERNAME` | `oauth2.providerName` |
| `CMD_OAUTH2_BASEURL` | `oauth2.baseURL` |
| `CMD_OAUTH2_USER_PROFILE_URL` | `oauth2.userProfileURL` |
| `CMD_OAUTH2_USER_PROFILE_ID_ATTR` | `oauth2.userProfileIdAttr` |
| `CMD_OAUTH2_USER_PROFILE_USERNAME_ATTR` | `oauth2.userProfileUsernameAttr` |
| `CMD_OAUTH2_USER_PROFILE_DISPLAY_NAME_ATTR` | `oauth2.userProfileDisplayNameAttr` |
| `CMD_OAUTH2_USER_PROFILE_EMAIL_ATTR` | `oauth2.userProfileEmailAttr` |
| `CMD_OAUTH2_TOKEN_URL` | `oauth2.tokenURL` |
| `CMD_OAUTH2_AUTHORIZATION_URL` | `oauth2.authorizationURL` |
| `CMD_OAUTH2_CLIENT_ID` | `oauth2.clientID` |
| `CMD_OAUTH2_CLIENT_SECRET` | stays a secret |
| `CMD_OAUTH2_SCOPE` | `oauth2.scope` |
| `CMD_OAUTH2_ROLES_CLAIM` | `oauth2.rolesClaim` |
| `CMD_OAUTH2_ACCESS_ROLE` | `oauth2.accessRole` |
| `CMD_OAUTH2_PKCE` | `oauth2.pkce` |
| `CMD_DROPBOX_CLIENTID` | `dropbox.clientID` |
| `CMD_DROPBOX_CLIENTSECRET` | stays a secret |
| `CMD_DROPBOX_APPKEY` | `dropbox.appKey` |
| `CMD_GOOGLE_CLIENTID` | `google.clientID` |
| `CMD_GOOGLE_CLIENTSECRET` | stays a secret |
| `CMD_GOOGLE_HOSTEDDOMAIN` | `google.hostedDomain` |
| `CMD_LDAP_PROVIDERNAME` | `ldap.providerName` |
| `CMD_LDAP_URL` | `ldap.url` |
| `CMD_LDAP_BINDDN` | `ldap.bindDn` |
| `CMD_LDAP_BINDCREDENTIALS` | stays a secret |
| `CMD_LDAP_SEARCHBASE` | `ldap.searchBase` |
| `CMD_LDAP_SEARCHFILTER` | `ldap.searchFilter` |
| `CMD_LDAP_SEARCHATTRIBUTES` | `ldap.searchAttributes` |
| `CMD_LDAP_USERNAMEFIELD` | `ldap.usernameField` |
| `CMD_LDAP_USERIDFIELD` | `ldap.useridField` |
| `CMD_LDAP_TLS_CA` | `ldap.tlsca` |
| `CMD_SAML_PROVIDERNAME` | `saml.providerName` |
| `CMD_SAML_IDPSSOURL` | `saml.idpSsoUrl` |
| `CMD_SAML_IDPCERT` | `saml.idpCert` |
| `CMD_SAML_CLIENTCERT` | `saml.clientCert` |
| `CMD_SAML_ISSUER` | `saml.issuer` |
| `CMD_SAML_IDENTIFIERFORMAT` | `saml.identifierFormat` |
| `CMD_SAML_DISABLEREQUESTEDAUTHNCONTEXT` | `saml.disableRequestedAuthnContext` |
| `CMD_SAML_WANT_ASSERTIONS_SIGNED` | `saml.wantAssertionsSigned` |
| `CMD_SAML_WANT_AUTHN_RESPONSE_SIGNED` | `saml.wantAuthnResponseSigned` |
| `CMD_SAML_GROUPATTRIBUTE` | `saml.groupAttribute` |
| `CMD_SAML_EXTERNALGROUPS` | `saml.externalGroups` |
| `CMD_SAML_REQUIREDGROUPS` | `saml.requiredGroups` |
| `CMD_SAML_ATTRIBUTE_ID` | `saml.attribute.id` |
| `CMD_SAML_ATTRIBUTE_USERNAME` | `saml.attribute.username` |
| `CMD_SAML_ATTRIBUTE_EMAIL` | `saml.attribute.email` |
| `CMD_EMAIL` | `email` |
| `CMD_ALLOW_EMAIL_REGISTER` | `allowEmailRegister` |
| `CMD_ALLOW_GRAVATAR` | `allowGravatar` |
| `CMD_OPENID` | `openID` |
| `CMD_LINKIFY_HEADER_STYLE` | `linkifyHeaderStyle` |
| `CMD_ENABLE_STATS_API` | `enableStatsApi` |
| `CMD_EXTERNAL_LINK_WARNING` | `externalLinkWarning` |
| `CMD_EXTERNAL_LINK_WHITELIST` | `externalLinkWhitelist` |

- `TZ` is no default of the environment anymore, the time zone is set by podman with `hedgedoc_timezone`.
- Booleans in the environment were written as `true` and `false`, booleans in `hedgedoc_config` are YAML booleans.
- Lists in the environment were separated by commas (e.g. `CMD_FORBIDDEN_NOTE_IDS`), they are YAML lists in `hedgedoc_config`.
- The former role set many variables with defaults (e.g. `CMD_ALLOW_GRAVATAR: true`, `CMD_HSTS_MAX_AGE: 31536000`), the role sets none of them now,
  HedgeDoc uses its own defaults. Set the options that differ from the defaults of HedgeDoc.
- OAuth2 was mandatory, it is optional now. The secret of OAuth2 was only created together with all other secrets if `hedgedoc_oauth2_user_profile_url` was defined,
  the condition applied to the whole list of secrets, this is fixed.
- The secrets were passed as `type=env`, they are mounted as files now, the podman secrets `hedgedoc_db_pass`, `hedgedoc_session_secret` and
  `hedgedoc_oauth2_client_secret` keep their names in the examples above.
- A `config.json` changed by hand is overwritten, the image copied its default only once.
- The role created `<hedgedoc_home>/uploads`, the image creates and links it itself.
- The volumes `/etc/localtime` and `/etc/timezone` are removed, the timezone is set by podman.
- The service is not stopped on every run anymore, `podman___update_mode` is removed.
- The tag `app_hedgedoc` stays, the tag `app` is added.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-hedgedoc-default` | Only the mandatory variables, sqlite |
| `molecule-hedgedoc` | IPv6, labels, `UMASK`, PostgreSQL with the secret `DB_PASS`, no anonymous notes, OAuth2 with the secret `CMD_OAUTH2_CLIENT_SECRET` |

`prepare` creates the podman network, pulls the image and starts PostgreSQL on `molecule-hedgedoc`.
`check` runs `converge` with `--check` on the new VMs.
`side_effect` runs the role with `hedgedoc_container` and `hedgedoc_config` not a dictionary, without `domain`, an unknown option, `dbURL` and secrets in `hedgedoc_config`,
invalid booleans, a line break in an option, `hedgedoc_secrets` not a list, a secret without `target`, without the session secret,
the session secret in the environment, `DB_HOST` without `DB_PASS` and without `CMD_DB_DIALECT`, a YAML boolean and a line break in the environment,
the former `CMD_DOMAIN` in the environment, an unknown secret and a relative home
and checks that it fails with the expected message and the quadlet unit and `config.json` are unchanged (tasks marked `expect ERROR`),
then it changes `allowGravatar` on `molecule-hedgedoc`, `config.json` changes and HedgeDoc has to restart,
`molecule-hedgedoc-default` runs again without a change and must not restart.
`verify` checks the quadlet unit with the secrets as files, the service without automatic restarts, the addresses, the time zone and the environment of the container
without options of HedgeDoc and without `TZ`, `config.json` with the options and without secrets, its owner and mode, `/status`,
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
