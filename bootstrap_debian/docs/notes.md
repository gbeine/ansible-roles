- The role needs the filters `hostname_short` and `ipv4_netmask2prefixlength` from `common_filters`, so add `common_filters` to the play before `bootstrap_debian`:

```yaml
- name: 'Configure host42.example.org'
  become: 'yes'
  hosts: 'host42'
  roles:
    - 'common_filters'
    - 'bootstrap_debian'
```

- The role starts with `apt-get update` and the installation of the packages required by the apt modules, followed by the repositories and storage, so packages can rely on mounted directories.
- Repositories, packages, timezone and hostname/hosts are always configured. Storage and accounts run when their lists are not empty. Networking, PKI, logrotate, unattended upgrades and mail have to be enabled with `debian_networking_enable`, `debian_pki_enable`, `debian_logrotate_enable`, `debian_unattended_upgrades_enable` and `debian_mail_enable`, because they overwrite system configuration files completely.
- With `debian_cloud_manage_etc_hosts: true` (default `false`) cloud-init manages `/etc/hosts` (`manage_etc_hosts: True` in `/etc/cloud/cloud.cfg.d/99-manage_etc_hosts.cfg`) and the role does not generate it.
- `debian_hostname` is mandatory.
- `debian_repositories` replaces the default Debian repositories completely. The entries are written as deb822 files to `/etc/apt/sources.list.d/<name>.sources`:

```yaml
debian_repositories:
  - name: 'debian'
    types: 'deb'
    uris: 'http://deb.debian.org/debian'
    suites: [ 'trixie', 'trixie-updates' ]
    components: [ 'main', 'contrib', 'non-free-firmware' ]
  - name: 'example'
    uris: 'https://repo.example.org/debian'
    suites: [ 'stable' ]
    components: [ 'main' ]
    signed_by: 'https://repo.example.org/key.asc'
```

- Repositories that are not configured are removed: `*.sources` in `/etc/apt/sources.list.d` without an entry in `debian_repositories` (including keys stored by the role for them), all `*.list` files in `/etc/apt/sources.list.d` and `/etc/apt/sources.list`. Additional repositories therefore belong to `debian_repositories`. With `debian_repositories_prune: false` the role keeps them.
- Bind mounts in `debian_mounts` default to `fs: none` and `options: rw,bind`.
- This role replaces the former roles `bootstrap_hosts`, `bootstrap_logrotate`, `bootstrap_networking`, `bootstrap_packages`, `bootstrap_repositories`, `bootstrap_storage`, `bootstrap_timezone`, `bootstrap_accounts`, `apt_common` and `apt_unattended_upgrades`. The inventory variables were renamed:

| Former variable | New variable |
|---|---|
| `packages` | `debian_packages` |
| `local_packages` | `debian_local_packages` |
| `timezone` | `debian_timezone` |
| `dns_hostname` | `debian_hostname` |
| `hosts` | `debian_hosts` |
| `cloud_manage_etc_hosts` | `debian_cloud_manage_etc_hosts`, default is now `false` |
| `storage` | `debian_storage` |
| `mount` | `debian_mounts` |
| `bootstrap_networking_interfaces` | `debian_network_interfaces` |
| `bootstrap_groups` | `debian_groups` |
| `bootstrap_users` | `debian_users` |
| `logrotate_files` | `debian_logrotate_files` |
| `unattended_upgrades_*` | `debian_unattended_upgrades_*` |
| `bootstrap_<area>_enable` (role `bootstrap`) | `debian_networking_enable`, `debian_logrotate_enable`, `debian_unattended_upgrades_enable` |

### Site settings

The role depends on `common_globals`, which provides the settings of the site (`site_*`), and does the Debian specific parts, which were done by the roles `pki_common` and `mail_common` before.

With `debian_pki_enable: true` the role installs the PKI packages `acl`, `ca-certificates`, `openssl` and `ssl-cert`
and copies the CA certificates in `site_pki_ca_certificates` from `<site_pki_secrets_dir>/ca-certificates` (default `<inventory_dir>/secrets/ca-certificates`) to `/usr/local/share/ca-certificates`,
`update-ca-certificates` runs if one changed.

With `debian_mail_enable: true` the site settings are the defaults of the mail configuration:

