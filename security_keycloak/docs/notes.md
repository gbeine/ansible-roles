Keycloak runs in the container image [quay.io/keycloak/keycloak](https://quay.io/repository/keycloak/keycloak) (`latest` by default) as podman quadlet `keycloak`
in production mode (`start`) with an external database. The role creates the admin once on a new installation and manages realms, clients,
required actions and user federations with the modules `community.general.keycloak_*`.

### Configuration

```yaml
keycloak_home: '/srv/container/keycloak'
keycloak_ip: '192.168.99.70'
keycloak_network: 'podman99'
keycloak_hostname: 'keycloak'
keycloak_timezone: 'Europe/Berlin'
keycloak_config:
  hostname: 'https://sso.example.org'
  db: 'postgres'
  db-url-host: '192.168.99.71'
  db-url-database: 'keycloak'
  db-username: 'keycloak'
  bootstrap-admin-username: 'admin'
  log-level: [ 'INFO', 'org.keycloak.events:debug' ]
  features-disabled: [ 'impersonation' ]
keycloak_secrets:
  - name: 'keycloak_db_password'
    data: "{{ vault_keycloak_db_password }}"
    target: 'db-password'
  - name: 'keycloak_admin_password'
    data: "{{ vault_keycloak_admin_password }}"
    target: 'bootstrap-admin-password'
```

The role writes `keycloak_config` to `<keycloak_home>/keycloak.conf` (root, `0644`), it is mounted read-only to `/opt/keycloak/conf/keycloak.conf`.
`keycloak_home` is mandatory. The file contains no passwords, they are passed as environment variables (see Secrets).

`keycloak_config` contains the options of Keycloak as they are written in `keycloak.conf`
(see the [configuration of Keycloak](https://www.keycloak.org/server/all-config)), it is merged over the default of the role:
`db: mariadb`, `db-username: keycloak`, `db-url-database: keycloak`, `http-enabled: true`, `proxy-headers: xforwarded`,
`health-enabled: true` and `log: console`. `hostname` and `db-url-host` are mandatory.

- a string or number writes `option=value`, a list writes the elements separated by commas, Keycloak allows every option once
- `true` and `false` write `true` and `false`, Keycloak has no options without value
- `null` removes the option, e.g. an option of the default
- `${…}` in a value is an expression of Keycloak, e.g. `${env.NAME}`, backslashes are escaped by the role

`bootstrap-admin-username` is the name of the admin (`admin` by default), it is only used for the initialization and the login of the role,
it is never written to the `keycloak.conf` of the service.

`keycloak_environment` only takes the variables of the start script and the JVM, e.g. `JAVA_OPTS_APPEND` or `JAVA_OPTS_KC_HEAP`,
the options of Keycloak (`KC_*`) are set with `keycloak_config`. It has no default, without it the quadlet unit has no environment,
the time zone is set by podman with `keycloak_timezone`.

### Options with keys

Some options of Keycloak contain a free part in their names, e.g. a named datasource or a log category.
The keys are declared in `keycloak_keys`, a dictionary with a list of keys per family, the role generates the allowed names from them.
Keys start with a letter or digit, followed by letters, digits, `.`, `_` and `-`.

| Family | Generated names |
|---|---|
| `datasource` | the options of the database with the datasource appended, e.g. `db-url-host-<key>`, `db-username-<key>`, `db-kind-<key>`, `db-url-full-<key>`, `db-enabled-<key>`, `transaction-xa-enabled-<key>`, the secrets `db-password-<key>`, `db-tls-trust-store-password-<key>` and `db-mtls-key-store-password-<key>` |
| `log_category` | `log-level-<key>` |
| `feature` | `feature-<key>` |
| `header` | `telemetry-header-<key>`, `telemetry-logs-header-<key>`, `telemetry-metrics-header-<key>`, `tracing-header-<key>` |
| `spi` | `spi-<key>`, the key is the rest of the option, e.g. `connections-http-client--default--proxy-mappings` |

```yaml
keycloak_keys:
  datasource: [ 'audit' ]
  log_category: [ 'org.hibernate' ]
keycloak_config:
  db-kind-audit: 'postgres'
  db-url-host-audit: '192.168.99.72'
  log-level-org.hibernate: 'warn'
keycloak_secrets:
  - name: 'keycloak_audit_password'
    data: "{{ vault_keycloak_audit_password }}"
    target: 'db-password-audit'
```

### Secrets

The secrets are set with `keycloak_secrets`, every entry needs `name`, `data` and `target`, the targets are the password options of Keycloak:
`db-password`, `bootstrap-admin-password`, `db-tls-trust-store-password`, `db-mtls-key-store-password`, `config-keystore-password`, `vault-pass`
and the passwords of the key stores, trust stores and keys of `https-*` and `https-management-*`, plus the passwords of the datasources of `keycloak_keys`.
`db-password` and `bootstrap-admin-password` are mandatory. The password options must not be set in `keycloak_config`.

Keycloak cannot read single options from files: there are no `*_FILE` variables, and `keycloak.conf` cannot reference files.
The only file source of Keycloak is a Java KeyStore (`config-keystore`), its password would have to be passed in plain text again.
Therefore every entry is a podman secret passed to the environment with `type=env,target=KC_<OPTION>`, the option in upper case with `_` for other characters,
e.g. `db-password` becomes `KC_DB_PASSWORD` and `db-password-audit` becomes `KC_DB_PASSWORD_AUDIT`.
Keycloak reads the environment before `keycloak.conf`, so the passwords are neither part of `keycloak.conf` nor of the quadlet unit in plain text.
A changed secret restarts the running service.
Secrets must not contain line breaks or `${`, Keycloak would expand it as expression.

`bootstrap-admin-password` is only used for the initialization and the login of the role, it is not part of the quadlet unit.

### TLS

`keycloak_tls` sets the certificate of a realm deployed on the host by `pki_easyrsa_deploy` or `pki_certbot`:

```yaml
keycloak_tls:
  realm: 'sso.example.org'
  # optional, the realms of common_globals by default, e.g. /opt/certbot/etc/live for pki_certbot
  dir: '/opt/certbot/etc/live'
keycloak_config:
  http-enabled: false
keycloak_container:
  publish:
    - '8443:8443'
```

`ExecStartPre` of the quadlet unit copies `fullchain.pem` (`0644`) and `privkey.pem` (`0600`) of `<dir>/<realm>` with `install` to `<keycloak_home>/tls`
(`0700`) at every start, owned by the user `keycloak` (1000) of the image, `install` follows the links of the realm.
The directory is mounted read-only to `/opt/keycloak/conf/tls`, the role writes `https-certificate-file` and `https-certificate-key-file` to `keycloak.conf`,
they must not be set in `keycloak_config` then. The ports and `http-enabled` stay with `keycloak_config` and `keycloak_container`.
The files of the realm have to exist before the role runs, in check mode missing files are only reported.

The copies only change at a start, so `https-certificates-reload-period` of Keycloak does not see a renewal.
The timer of `pki_update` (`pki-update@keycloak.timer`) checks the certificate of the realm and restarts Keycloak if the certificate is newer than the start,
`keycloak_pki_update_enabled` (`true`) and `keycloak_pki_update_schedule` (`*-*-* 00/4:00:00`) control it.

### Initialization

Keycloak creates the realm `master` and the admin of `bootstrap-admin-*` only on a new installation, the database is the installation.
If Keycloak is not running, the role starts the container `<name>-init` once before the service: same image, network, environment, secrets
and volumes (including `keycloak.conf`), without address and ports, plus the secret `bootstrap-admin-password` as `KC_BOOTSTRAP_ADMIN_PASSWORD`
and the environment `KC_BOOTSTRAP_ADMIN_USERNAME`, `KC_CACHE=local` and `KC_SERVER_ASYNC_BOOTSTRAP=false`, the environment takes precedence over `keycloak.conf`.
With `keycloak_tls` the role copies the certificate like `ExecStartPre` before, the copies do not exist before the first start of the service.
The role waits until Keycloak reports the created admin (`Created temporary admin user`) or, on an existing installation, its start,
and removes the container afterwards, also if the initialization failed.
If the initialization fails, Keycloak may have created a part of its tables, drop them before the next run.

If Keycloak is running, the initialization is skipped. After every start the role logs in as admin to the realm `master`,
the role fails if the login fails, e.g. because the password of the admin was changed in Keycloak or the admin was deleted.
Keycloak marks the admin as temporary, create a permanent admin and delete the temporary one if wanted, then set its name and password in the inventory.

### Realms

`keycloak_realms` is a list of realms, every entry needs `realm` and may contain `id` (the name by default), `display_name`, `enabled`,
`login_with_email`, `required_actions`, `clients` and `user_federation`.

```yaml
keycloak_realms:
  - realm: 'example'
    display_name: 'Example'
    login_with_email: true
    required_actions:
      - alias: 'TERMS_AND_CONDITIONS'
        name: 'Terms and Conditions'
        providerId: 'TERMS_AND_CONDITIONS'
        enabled: true
    clients:
      - client_id: 'grafana'
        name: 'Grafana'
        secret: "{{ vault_keycloak_grafana_secret }}"
        public_client: false
        redirect_uris: [ 'https://grafana.example.org/*' ]
    user_federation:
      - federation_name: 'ldap'
        provider_id: 'ldap'
        config: { ... }
```

Clients take `client_id`, `name`, `description`, `root_url`, `client_authenticator_type`, `secret`, `redirect_uris`, `web_origins`, `protocol`,
`attributes` and the flags `standard_flow_enabled`, `implicit_flow_enabled`, `direct_access_grants_enabled`, `service_accounts_enabled`,
`authorization_services_enabled` and `public_client` (`true` by default).
User federations take `federation_id`, `federation_name`, `provider_id`, `config` and `mappers`.
The role compares the realm with its parameters in check mode first and only updates it if they differ,
an update of a realm always reports a change, because Keycloak changes the realm on every update.
The role uses the API of the container on `http://<ip>:8080` (`https://<ip>:8443` without certificate validation if `http-enabled` is `false`).

### Allowed variables

The role only allows the options of Keycloak in `security_keycloak__config_allowed`, the password options in `security_keycloak__secrets_allowed`
and the environment variables in `security_keycloak__environment_allowed`, it stops before any change if unknown options, secrets or variables are set.
This prevents unexpected behavior by accident, e.g. by a typo or a password in the configuration.
The options are generated from `quarkus/config-api` of Keycloak 26.8.2 without the hidden options and the options of the commands `import` and `export`,
the environment from `bin/kc.sh` and the `Dockerfile` of the image.
The check of the environment uses the environment of the container after merging `keycloak_container`.

### Container

Ports, volumes (e.g. providers), additional hosts (`etc_hosts`) and the dependencies are changed with `keycloak_container`,
it is merged over the default of the container. The dependencies of the quadlet unit are lists: `requires`, `wants`, `after`, `part_of` and `binds_to` are units,
`requires_mounts_for` are paths. They are written to `[Unit]` as `Requires=`, `Wants=`, `After=`, `PartOf=`, `BindsTo=` and `RequiresMountsFor=`.
The merge is not recursive, `keycloak_container.volumes` replaces `keycloak.conf` and the certificate, `keycloak_container.environment` replaces
`keycloak_environment`, `keycloak_container.secrets` the secrets. The container publishes no ports by default, a reverse proxy uses the address of the container.

```yaml
keycloak_container:
  wants: [ 'network-online.target' ]
  after: [ 'network-online.target' ]
```

### Validation

The role checks before any change:

- `keycloak_keys` is a dictionary of the known families with lists of valid and unique keys
- `keycloak_home` is an absolute path
- `keycloak_tls` is a dictionary with a valid realm and an absolute `dir`, the files of the realm exist, the options of the certificate are not set in `keycloak_config`
- `keycloak_secrets` is a list of entries with `name`, `data` and `target` and unique names, every target is a known password option and set once,
  `db-password` and `bootstrap-admin-password` are set, no secret contains a line break or `${`
- `keycloak_config` contains known options with strings, numbers, booleans, `null` or lists of them without line breaks,
  the boolean options are `true` or `false`, no password option, `hostname` and `db-url-host` are set
- `keycloak_environment` is a dictionary without options of Keycloak, only allowed environment variables without line breaks are set in the container
- `keycloak_realms` is a list of realms with known keys, booleans, lists and clients with `client_id` and user federations with `federation_name` and `provider_id`

If `keycloak_container` or `keycloak_config` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter. Keycloak checks the values of the options at the start.

### Check mode

The role runs with `--check`, also on a host where it never ran, and reports the home directory, `keycloak.conf`, the secrets, the quadlet unit
and the timer of `pki_update`. The initialization, the start, the login and the realms do not run in check mode.

### Restart and updates

Keycloak is restarted if it was running and `keycloak.conf`, a secret or the quadlet unit changed, otherwise it is started and enabled.
A renewed certificate restarts Keycloak by the timer of `pki_update` (see TLS).
If the start fails, the role shows the journal of the service.
Afterwards the role waits up to 300 seconds until the realm `master` answers and shows the journal otherwise.
Keycloak builds itself at the start if build options changed, e.g. `db` or `features`.
Updates of the image are done by `container_update` with `keycloak_autoupdate_enabled: true` and `keycloak_autoupdate_schedule`,
without `keycloak_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

| Former variable | Replacement |
|---|---|
| `keycloak_ip`, `keycloak_ipv6`, `keycloak_network`, `keycloak_hostname`, `keycloak_timezone`, `keycloak_labels`, `keycloak_version`, `keycloak_autoupdate_enabled`, `keycloak_realms` | Unchanged |
| `keycloak_db_type`, `keycloak_db_host`, `keycloak_db_port`, `keycloak_db_user`, `keycloak_db_name` | `db`, `db-url-host`, `db-url-port`, `db-username`, `db-url-database` of `keycloak_config` |
| `keycloak_db_pass` | Secret with target `db-password` |
| `keycloak_admin` | `bootstrap-admin-username` of `keycloak_config` |
| `keycloak_password` | Secret with target `bootstrap-admin-password` |
| `keycloak_url` | `hostname` of `keycloak_config` |
| `keycloak_http_enabled`, `keycloak_health_enabled`, `keycloak_metrics_enabled`, `keycloak_proxy_headers`, `keycloak_log`, `keycloak_log_level` | `http-enabled`, `health-enabled`, `metrics-enabled`, `proxy-headers`, `log`, `log-level` of `keycloak_config` |
| `keycloak_proxy_address_forwarding` | Removed, `PROXY_ADDRESS_FORWARDING` is not read by Keycloak, use `proxy-headers` |
| `keycloak_publish` | `keycloak_container.publish`, the former role ignored it |
| none | `keycloak_environment`, `keycloak_config`, `keycloak_keys`, `keycloak_secrets`, `keycloak_container`, `keycloak_autoupdate_schedule` |
| `podman___update_mode` | Removed, updates are done by `container_update` |

Changes of this revision:

- `keycloak_home` is mandatory, `keycloak.conf` is written to it and mounted read-only instead of the podman secret `<name>-config`
- the passwords are podman secrets per entry of `keycloak_secrets` passed as `KC_*` variables with `type=env`, the targets stay the same
- the podman secrets `keycloak-config` and `keycloak-init-config` are not used anymore, remove them with `podman secret rm keycloak-config keycloak-init-config`
- `keycloak_tls`, `keycloak_pki_update_enabled` and `keycloak_pki_update_schedule` are new, a certificate mounted with `keycloak_container.volumes` can be replaced by `keycloak_tls`
- `TZ` is no default of the environment anymore, the time zone is set by podman
- the messages of the validation of the secrets name the variable in backticks

In `keycloak_realms` `required_actions`, `user_federation` and the keys of the clients except `client_id` are optional now, `id` defaults to `realm`.

Fixed bugs:

- the name of the database was passed as `KC_DB_SCHEMA`, it is `db-url-database` now, set `db-schema` if a schema was used
- the role stopped Keycloak at every run and reached the realms through the public URL

Changed behavior:

- Keycloak runs in production mode (`start`) instead of `start-dev`, `http-enabled: true` is the default for a reverse proxy
- the passwords are podman secrets in the environment of the container instead of plain environment variables
- the admin is created once by `<name>-init`, the quadlet unit no longer contains `KEYCLOAK_ADMIN` and its password,
  an existing installation keeps its admin, the role checks the login
- `/etc/localtime` and `/etc/timezone` are no longer mounted, the time zone is set by podman with `keycloak_timezone`
- the configuration, the environment, the secrets and the realms are checked before any change
- the role restarts Keycloak only if `keycloak.conf`, a secret or the quadlet unit changed and waits until Keycloak answers
- the tags are `security` and `security_keycloak`

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root. The VMs need access to quay.io and docker.io.

| Platform | Test case |
|---|---|
| `molecule-keycloak-default` | Only the mandatory variables with MariaDB |
| `molecule-keycloak` | PostgreSQL, IPv6, labels, another admin, log levels with a key, a disabled feature, metrics, a realm with a client and a required action, the certificate of a realm with https only |

`prepare` creates the podman network, pulls the images and starts the database, on `molecule-keycloak` it creates a CA and the certificate of the realm
with openssl on the controller and deploys the realm in the structure of `pki_easyrsa_deploy`.
`check` runs `converge` with `--check` on the new VMs.
`side_effect` runs the role with `keycloak_container` not a dictionary, `keycloak_secrets` not a list, a secret without target, an unknown secret,
without the database password, a password in `keycloak_config`, an option in `keycloak_environment`, a line break in the environment, unknown options and a boolean as string,
invalid `keycloak_keys`, without `db-url-host`, invalid realms, `keycloak_tls` not a dictionary, with an unknown key, an invalid realm or a relative directory,
a realm without certificate, an option of the certificate in `keycloak_config` and a relative home
and checks that it fails with the expected message and the quadlet unit and `keycloak.conf` are unchanged (tasks marked `expect ERROR`),
then it changes the log level on `molecule-keycloak`, `keycloak.conf` changes, Keycloak has to restart and the initialization must not run again,
`molecule-keycloak-default` runs again without a change and must not restart.
`verify` checks the quadlet unit with the volumes, the secret of the database as environment, `ExecStartPre` and without passwords, the admin and the time zone,
the service without automatic restarts, the removed container of the initialization and the former secrets, `keycloak.conf` in the home and in the container
without passwords, the copies of the certificate, the time zone of the container, the timer of `pki_update`, the login of the admin, the health,
the realm, a token of the client with its secret and the metrics, on `molecule-keycloak` the certificate is verified with `openssl s_client`
and the CA of the realm on both ports, the requests use https.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd security_keycloak
MOLECULE_TART_IMAGE='debian' molecule test
```
