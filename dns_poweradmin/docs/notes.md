Poweradmin runs in the official container image [poweradmin/poweradmin](https://hub.docker.com/r/poweradmin/poweradmin) and is configured with environment variables.
See the [Docker documentation of Poweradmin](https://github.com/poweradmin/poweradmin/blob/master/DOCKER.md) for all variables.

`poweradmin_version` sets the tag of the image, `stable` by default, the release line recommended by Poweradmin for production.
Use `latest` for the newest release line.

### Environment and secrets

All variables are set with `poweradmin_environment`, which is merged over the defaults of the role.
Variables carrying secrets are passed as podman secrets with `poweradmin_secrets` and must not be set in `poweradmin_environment`.
Every secret has a `name`, the `data` and the `target`, the usual name of the variable, e.g. `PA_SESSION_KEY`.
The role creates the secret with `podman secret create`, mounts it to `/run/secrets/<name>` and sets `<target>__FILE` (two underscores),
the image reads the variable from this file, so the secret is neither part of the quadlet unit nor of the environment of the container.

The role requires the following variables and checks them before it changes anything:

| Variable | Set with | Default of the role |
|---|---|---|
| `DB_TYPE` | `poweradmin_environment` | `sqlite` |
| `DNS_NS1` | `poweradmin_environment` | – |
| `DNS_NS2` | `poweradmin_environment` | – |
| `DNS_HOSTMASTER` | `poweradmin_environment` | – |
| `DB_HOST`, `DB_USER`, `DB_NAME` | `poweradmin_environment` | –, only required for `DB_TYPE` `mysql` and `pgsql` |
| `DB_PASS` | `poweradmin_secrets` | –, only required for `DB_TYPE` `mysql` and `pgsql` |

The role also sets `DB_FILE` to `/db/pdns.db` (in `db` below `poweradmin_home`) and `PA_TIMEZONE` to `poweradmin_timezone`.

The following variables carry secrets, they are the allowed targets of `poweradmin_secrets` and are rejected in `poweradmin_environment`:
`DB_PASS`, `PA_SESSION_KEY`, `PA_ADMIN_PASSWORD`, `PA_PDNS_API_KEY`, `PA_PDNS_WEBSERVER_PASSWORD`, `PA_SMTP_PASSWORD`, `PA_RECAPTCHA_SECRET_KEY`,
`PA_LDAP_BIND_PASSWORD`, `PA_OIDC_AZURE_CLIENT_SECRET`, `PA_OIDC_GOOGLE_CLIENT_SECRET`, `PA_OIDC_GENERIC_CLIENT_SECRET`, `PA_SAML_SP_PRIVATE_KEY`.
`DB_SSL_KEY` is the path of a key file in the container, not a secret.

Set `PA_SESSION_KEY` as secret, otherwise the container generates a new session key on every start and all sessions are lost.

Example with SQLite:

```yaml
poweradmin_environment:
  DNS_NS1: 'ns1.example.org'
  DNS_NS2: 'ns2.example.org'
  DNS_HOSTMASTER: 'hostmaster.example.org'
poweradmin_secrets:
  - name: 'poweradmin_session_key'
    data: "{{ vault_poweradmin_session_key }}"
    target: 'PA_SESSION_KEY'
```

Example with the PostgreSQL database of PowerDNS and the PowerDNS API:

```yaml
poweradmin_environment:
  DB_TYPE: 'pgsql'
  DB_HOST: '192.168.99.10'
  DB_USER: 'poweradmin'
  DB_NAME: 'powerdns'
  DNS_NS1: 'ns1.example.org'
  DNS_NS2: 'ns2.example.org'
  DNS_HOSTMASTER: 'hostmaster.example.org'
  PA_PDNS_API_URL: 'http://192.168.99.11:8081'
poweradmin_secrets:
  - name: 'poweradmin_db_password'
    data: "{{ vault_poweradmin_db_password }}"
    target: 'DB_PASS'
  - name: 'poweradmin_session_key'
    data: "{{ vault_poweradmin_session_key }}"
    target: 'PA_SESSION_KEY'
  - name: 'poweradmin_pdns_api_key'
    data: "{{ vault_powerdns_api_key }}"
    target: 'PA_PDNS_API_KEY'
```

The container loads the Poweradmin schema into an empty database on startup.
With `PA_CREATE_ADMIN: 'true'` it creates an initial admin user, set the password as secret with target `PA_ADMIN_PASSWORD`,
otherwise it is generated and printed to the log of the container.

### Allowed variables

The role only allows the environment variables in `dns_poweradmin__environment_allowed` and the secrets above,
it stops before any change if unknown variables or secrets are set.
This prevents unexpected behavior by accident, e.g. by a typo or a variable that has to be passed as secret.
The check uses the environment and the secrets of the container after merging `poweradmin_container`,
so variables set with `poweradmin_container.environment` are checked as well.
The allowed variables are generated from `docker-entrypoint.sh` of Poweradmin v4.4.3, the release of the tag `stable`,
without the internal variables of the script and the variables carrying secrets,
and the file variables of the secrets. The role sets them from `poweradmin_secrets`, they must not be set in `poweradmin_environment`.
Newer releases (`latest`) know additional variables, e.g. `DB_CHARSET` or `PA_HEALTH_TOKEN`, the list is generated again for a new release line.

### Validation

The role checks before any change that `poweradmin_secrets` is a list of entries with `name`, `data` and `target` and unique names,
that the required variables and secrets are set, that neither a secret nor its file variable is set in `poweradmin_environment`
and that only allowed variables and secrets are used.
If `poweradmin_container` is no dictionary, merging it with the default fails before anything changes.

### Changes and restarts

A running container is restarted when a secret or the quadlet unit changed, e.g. after changing `poweradmin_environment`.
The first start of the container does not trigger an additional restart.
Updates of the image are done by `container_update` with `poweradmin_autoupdate_enabled: true` and `poweradmin_autoupdate_schedule`.

### Migration from `settings.php`

Former versions of the role generated `settings.php` from single variables and mounted it as `/config/custom.php`.
The role does not generate this file anymore and does not mount it, set the variables in `poweradmin_environment` and `poweradmin_secrets` instead:

| Former variable | Now |
|---|---|
| `poweradmin_db_type`, `poweradmin_db_host`, `poweradmin_db_port`, `poweradmin_db_user`, `poweradmin_db_name` | `DB_TYPE`, `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_NAME` |
| `poweradmin_db_charset`, `poweradmin_db_file` | `DB_FILE`, `DB_CHARSET` is only known by releases after 4.4 (`latest`) |
| `poweradmin_db_pass` | secret with target `DB_PASS` |
| `poweradmin_dns_ns1` … `poweradmin_dns_ns4`, `poweradmin_dns_hostmaster` | `DNS_NS1` … `DNS_NS4`, `DNS_HOSTMASTER` |
| `poweradmin_pa_dns_ttl`, `poweradmin_pa_dns_soa_*` | `PA_DNS_TTL`, `PA_DNS_SOA_*` |
| `poweradmin_pa_dns_zone_type_default` | `PA_DNS_ZONE_TYPE_DEFAULT` |
| `poweradmin_pa_dns_strict_tld_check`, `poweradmin_pa_dns_top_level_tld_check`, `poweradmin_pa_dns_third_level_check` | `PA_DNS_STRICT_TLD_CHECK`, `PA_DNS_TOP_LEVEL_TLD_CHECK`, `PA_DNS_THIRD_LEVEL_CHECK` |
| `poweradmin_pa_dns_txt_auto_quote`, `poweradmin_pa_dns_prevent_duplicate_ptr` | `PA_DNS_TXT_AUTO_QUOTE`, `PA_DNS_PREVENT_DUPLICATE_PTR` |
| `poweradmin_pa_dnssec_enabled` | `PA_DNSSEC_ENABLED` |
| `poweradmin_pa_session_key` | secret with target `PA_SESSION_KEY` |
| `poweradmin_pa_mfa_enabled`, `poweradmin_pa_mfa_app_enabled`, `poweradmin_pa_mfa_mail_enabled` | `PA_MFA_ENABLED`, `PA_MFA_APP_ENABLED`, `PA_MFA_EMAIL_ENABLED` |
| `poweradmin_pa_mfa_recovery_codes`, `poweradmin_pa_mfa_recovery_code_length` | `PA_MFA_RECOVERY_CODES`, `PA_MFA_RECOVERY_CODE_LENGTH` |
| `poweradmin_pa_api_enabled`, `poweradmin_pa_api_basic_auth_enabled`, `poweradmin_pa_api_docs_enabled` | `PA_API_ENABLED`, `PA_API_BASIC_AUTH_ENABLED`, `PA_API_DOCS_ENABLED` |
| `poweradmin_pa_pdns_api_url`, `poweradmin_pa_pdns_server_name` | `PA_PDNS_API_URL`, `PA_PDNS_SERVER_NAME` |
| `poweradmin_pa_pdns_api_key` | secret with target `PA_PDNS_API_KEY` |
| `poweradmin_pa_display_stats` | `PA_DISPLAY_STATS` |
| `poweradmin_pa_whois_enabled`, `poweradmin_pa_rdap_enabled` | `PA_MODULE_WHOIS_ENABLED`, `PA_MODULE_RDAP_ENABLED` |
| `poweradmin_pa_dnssec_debug` | removed |

Values that were fixed in the former `settings.php`, e.g. mail enabled with the sender `poweradmin@example.com`, are not set anymore, the defaults of the image apply.
The former default `poweradmin_db_type` was `sqlite`, but the role required `poweradmin_db_host`, `poweradmin_db_port` and `poweradmin_db_pass` anyway, these are only required for `mysql` and `pgsql` now.

The default tag changed from `latest` to `stable`, which may be an older release line, set `poweradmin_version: 'latest'` to keep it.
Remove the former `settings.php` in `poweradmin_home`, it contains the database password and the session key in plain text.

Later changes of the role:

- The secrets are mounted as files and read with `<target>__FILE`, before they were passed as environment variables, `poweradmin_secrets` stays the same.
- `PA_HEALTH_TOKEN` is not a secret of the role anymore, the release of `stable` does not know it.
- `poweradmin_publish` is removed, set the ports with `poweradmin_container.publish`.
- The tags are `dns` and `dns_poweradmin`.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The base VM is cloned for every platform and the clones are deleted afterwards, the base VM itself is never changed.
The playbooks creating and destroying the VMs are shared by all tart scenarios and live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-poweradmin-ipv4-only` | Container with IPv4 address only, SQLite |
| `molecule-poweradmin-ipv6` | Container with IPv4 and IPv6 address, SQLite |

`prepare` sets up podman and the network `podman-molecule` with the role `container_podman` and pulls the image.
`side_effect` runs the role with `poweradmin_container` not a dictionary, two secrets of the same name, MySQL without the secret of the database password,
the session key and its file variable in the environment, an unknown environment variable in `poweradmin_environment` and in `poweradmin_container.environment` and an unknown secret
and checks that it fails with the expected message and the quadlet unit is unchanged (tasks marked `expect ERROR`),
then it changes `PA_APP_TITLE` and checks that the running service is restarted.
`verify` checks the quadlet unit with the mounted secret, `PA_SESSION_KEY__FILE` and the environment without the session key, the podman secret,
the session key read from the file in the generated `settings.php`, the service and the container addresses,
requests the login page via IPv4 and IPv6 and checks the title of the side effect and the SQLite database.
The VMs need access to Docker Hub.

Requirements on the controller: `tart`, `sshpass` (`brew install hudochenkov/sshpass/sshpass`), `molecule` and the collection `containers.podman`.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd dns_poweradmin
MOLECULE_TART_IMAGE='debian' molecule test
```
