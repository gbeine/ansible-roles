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
- Repositories, packages, timezone and hostname/hosts are always configured. Storage and accounts run when their lists are not empty. Networking, PKI, NTP, SSH, logrotate, unattended upgrades and mail have to be enabled with `debian_networking_enable`, `debian_pki_enable`, `debian_ntp_enable`, `debian_sshd_enable`, `debian_logrotate_enable`, `debian_unattended_upgrades_enable` and `debian_mail_enable`, because they overwrite system configuration files or replace installed services.
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
- This role replaces the former roles `bootstrap_hosts`, `bootstrap_logrotate`, `bootstrap_networking`, `bootstrap_packages`, `bootstrap_repositories`, `bootstrap_storage`, `bootstrap_timezone`, `bootstrap_accounts`, `apt_common`, `apt_unattended_upgrades`, `ntp_common`, `ntp_timesyncd` and `systemd_timesyncd`. The inventory variables were renamed:

| Former variable | New variable |
|---|---|
| `packages` | `debian_packages` |
| `local_packages` | `debian_local_packages` |
| `timezone` | `site_timezone` of `common_globals`, `debian_timezone` overrides it for a host |
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
| `security_sshd_listen` (role `security_ssh`) | `debian_sshd.config.ListenAddress`, see SSH |
| `timesyncd_ntp` (role `systemd_timesyncd`), `ntp_server` (role `ntp_common`) | `site_ntp_sources` of `common_globals` with `type: 'server'`, `debian_ntp_sources` overrides it for a host |
| `timesyncd_fallback_ntp`, `ntp_pool` | entries with `type: 'pool'` in `site_ntp_sources` or `debian_ntp_sources` |
| `timesyncd_root_distance_max_sec`, `timesyncd_poll_interval_min_sec`, `timesyncd_poll_interval_max_sec`, `timesyncd_connection_retry_sec`, `timesyncd_save_interval_sec` | `debian_ntp_root_distance_max_sec`, `debian_ntp_poll_interval_min_sec`, `debian_ntp_poll_interval_max_sec`, `debian_ntp_connection_retry_sec`, `debian_ntp_save_interval_sec` |
| `bootstrap_<area>_enable` (role `bootstrap`) | `debian_networking_enable`, `debian_logrotate_enable`, `debian_unattended_upgrades_enable` |

### Site settings

The role depends on `common_globals`, which provides the settings of the site (`site_*`), and does the Debian specific parts, which were done by the roles `pki_common` and `mail_common` before.

The time zone is `site_timezone` (default `Etc/UTC`), `debian_timezone` overrides it for a host.

With `debian_pki_enable: true` the role installs the PKI packages `acl`, `ca-certificates`, `openssl` and `ssl-cert`
and copies the CA certificates in `site_pki_ca_certificates` from `<site_pki_secrets_dir>/ca-certificates` (default `<inventory_dir>/secrets/ca-certificates`) to `/usr/local/share/ca-certificates`,
`update-ca-certificates` runs if one changed.

With `debian_mail_enable: true` the site settings are the defaults of the mail configuration:

- `site_mail_root_forward` is the alias of `root`, `debian_mail_aliases` overrides it,
- with `debian_mail_root_forward_enable: true` the role writes `site_mail_root_forward` to `/root/.forward` as well, the role fails if `site_mail_root_forward` is not set,
- `site_mail_domain` is the `maildomain`, `debian_mail_maildomain` overrides it, without both it is `localdomain`,
- if `debian_mail_accounts` is not set, the role creates the account `site` from `site_mail_smtp_host`, `site_mail_smtp_port`, `site_mail_from`, `site_mail_smtp_user` and `site_mail_smtp_password`, without them it sends to `localhost:25`.

### NTP

With `debian_ntp_enable: true` the role installs `systemd-timesyncd` as NTP client, the default of Debian and of the Debian images of Hetzner.
`chrony` and `ntpsec` conflict with `systemd-timesyncd`, apt removes them if they are installed.

The sources are `site_ntp_sources` of `common_globals`, `debian_ntp_sources` overrides them for a host.
Every entry needs `type` (`server` or `pool`) and `address`, `options` (e.g. `iburst`) are used by NTP servers, but not by `systemd-timesyncd`.
The role writes the drop-in `/etc/systemd/timesyncd.conf.d/50-bootstrap-debian.conf`, the `/etc/systemd/timesyncd.conf` of the package or of the provider (e.g. Hetzner) stays unchanged, the drop-in overrides it:

- the addresses of the entries with `type: 'server'` become `NTP=`,
- the addresses of the entries with `type: 'pool'` become `FallbackNTP=`, `systemd-timesyncd` has no pools and uses them only if no server is reachable,
- without entries of a type the setting is empty, without pools `systemd-timesyncd` has no fallback.

```yaml
debian_ntp_enable: true
site_ntp_sources:
  - type: 'server'
    address: 'ntp1.example.org'
    options: [ 'iburst' ]
  - type: 'pool'
    address: '0.de.pool.ntp.org'
debian_ntp_poll_interval_min_sec: 64
```

