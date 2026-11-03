The role provides the settings of the site, values used by several roles and independent of the operating system, e.g. the directory of the PKI realms or the SMTP host.
It has no tasks, it only resolves the inventory variables `site_*` with their defaults to `common_globals__*`.

### Naming scheme

| Level | Scheme | Example |
|---|---|---|
| Inventory, global for the site | `site_<area>_<name>` | `site_pki_realms_dir`, `site_mail_smtp_host` |
| Resolved value, used by roles | `common_globals__<area>_<name>` | `common_globals__pki_realms_dir` |
| Specific to a role | `<role>_<name>`, resolved as `<role>__<name>` | `debian_mail_accounts`, `bootstrap_debian__mail_accounts` |

Roles never read the `__` variables of another role, except `common_globals__*`.
A role may make a site setting overridable with a variable of its own, e.g. `postsrsd_domain | default(common_globals__mail_domain)`.

### Usage

Roles using site settings list the role as dependency in `meta/main.yml`, the defaults are then available in the play:

```yaml
dependencies:
  - role: 'common_globals'
```

Site settings are set once in the inventory, e.g. in `group_vars/all`:

```yaml
site_timezone: 'Europe/Berlin'
site_ntp_sources:
  - type: 'server'
    address: 'ntp1.example.org'
    options: [ 'iburst' ]
  - type: 'pool'
    address: '0.de.pool.ntp.org'
    options: [ 'iburst' ]
site_pki_ca_certificates: [ 'example-ca.crt' ]
site_mail_domain: 'example.org'
site_mail_root_forward: 'admin@example.org'
site_mail_smtp_host: 'smtp.example.org'
```

`site_ntp_sources` are the time sources of the site, NTP clients and servers use them, e.g. `bootstrap_debian` (`systemd-timesyncd`) and `bootstrap_openwrt` (`sysntpd`).
Every entry has `type` (`server` or `pool`, like the directives of chrony and ntpsec), `address` (hostname or IP address) and optional `options` (e.g. `iburst`).
Without `site_ntp_sources` the servers of the PTB (`ptbtime1.ptb.de` to `ptbtime3.ptb.de`) and the German pool (`0.de.pool.ntp.org` to `3.de.pool.ntp.org`) are used.

The operating system specific parts are done by the bootstrap roles, e.g. `bootstrap_debian` installs the PKI packages, the CA certificates from `<site_pki_secrets_dir>/ca-certificates` and writes `/root/.forward`.

### Migration

The role replaces the roles `pki_common`, `mail_common` and `ntp_common`, the tasks of `pki_common` and `mail_common` moved to `bootstrap_debian`.

| Before | Now |
|---|---|
| `bootstrap_timezone__timezone`, `timezone` of the former role `bootstrap_timezone` | `site_timezone` (IANA name, e.g. `Europe/Berlin`) |
| `pki_realms` | `site_pki_realms` |
| `pki_ca_certificates` | `site_pki_ca_certificates` |
| `pki_dhparams_size` | removed, it was not used |
| `mail_domain`, `mail_root_forward`, `mail_from` | `site_mail_domain`, `site_mail_root_forward`, `site_mail_from` |
| `mail_smtp_host`, `mail_smtp_port`, `mail_smtp_user`, `mail_smtp_password` | `site_mail_smtp_host`, `site_mail_smtp_port`, `site_mail_smtp_user`, `site_mail_smtp_password` |
| `pki_common__*` in other roles | `common_globals__pki_*` |
| `mail_common__*` in other roles | `common_globals__mail_*` |
| dependency on `pki_common` or `mail_common` | dependency on `common_globals` |
| `ntp_server`, `ntp_pool` with `hostname` and `options` | `site_ntp_sources` with `type` (`server` or `pool`), `address` and `options` |
| `ntp_use_pool` | removed, pools are used if `site_ntp_sources` contains entries with `type: 'pool'` |
| `ntp_hwclockfile`, `ntp_ntpsigndsocket` | removed, they were not used |
| `ntp_common__*` in other roles | `common_globals__ntp_sources` |
| dependency on `ntp_common` | dependency on `common_globals` |
