The role installs additional plugins for Icinga 2 that are not part of the Debian packages of the monitoring plugins.
For every plugin it installs the needed packages, copies the plugin to the local plugin directory (`/usr/local/lib/nagios/plugins`),
writes the Icinga configuration (`CheckCommand` or `NotificationCommand`) to `/usr/local/etc/icinga2` and adds sudoers entries if the plugin needs root.

The role expects Icinga 2 to be installed, e.g. by `monitoring_icinga_agent`, which defines the constant `PluginLocalDir` and includes `/usr/local/etc/icinga2`.
It does not reload Icinga 2, the configuration becomes active on the next reload of Icinga 2.

### Plugins

`monitoring_plugins` is a list of the plugins to install:

```yaml
monitoring_plugins:
  - 'reboot'
  - 'systemd'
  - 'tls_cert'
  - 'pushover'
```

| Plugin | Installs | Icinga command | sudo |
|---|---|---|---|
| `borg_repository_status` | `check_borg_repository_status` | `borg-repository-status` | yes |
| `certexp` | `check_certexp.pl` | `certexp` | |
| `container_stats_docker` | `check_container_stats_docker.py` | `container-stats-docker`, `sudo-container-stats-docker` | |
| `container_stats_podman` | `check_container_stats_podman.py` | `container-stats-podman`, `sudo-container-stats-podman` | yes |
| `dsa` | `monitoring-plugins-contrib`, `openssl` and `libnet-dns-perl` | `dsa-*`, e.g. `dsa-cert-expire`, `dsa-entropy`, `dsa-soas` | |
| `logfiles` | `check_logfiles` of `monitoring-plugins-check-logfiles` | none, see the ITL | |
| `madrisan` | `monitoring-plugins-contrib` | `madrisan-*`, e.g. `madrisan-cpu`, `madrisan-memory`, `madrisan-network` | |
| `mariadb` | `monitoring-plugins-contrib` and `libmariadb3`, alias of `mysql` | none, see the ITL | |
| `mysql` | `monitoring-plugins-contrib` and `libmariadb3` | none, see the ITL | |
| `nginx` | `check_nginx_status.pl` | `nginx-status` | |
| `pass_alive` | `check_pass_alive` | `pass-alive` | yes |
| `pgactivity` | `check_pgactivity.pl` | `pgactivity` | |
| `phpfpm` | `check_phpfpm_status.pl` | `php-fpm-status` | |
| `printer_snmp` | `check_printer_snmp.py` | `printer_snmp` | |
| `pushover` | `pushover.sh` | `push-host-notification`, `push-service-notification` | |
| `raid` | `check_raid` of `monitoring-plugins-contrib` | `raid` | `dmsetup` |
| `reboot` | `check_reboot` | `reboot` | |
| `running_kernel` | `check_running_kernel` of `monitoring-plugins-contrib` | none, see the ITL | |
| `smart` | `check_smart.pl` of `monitoring-plugins-check-smart` | `sudo-smartpl` | `check_smart.pl`, `smartctl` |
| `systemd` | `check_systemd` of `monitoring-plugins-systemd` | none, see the ITL | |
| `tls_cert` | `check_tls_cert.py` | `tls_cert` | |

`check_memory` of madrisan (`madrisan-memory` of the plugin `madrisan`) is preferred to check the memory,
the former plugin `mem` with `check_mem.pl` is removed.

The plugins, their files, configurations and sudoers entries are listed in `monitoring_plugins__catalog` at the end of `defaults/main.yml`,
the packages in `vars/Debian-13.yml`.

### Icinga user and directories

The Icinga configuration and the credential files belong to `monitoring_plugins_user` (default `nagios`) and `monitoring_plugins_group`
(default the user), the sudoers entries are written for this user. The plugins are copied to `monitoring_plugins_local_dir`
(default `/usr/local/lib/nagios/plugins`), the Icinga configuration is written to `monitoring_plugins_etc_dir` (default `/usr/local/etc/icinga2`).

