GitLab CE runs in the container image [gitlab/gitlab-ce](https://hub.docker.com/r/gitlab/gitlab-ce) (`latest` by default, `gitlab_version` sets the tag) as podman quadlet.
The image contains GitLab with PostgreSQL, Redis, nginx and the registry, it runs as root and listens on the ports 80, 443 and 22.
Below `gitlab_home` the role creates `config` (`/etc/gitlab`), `data` (`/var/opt/gitlab`) and `logs` (`/var/log/gitlab`).
GitLab needs at least 4 GB of memory, the first start migrates the database and takes several minutes,
the quadlet unit allows 900 seconds for the start (`TimeoutStartSec`).

### Configuration

`gitlab_config` contains the options of `/etc/gitlab/gitlab.rb`, see `files/gitlab-config-template/gitlab.rb.template` of
[omnibus-gitlab](https://gitlab.com/gitlab-org/omnibus-gitlab). It is merged recursively over the default of the role and written to
`<gitlab_home>/config/gitlab.rb` (root, mode `0600`). The image reads the file with `gitlab-ctl reconfigure` at every start, GitLab never writes it,
so the role replaces the file and restarts GitLab after a change.

- a value that is no dictionary on the top level is a setting, e.g. `external_url: 'https://gitlab.example.org'` writes `external_url 'https://gitlab.example.org'`
- a dictionary on the top level is an attribute, its keys are the options, e.g. `gitlab_rails: { smtp_enable: true }` writes `gitlab_rails['smtp_enable'] = true`
- values are written as Ruby: strings in single quotes, numbers, `true` and `false`, `null` as `nil`, lists as arrays and dictionaries as hashes with string keys
- the options the template sets with nested keys (`app_gitlab_ce__config_sections`, e.g. `gitlab_rails.object_store` or `registry.nginx`)
  are written key by key, e.g. `gitlab_rails['object_store']['enabled'] = true`, so the other keys keep their defaults

The default of the role sets `gitlab_rails.time_zone` to `gitlab_timezone` and `gitlab_rails.monitoring_whitelist` to `127.0.0.0/8` and `::1/128`.
Without `external_url` the image uses `http://<gitlab_hostname>`.

```yaml
gitlab_config:
  external_url: 'https://gitlab.example.org'
  registry_external_url: 'https://registry.example.org'
  gitlab_rails:
    gitlab_ssh_host: 'ssh.example.org'
    gitlab_email_from: 'gitlab@example.org'
    smtp_enable: true
    smtp_address: 'mail.example.org'
    smtp_port: 465
    smtp_user_name: 'gitlab@example.org'
    smtp_tls: true
  nginx:
    listen_https: false
    listen_port: 80
```

### Secrets

`gitlab.rb` is Ruby and can read files, so the passwords are podman secrets mounted as files.
`gitlab_secrets` is a list of entries with `name`, `data` and `target`, the target is the path of the option, e.g. `gitlab_rails.smtp_password`.
The role mounts the secret to `/run/secrets/<name>` (root, `0400`) and writes `gitlab_rails['smtp_password'] = File.read('/run/secrets/<name>').chomp` to `gitlab.rb`,
the passwords are neither part of `gitlab.rb` nor of the quadlet unit or the environment. A changed secret restarts GitLab.

The targets are the passwords, secrets and tokens of the template (`app_gitlab_ce__secrets_allowed_options`), e.g. `gitlab_rails.initial_root_password`,
`gitlab_rails.smtp_password` or `gitlab_rails.db_password`, and the passwords of the LDAP servers (see Options with keys).
A target must not be set in `gitlab_config`. `gitlab_rails.initial_root_password` is only used by the first start with an empty database.

```yaml
gitlab_secrets:
  - name: 'gitlab_root_password'
    data: "{{ vault_gitlab_root_password }}"
    target: 'gitlab_rails.initial_root_password'
  - name: 'gitlab_smtp_password'
    data: "{{ vault_gitlab_smtp_password }}"
    target: 'gitlab_rails.smtp_password'
```

### Options with keys

`gitlab_rails.ldap_servers` is a dictionary of LDAP servers, the keys are the IDs of the providers, e.g. `main`.
The password of a server is a secret with the target `gitlab_rails.ldap_servers.<key>.password`, the keys are declared in `gitlab_keys`.

| Family | Generated name |
|---|---|
| `ldap_servers` | the target `gitlab_rails.ldap_servers.<key>.password` |

```yaml
gitlab_keys:
  ldap_servers: [ 'main' ]
gitlab_config:
  gitlab_rails:
    ldap_enabled: true
    ldap_servers:
      main:
        label: 'LDAP'
        host: 'ldap.example.org'
        port: 636
        uid: 'uid'
        encryption: 'simple_tls'
        bind_dn: 'cn=gitlab,dc=example,dc=org'
        base: 'dc=example,dc=org'
gitlab_secrets:
  - name: 'gitlab_ldap_password'
    data: "{{ vault_gitlab_ldap_password }}"
    target: 'gitlab_rails.ldap_servers.main.password'
```

The keys consist of lowercase letters, digits and `_` and start with a letter.

### TLS

`gitlab_tls` takes the certificate of a realm on the host: `realm` is the name of the realm, `dir` the directory of the realms,
it defaults to the realms of `common_globals` (`site_pki_realms_dir`, default `/etc/pki/realms`) deployed by `pki_easyrsa_deploy`, e.g. `/opt/certbot/etc/live` for `pki_certbot`.
`ExecStartPre` of the quadlet unit copies with `install` on every start

- `fullchain.pem` to `config/ssl/tls.crt` (`0644`)
- `privkey.pem` to `config/ssl/tls.key` (`0600`)
- `chain.pem` to `config/trusted-certs/<realm>.crt`, GitLab trusts the CA of the realm

and the role sets `registry.nginx.ssl_certificate` and `registry.nginx.ssl_certificate_key` to these files, they must not be set in `gitlab_config` then.
Other components use the certificate with their options, e.g. `gitlab_rails: { nginx: { ssl_certificate: '/etc/gitlab/ssl/tls.crt' } }`.
The timer of `pki_update` restarts GitLab after a renewal of the certificate (`gitlab_pki_update_enabled`, `gitlab_pki_update_schedule`).
The realm has to be deployed before the role runs, e.g. by `pki_easyrsa_deploy` or `pki_certbot` in the same play.

```yaml
gitlab_tls:
  realm: 'registry.example.org'
```

### Allowed variables

The role only allows the options in `app_gitlab_ce__config_settings` and `app_gitlab_ce__config_allowed`, the secrets in `app_gitlab_ce__secrets_allowed`
and the environment variables in `app_gitlab_ce__environment_allowed`, it stops before any change if unknown names are set.
This prevents unexpected behavior by accident, e.g. by a typo or a password that has to be passed as secret.

The options and the secrets are generated from `files/gitlab-config-template/gitlab.rb.template` of omnibus-gitlab 19-6-stable,
new versions may add options, the lists are generated again. The content of options that are dictionaries or lists is not checked, e.g. `ldap_servers`.

The environment only takes the variables of `docker/assets/init-container` and `docker/assets/gitlab.rb` of the image
(e.g. `GITLAB_SKIP_TAIL_LOGS` or `GITLAB_POST_RECONFIGURE_SCRIPT`). `GITLAB_OMNIBUS_CONFIG` is `gitlab_config`,
`GITLAB_ROOT_PASSWORD` is the secret `gitlab_rails.initial_root_password`, both are not allowed.
`gitlab_environment` has no default, without it the quadlet unit has no environment.
The check uses the environment of the container after merging `gitlab_container`.

### Container

Ports, volumes, additional hosts (`etc_hosts`), `shm_size` (`256m`), `timeout_start` (900 seconds), `stop_timeout` (120 seconds) and the dependencies are changed with `gitlab_container`,
it is merged over the default of the container. No port is published by default.
`stop_timeout` is the time podman waits for GitLab to stop PostgreSQL, Puma and Sidekiq before it kills the container,
`TimeoutStopSec` of the quadlet unit is 30 seconds longer.
The dependencies of the quadlet unit are lists: `requires`, `wants`, `after`, `part_of` and `binds_to` are units,
`requires_mounts_for` are paths. They are written to `[Unit]` as `Requires=`, `Wants=`, `After=`, `PartOf=`, `BindsTo=` and `RequiresMountsFor=`.
The merge is not recursive, `gitlab_container.volumes` replaces the three directories.

```yaml
gitlab_container:
  publish: [ '2222:22' ]
  wants: [ 'network-online.target' ]
  after: [ 'network-online.target' ]
```

### Validation

The role checks before any change:

- `gitlab_config` and `gitlab_container` are dictionaries, merging them with the defaults fails otherwise
- `gitlab_keys` is a dictionary of known families with lists of valid and unique keys
- `gitlab_secrets` is a list of entries with `name`, `data` and `target`, with unique names and targets, the targets are allowed
- `gitlab_config` only contains allowed options, no values with line breaks, no targets of the secrets and not the options set for `gitlab_tls`
- `gitlab_tls` only contains `realm` and `dir`, the realm is a name of letters, digits, `_`, `.` and `-`, `dir` is an absolute path, the files of the realm exist
- `gitlab_home` is an absolute path
- only allowed environment variables are set in the container, their values contain no line breaks

### Check mode

The role runs with `--check` without failing, also on a host where it never ran before.
It reports the changes of the directories, `gitlab.rb`, the secrets and the quadlet unit, the service is neither started nor restarted.
Missing files of the realm are only reported in check mode.

### Restart and updates

GitLab is restarted if it was running and `gitlab.rb`, a secret or the quadlet unit changed, otherwise it is started and enabled,
the start runs `gitlab-ctl reconfigure`. If the start fails, the role stops with the last lines of the journal of the service.
Updates of the image are done by `container_update` with `gitlab_autoupdate_enabled: true` and `gitlab_autoupdate_schedule`,
without `gitlab_autoupdate_schedule` the schedule of `container_update` is used. GitLab only supports updates along its upgrade path,
`gitlab_version` should be set to a release.

### Migration

The single variables are replaced by `gitlab_config`, `gitlab_secrets`, `gitlab_tls` and `gitlab_container`:

| Former variable | Now |
|---|---|
| `gitlab_hostname` | stays, mandatory, the default `gitlab.<dns_hostname>` is removed |
| `gitlab_timezone` | stays, mandatory, it sets the time zone of the container and `gitlab_rails.time_zone` |
| `gitlab_ipv6` | stays, optional |
| `gitlab_hosts` | `gitlab_container.etc_hosts` |
| `gitlab_publish` | `gitlab_container.publish` |
| `gitlab_external_url` | `gitlab_config.external_url` |
| `gitlab_ssh_host` | `gitlab_config.gitlab_rails.gitlab_ssh_host` |
| `gitlab_smtp_enable`, `_address`, `_port`, `_user_name`, `_domain`, `_tls`, `_pool` | `gitlab_config.gitlab_rails.smtp_enable`, `smtp_address`, `smtp_port`, `smtp_user_name`, `smtp_domain`, `smtp_tls`, `smtp_pool` |
| `gitlab_smtp_starttls` | `gitlab_config.gitlab_rails.smtp_enable_starttls_auto` |
| `gitlab_smtp_password` | a secret with the target `gitlab_rails.smtp_password` |
| `gitlab_email_enable`, `_from`, `_display_name`, `_reply_to` | `gitlab_config.gitlab_rails.gitlab_email_enabled`, `gitlab_email_from`, `gitlab_email_display_name`, `gitlab_email_reply_to` |
| `gitlab_monitoring_whitelist` | `gitlab_config.gitlab_rails.monitoring_whitelist`, the default stays |
| `gitlab_ldap_enable` | `gitlab_config.gitlab_rails.ldap_enabled` |
| `gitlab_ldap_label`, `_host`, `_port`, `_uid`, `_encryption`, `_active_directory`, `_allow_username_or_email_login`, `_lowercase_usernames`, `_block_auto_created_users`, `_base`, `_user_filter`, `_attributes` | the keys of `gitlab_config.gitlab_rails.ldap_servers.main` |
| `gitlab_registry_external_url` | `gitlab_config.registry_external_url` |
| `gitlab_registry_enable`, `_host`, `_port`, `_path` | `gitlab_config.gitlab_rails.registry_enabled`, `registry_host`, `registry_port`, `registry_path` |
| `gitlab_registry_ssl_realm` | `gitlab_tls.realm` |

- The former role wrote the defaults of the removed variables to `gitlab.rb` (e.g. `smtp_enable`, `ldap_enabled` and `registry_enabled` false),
  they are the defaults of GitLab, the role only writes the options of `gitlab_config` now.
- The template of the former role copied the whole template of GitLab and was not written in update mode, `gitlab.rb` is written on every run now.
- The former role read `timezone` of a container default that did not set it, so it always failed on `mandatory`.
- The certificate of the registry and the CA of `pki_easyrsa_deploy` were copied once by the role, `ExecStartPre` copies them on every start now,
  the files are `config/ssl/tls.crt`, `config/ssl/tls.key` and `config/trusted-certs/<realm>.crt`, the former files below `config/ssl` and `config/trusted-certs` can be removed.
- `pki_easyrsa_deploy` is no dependency of the role anymore, the play deploys the realm before, e.g. with `pki_easyrsa_deploy` or `pki_certbot`.
- The container was managed by the podman module with `restart_policy: always`, it is a quadlet unit now.
  The former container `gitlab-ce` has to be removed before the first run (`podman rm -f gitlab-ce`), the data in `gitlab_home` stays.
- `expose` is removed, `podman___update_mode` is not evaluated anymore, the tag `app` is added.
- podman waits 120 seconds for GitLab to stop, the former container was killed after the 10 seconds of podman.
- `gitlab_config`, `gitlab_secrets`, `gitlab_keys`, `gitlab_tls`, `gitlab_labels`, `gitlab_autoupdate_*` and `gitlab_pki_update_*` are new.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root, the platforms set `memory` (6 GB) and `cpu` (4) of the VMs.

| Platform | Test case |
|---|---|
| `molecule-gitlab-ce-default` | Only the mandatory variables |
| `molecule-gitlab-ce` | IPv6, labels, dependencies, `external_url`, the registry with the certificate of a realm, SMTP, LDAP with `gitlab_keys` and the initial root password, the SMTP and the LDAP password as secrets |

`prepare` creates the podman network, pulls the image and creates a realm with a self-signed certificate for the registry on `molecule-gitlab-ce`.
`check` runs `converge` with `--check` on the new VMs.
`side_effect` runs the role with `gitlab_container` and `gitlab_config` not a dictionary, unknown options, a line break in a value, a secret in `gitlab_config`,
`gitlab_secrets` not a list, an unknown secret, the password of an LDAP server without its key, an invalid key, `GITLAB_OMNIBUS_CONFIG` and a line break in the environment,
an unknown key in `gitlab_tls`, a relative directory of the realms and a relative home
and checks that it fails with the expected message and the quadlet unit and `gitlab.rb` are unchanged (tasks marked `expect ERROR`),
then it changes `gitlab_rails.gitlab_default_theme` on `molecule-gitlab-ce`, GitLab has to restart,
`molecule-gitlab-ce-default` runs again without a change and must not restart.
`verify` checks the quadlet unit with the secrets, `ExecStartPre` and the dependencies and without the time zone files of the host,
`gitlab.rb` with its mode and the references to the secrets, the service without automatic restarts, the addresses, the time zone and the environment of the container,
waits until GitLab is ready, checks with `gitlab-rails runner` that the password of root is the one of the secret,
logs in as root with this password with the form login
and requests the registry with the CA of the realm.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd app_gitlab_ce
MOLECULE_TART_IMAGE='debian' molecule test
```