- `site_mail_root_forward` is the alias of `root`, `debian_mail_aliases` overrides it,
- with `debian_mail_root_forward_enable: true` the role writes `site_mail_root_forward` to `/root/.forward` as well, the role fails if `site_mail_root_forward` is not set,
- `site_mail_domain` is the `maildomain`, `debian_mail_maildomain` overrides it, without both it is `localdomain`,
- if `debian_mail_accounts` is not set, the role creates the account `site` from `site_mail_smtp_host`, `site_mail_smtp_port`, `site_mail_from`, `site_mail_smtp_user` and `site_mail_smtp_password`, without them it sends to `localhost:25`.

### Mail

With `debian_mail_enable` the role installs [msmtp](https://marlam.de/msmtp/) as sendmail replacement (`msmtp`, `msmtp-mta`, `bsd-mailx`), writes `/etc/msmtprc` and `/etc/aliases`,
so mails of cron, unattended upgrades and other local services are delivered to a smarthost.
The service `msmtpd` of the package `msmtp-mta` is stopped and disabled, the SMTP relay runs as container with the role `mail_msmtp`.

```yaml
debian_mail_enable: true
debian_mail_accounts:
  # msmtpd container of the role mail_msmtp, no TLS and authentication
  - name: 'relay'
    smtp_host: '192.168.99.25'
    smtp_port: 2500
  - name: 'provider'
    smtp_host: 'smtp.example.org'
    smtp_port: 587
    tls: true
    starttls: true
    auth: true
    user: 'host42@example.org'
    password: "{{ vault_smtp_password }}"
    from: 'host42@example.org'
debian_mail_default_account: 'relay'
debian_mail_aliases:
  root: 'admin@example.org'
  default: 'admin@example.org'
```

- Every account needs `name` and `smtp_host`, accounts with `auth` need `user` and `password`. Optional keys are `smtp_port`, `from`, `tls`, `starttls` and `tls_certcheck`.
- `debian_mail_default_account` defaults to the first account.
- Envelope-from addresses are built as `user@debian_mail_maildomain` (`debian_mail_auto_from`, default `debian_hostname`), msmtp logs with the syslog facility `debian_mail_syslog` (`LOG_MAIL`).
- `debian_mail_aliases` maps local recipients to addresses, `default` applies to all recipients without own alias.
- `/etc/msmtprc` is readable for root only as soon as an account has a password, otherwise for all users. With passwords only root and services running as root can send mails.
- This replaces the client part of the former role `mail_msmtp`: `msmtp_accounts` is now `debian_mail_accounts` with the same keys,
  `msmtp_aliases` is now `debian_mail_aliases` (a mapping, written to `/etc/aliases`), `msmtp_auto_from`, `msmtp_maildomain` and `msmtp_syslog` are now `debian_mail_auto_from`, `debian_mail_maildomain` and `debian_mail_syslog`.

### Tests

The molecule scenario `default` runs the role in [tart](https://tart.run) VMs on a macOS controller.
The base VM is cloned for every platform and the clones are deleted afterwards, the base VM itself is never changed.
The playbooks creating and destroying the VMs are shared by all tart scenarios and live in `.molecule/tart/` in the repository root.

| Platform | Tested |
|---|---|
| `molecule-bootstrap-debian-minimal` | repositories including the removal of repositories that are not configured, packages, timezone, hostname and hosts with defaults |
| `molecule-bootstrap-debian-full` | PKI (CA certificate), mail with root forward, `/etc/hosts` managed by cloud-init (not generated), repositories that are not configured are kept (`debian_repositories_prune: false`), additionally storage (additional disk `/dev/vdb`) and bind mounts, networking (`dummy0`), accounts, logrotate, unattended upgrades and mail |

Requirements on the controller: `tart`, `sshpass` (`brew install hudochenkov/sshpass/sshpass`), `molecule` and the collection `ansible.posix`.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd bootstrap_debian
MOLECULE_TART_IMAGE='debian' molecule test
```

For mail, `prepare` starts an SMTP sink (`python3-aiosmtpd`) on `127.0.0.1:2525` as transient unit `molecule-smtp-sink`, `verify` sends a mail to `root` with `mail` and checks in the journal of the sink that it was delivered, then sends a mail with `msmtp -v` and checks in the SMTP dialog that the alias of `root` is used as recipient.

The test cases and expectations are defined in `molecule/default/test_cases.yml`.
If the additional disk does not appear as `/dev/vdb` in the VM, adjust the device there.
