The role installs [fail2ban](https://github.com/fail2ban/fail2ban) from the Debian packages (fail2ban 1.1 on Debian 13) together with `nftables`, `python3-systemd`, `sqlite3` and `whois`.
It does not change the configuration files of the package, all settings are written to `.local` files, which fail2ban reads after the `.conf` files:

| File | Content |
|---|---|
| `/etc/fail2ban/fail2ban.local` | All settings of the daemon from `fail2ban.conf` with description and default |
| `/etc/fail2ban/jail.local` | All settings of the section `[DEFAULT]` from `jail.conf` with description and default |
| `/etc/fail2ban/jail.d/<name>.local` | One file for every jail in `fail2ban_jails` |
| `/etc/fail2ban/filter.d/<name>.local` | One file for every filter in `fail2ban_filters` |

### Settings

`fail2ban_settings` sets settings of the daemon, `fail2ban_jail_defaults` settings of the section `[DEFAULT]` of the jails.
Both are mappings of the names of the settings to values, `fail2ban.local` and `jail.local` contain all settings of the release with their defaults,
settings without value or commented out in the files of the package stay commented out until they are set.
`true` and `false` are written as `true` and `false`, lists are written as multiline values, e.g. for `ignoreip` or actions.

```yaml
fail2ban_settings:
  loglevel: 'NOTICE'
  logtarget: 'SYSTEMD-JOURNAL'
fail2ban_jail_defaults:
  bantime: '1h'
  bantime.increment: true
  bantime.maxtime: '1w'
  ignoreip: [ '127.0.0.1/8', '::1', '192.168.99.0/24' ]
  destemail: 'admin@example.org'
  action: '%(action_mwl)s'
```

The settings of the daemon and the release are in `vars/settings-<release>.yml`, generated from `fail2ban.conf` and `jail.conf` of fail2ban.
The role fails before it changes anything if `fail2ban_settings` contains a setting unknown to the release.
`fail2ban_jail_defaults` may contain additional settings, e.g. `blocklist_de_apikey` or other parameters of actions, they are written to the end of `jail.local`.

### Defaults of the role

Without variables the role creates the same configuration as a fresh installation of fail2ban on Debian 13, the defaults of `jail.conf` and `jail.d/defaults-debian.conf`:

- `banaction` is `nftables` and `banaction_allports` is `nftables[type=allports]`,
- the jail `sshd` is enabled with `backend = systemd` and `journalmatch = _SYSTEMD_UNIT=ssh.service + _COMM=sshd`.

The role removes `jail.d/defaults-debian.conf`, its content comes from the defaults of the role.
Setting `fail2ban_jails` replaces the default jail `sshd`, add it to the list to keep it.

### Jails

Every jail in `fail2ban_jails` needs `name`, `enabled` defaults to `true`, `settings` contains the settings of the jail:

```yaml
fail2ban_jails:
  - name: 'sshd'
    settings:
      backend: 'systemd'
      journalmatch: '_SYSTEMD_UNIT=ssh.service + _COMM=sshd'
      maxretry: 3
  - name: 'nginx-http-auth'
    settings:
      backend: 'polling'
      port: 'http,https'
      logpath: '/var/log/nginx/error.log'
  - name: 'recidive'
    settings:
      backend: 'polling'
      logpath: '/var/log/fail2ban.log'
      bantime: '1w'
      findtime: '1d'
```

Jails reading log files need a backend other than `systemd`, e.g. `polling`, and the log file has to exist when fail2ban starts.

### Filters

Every filter in `fail2ban_filters` needs `name` and `definition.failregex`, `includes` and `init` are optional.
A filter with the name of a filter of the package overrides its settings.

```yaml
fail2ban_filters:
  - name: 'myapp'
    includes:
      before: 'common.conf'
    definition:
      datepattern: '^%%Y-%%m-%%d %%H:%%M:%%S'
      failregex:
        - '^ Failed login for \S+ from <HOST>$'
        - '^ Blocked request from <HOST>$'
      ignoreregex: ''
```

### Removing jails and filters

With `fail2ban_prune` (default `true`) the role removes all `*.local` files in `jail.d` and `filter.d` which are not defined in `fail2ban_jails` and `fail2ban_filters`.

### Changes and reloads

After a change the role tests the configuration with `fail2ban-client --test` and fails if it is invalid.
A running fail2ban is reloaded with `fail2ban-client reload`, so current bans stay active.

### Migration

| Former variable | Now |
|---|---|
| `fail2ban_ignoreip` | `ignoreip` in `fail2ban_jail_defaults` |
| `fail2ban_bantime`, `fail2ban_findtime`, `fail2ban_maxretry` | `bantime`, `findtime`, `maxretry` in `fail2ban_jail_defaults` |
| `fail2ban_overrides` | `fail2ban_jail_defaults` |
| `fail2ban_jails` | `fail2ban_jails`, the settings of a jail are now in `settings`, `enabled` is optional |
| `fail2ban_filter` | `fail2ban_filters`, the settings are now in `definition`, `variables` are settings with a leading `_` |

Former versions of the role set `bantime` to `1d` and `ignoreip` to `127.0.0.1/8 ::1`, the role now uses the defaults of fail2ban (`10m`, `ignoreip` commented out), set them in `fail2ban_jail_defaults` to keep them.
Jails and filters were written to `jail.d/<name>.conf` and `filter.d/<name>.conf`, they are now written to `.local` files, remove the former `.conf` files.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The base VM is cloned for every platform and the clones are deleted afterwards, the base VM itself is never changed.
The playbooks creating and destroying the VMs are shared by all tart scenarios and live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-fail2ban-default` | No variables, the effective settings of the jail `sshd` match a fresh installation of Debian 13 |
| `molecule-fail2ban` | Own settings, the jail `sshd` and a jail `molecule` with an own filter on a log file |

`prepare` creates the log file of the jail `molecule`.
`side_effect` changes `findtime` of the jail `molecule` and checks that fail2ban is reloaded, not restarted.
`verify` checks the generated files, the removal of `defaults-debian.conf`, the jails and the effective settings of the jail `sshd` with `fail2ban-client`,
and on `molecule-fail2ban` writes failed logins to the log file and checks that the address is banned in fail2ban and in nftables.

Requirements on the controller: `tart`, `sshpass` (`brew install hudochenkov/sshpass/sshpass`) and `molecule`.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd security_fail2ban
MOLECULE_TART_IMAGE='debian' molecule test
```