### Printer

`printer_snmp` checks the toner levels or the status of a printer with `snmpwalk` of the package `snmp`,
it reads the Printer-MIB (RFC 3805) and the Host-Resources-MIB (RFC 2790) with SNMP v1 or v2c.
The `CheckCommand` `printer_snmp` uses the address of the host and these variables:

- `printer_check` is mandatory, `toner` checks the toner levels, `status` the error flags of the printer
- `printer_toner` is `all` (default, the worst level wins) or a part of the name of a toner, e.g. `black`
- `printer_warning` and `printer_critical` are the levels of the toner in percent (default 10 and 5)
- `printer_status_critical` is a comma separated list of error flags causing CRITICAL, other flags cause WARNING
- `printer_status_ignore` is a comma separated list of error flags that are ignored
- `printer_community` (default `public`), `printer_snmp_version` (`1` or `2c`, default `2c`) and `printer_timeout` (default 5 seconds)
- `printer_address` overrides the address of the host

The error flags are `lowPaper`, `noPaper`, `lowToner`, `noToner`, `doorOpen`, `jammed`, `offline`, `serviceRequested`,
`inputTrayMissing`, `outputTrayMissing`, `markerSupplyMissing`, `outputNearFull`, `outputFull`, `inputTrayEmpty`
and `overduePreventMaintenance`. The toner levels are written as performance data in percent.

```
apply Service "printer-toner" {
  check_command = "printer_snmp"
  vars.printer_check = "toner"
  assign where host.vars.printer
}

apply Service "printer-status" {
  check_command = "printer_snmp"
  vars.printer_check = "status"
  vars.printer_status_critical = "noToner,jammed"
  vars.printer_status_ignore = "lowPaper"
  assign where host.vars.printer
}
```

### Credentials

`pgactivity` needs credentials for PostgreSQL, the role writes `~nagios/.pg_service.conf` with the service `nagios` and `~nagios/.pgpass`:

```yaml
monitoring_plugins_postgresql_credentials:
  host: 'localhost'   # default
  port: 5432          # default
  user: 'monitoring'
  password: 'secret'
```

The plugins for MariaDB or MySQL of the Debian packages (`mariadb` or `mysql`) read `~nagios/.my.cnf`,
the role writes it if `monitoring_plugins_mysql_credentials` is set and `mysql` or `mariadb` is in `monitoring_plugins`.
Without one of these plugins the credentials are ignored, they are neither checked nor written and an existing `.my.cnf` is removed when pruning:

```yaml
monitoring_plugins_mysql_credentials:
  user: 'monitoring'
  password: 'secret'
```