- `debian_ntp_root_distance_max_sec`, `debian_ntp_poll_interval_min_sec`, `debian_ntp_poll_interval_max_sec`, `debian_ntp_connection_retry_sec` and `debian_ntp_save_interval_sec` are seconds and only written if set, otherwise the defaults of systemd apply.
  The former role `systemd_timesyncd` always wrote them, with `ConnectionRetrySec=20` instead of the systemd default 30.
- The role validates the sources and the seconds before any change, `debian_ntp_poll_interval_min_sec` must not be greater than `debian_ntp_poll_interval_max_sec`.
- `systemd-timesyncd` is restarted if the drop-in changed.

### SSH

With `debian_sshd_enable` the role installs `openssh-server` and `openssh-client`, writes the options of sshd and of the ssh client to drop-ins
and the authorized keys of users. `/etc/ssh/sshd_config` and `/etc/ssh/ssh_config` of the package stay unchanged.

```yaml
debian_sshd_enable: true
debian_sshd:
  config:
    PermitRootLogin: 'prohibit-password'
    PasswordAuthentication: false
    ClientAliveInterval: 30
    ListenAddress: [ '192.168.99.10', '2001:db8::10' ]
  client:
    ServerAliveInterval: 60
  authorized_keys:
    admin:
      - 'ssh-ed25519 AAAAC3Nza... admin@example.org'
    backup: []
```

- `debian_sshd` is merged recursively into the default (`config`, `client` and `authorized_keys` empty), so only the parts in use have to be written.
- `config` holds options of sshd, written to `/etc/ssh/sshd_config.d/00-ansible.conf`, `client` options of ssh, written to `/etc/ssh/ssh_config.d/00-ansible.conf`.
  `sshd_config` and `ssh_config` of Debian include these directories before their own options and sshd and ssh use the first value of an option,
  `00-` sorts before the drop-ins of other packages (e.g. `50-cloud-init.conf`), so the options of the role take precedence.
- The values are written by type: a string or number writes `Option value`, a list one line per element, `true` and `false` write `yes` and `no`,
  `null` removes the option. Without options the files are empty, the role writes no defaults.
- `Include` and `Match` (and `Host` for the client) are not allowed, they change the meaning of the following options of the file.
- `authorized_keys` maps users to their keys, written to `~/.ssh/authorized_keys` of the home in `/etc/passwd`, owned by the user with mode `0600` (`.ssh` with `0700`).
  An empty list removes the file, users that are not listed are not changed. The users have to exist, e.g. created with `debian_users`.
- The role checks the options and the keys before it changes anything, sshd (`sshd -t`) and ssh (`ssh -G`) check the files before they are replaced.
- sshd is reloaded if its options changed, running sessions are kept.
- This replaces the former role `security_ssh`: `security_sshd_listen` is now `ListenAddress` of `debian_sshd.config`,
  its default `0.0.0.0` and `::` is not written anymore, sshd listens on all addresses without `ListenAddress`.
  The files `/etc/ssh/sshd_config.d/sshd_config.conf` and `/etc/ssh/ssh_config.d/ssh_config.conf` of the former role are removed,
  sshd is reloaded instead of restarted.

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
| `molecule-bootstrap-debian-minimal` | repositories including the removal of repositories that are not configured, packages, timezone, hostname and hosts with defaults, no NTP drop-in without `debian_ntp_enable`, SSH without options (empty drop-ins, sshd listens on all addresses) |
| `molecule-bootstrap-debian-full` | PKI (CA certificate), mail with root forward, NTP client with servers, pool and poll interval of the site settings, `/etc/hosts` managed by cloud-init (not generated), repositories that are not configured are kept (`debian_repositories_prune: false`), additionally storage (additional disk `/dev/vdb`) and bind mounts, networking (`dummy0`), accounts, SSH with options of sshd and of the client and authorized keys (login with a key, removal of the keys of a user with an empty list), logrotate, unattended upgrades and mail |

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

For SSH, `prepare` stores the checksums of `sshd_config` and `ssh_config`, creates the file of the former role `security_ssh`,
on `molecule-bootstrap-debian-full` a key pair and a user `stale` with authorized keys, `converge` adds the public key to `debian_sshd.authorized_keys`.
`side_effect` runs the role with an unknown key in `debian_sshd`, `config` not a dictionary, `Match` and `Host`, invalid options, authorized keys of an unknown user
and an option unknown to sshd and checks that it fails with the expected message and the drop-ins are unchanged (tasks marked `expect ERROR`),
then it changes an option of sshd on `molecule-bootstrap-debian-full`.
`verify` checks the drop-ins (empty without options), that `sshd_config` and `ssh_config` are unchanged, that the file of `security_ssh` is removed,
the effective options of sshd (`sshd -T`) and of the client (`ssh -G`), the authorized keys and logs in with the key.

For mail, `prepare` starts an SMTP sink (`python3-aiosmtpd`) on `127.0.0.1:2525` as transient unit `molecule-smtp-sink`, `verify` sends a mail to `root` with `mail` and checks in the journal of the sink that it was delivered, then sends a mail with `msmtp -v` and checks in the SMTP dialog that the alias of `root` is used as recipient.

The test cases and expectations are defined in `molecule/default/test_cases.yml`.
If the additional disk does not appear as `/dev/vdb` in the VM, adjust the device there.