All credential files belong to the Icinga user and have mode `0400`. `:` and `\` in the fields of `.pgpass` are escaped as `\:` and `\\`.

### Validation

The role checks before any change:

- `monitoring_plugins` is a list of known plugins, `monitoring_plugins_prune` is a boolean
- `pgactivity` has user and password in `monitoring_plugins_postgresql_credentials`
- `monitoring_plugins_mysql_credentials` is a dictionary, with `mysql` or `mariadb` and credentials set it has user and password
- the credentials contain no line breaks

If `monitoring_plugins_postgresql_credentials` is no dictionary, merging it with the default fails before anything changes.

### Check mode

The role runs with `--check`, also on a host where it never ran, and reports the packages, the directories, the plugins,
the Icinga configuration, the sudoers entries and the credential files.

### Pruning

With `monitoring_plugins_prune: true` (default) the role removes the plugins, configurations and sudoers entries of all plugins of the role
that are not in `monitoring_plugins` and the credential files that are not configured or whose plugins are not selected.
Packages are never removed.
Files of other roles or plugins not known to the role are not touched.

### Migration

| Before | Now |
|---|---|
| `monitoring_check_<name>: true` | `<name>` in `monitoring_plugins` |
| `monitoring_check_docker`, `monitoring_check_podman` | `container_stats_docker`, `container_stats_podman` |
| `monitoring_check_ide_smart` | `smart`, only `check_smart.pl` (`sudo-smartpl`), Debian 13 does not ship `check_ide_smart` anymore, `sudo-smart` is gone |
| `monitoring_check_phpfpm`, `monitoring_check_nginx` | `phpfpm`, `nginx` |
| `monitoring_pushover` | `pushover` |
| `monitoring_rocketchat` | removed, see `rocketchat` below |
| `monitoring_credentials_mariadb*`, `monitoring_credentials_mysql*` | `monitoring_plugins_mysql_credentials` with `user` and `password`, only used with the plugin `mysql` or `mariadb` |
| `monitoring_credentials_postgresql_*` | `monitoring_plugins_postgresql_credentials` with `host`, `port`, `user` and `password` |
| `icinga_user`, `icinga_group` | `monitoring_plugins_user`, `monitoring_plugins_group` |
| `monitoring_plugin_local_dir`, `monitoring_plugin_etc_dir` | `monitoring_plugins_local_dir`, `monitoring_plugins_etc_dir` |
| `rocketchat` (`notify_rocketchat`) | removed, `rocketchat` is an unknown plugin now; remove `/usr/local/lib/nagios/plugins/notify_rocketchat` and `/usr/local/etc/icinga2/rocketchat.conf` by hand |
| `mem` (`check_mem.pl`) | removed, `madrisan` with `madrisan-memory` (`check_memory`), `mem` is an unknown plugin now; the role does not prune `check_mem.pl` anymore, remove `/usr/local/lib/nagios/plugins/check_mem.pl` by hand |

Fixed errors:

- a `:` or `\` in the credentials of PostgreSQL broke `.pgpass`, they are escaped now,
- `tls_cert` was never installed, the package list overwrote the switch, the plugin is now installed as `check_tls_cert.py` as the `CheckCommand` expects,
- `pushover` installed `pushover.pl`, the `NotificationCommand` runs `pushover.sh`,
- sudoers entries use the Icinga user (`monitoring_plugins_user`) instead of a fixed `nagios`, the entry of the podman plugin is now `icinga-run-container-stats-podman`.

### Tests

The molecule scenario `default` uses tart with two VMs, both with Icinga 2 installed in `prepare`:

- `molecule-plugins-default` runs the role without variables, only the directories are created,
- `molecule-plugins` installs all plugins with credentials, the password of PostgreSQL contains `:`,
  `side_effect` removes `pushover`, `reboot`, `mysql` and `mariadb` again, `.my.cnf` has to be removed with them.

`check` runs `converge` with `--check` on the new VMs.
Before the removal `side_effect` runs the role on `molecule-plugins` with `monitoring_plugins` not a list, an unknown plugin (`rocketchat`),
`monitoring_plugins_prune` not a boolean, `pgactivity` without password, the credentials of MySQL without password,
the credentials of PostgreSQL and MySQL not a dictionary and a line break in a password and checks that it fails with the expected message
and the configuration and `.pgpass` are unchanged (tasks marked `expect ERROR`).
`molecule-plugins-default` runs the role again, it must not write a plugin.

`verify` checks that exactly the expected files, configurations and sudoers entries exist, the credential files, the packages of `mysql`, `mariadb`, `dsa` and `madrisan`, `visudo -c`,
the sudo commands of the Icinga user, the syntax and dependencies of the plugins (`perl -c`, `bash -n`, `--help`),
runs `check_systemd` as the Icinga user,
runs `check_printer_snmp.py` as the Icinga user against `127.0.0.1` without SNMP agent, it has to return UNKNOWN with an SNMP error,
which shows that `snmpwalk` is installed, and validates the Icinga configuration with `icinga2 daemon -C`.

```
cd monitoring_plugins
MOLECULE_TART_IMAGE='debian' molecule test
```
