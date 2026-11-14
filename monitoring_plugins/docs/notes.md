The role installs additional plugins for Icinga 2 that are not part of the Debian packages of the monitoring plugins,
or links plugins of Debian packages that are not installed into the plugin directory by default.
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
| `logfiles` | link to `check_logfiles` | none, see the ITL | |
| `mem` | `check_mem.pl` | none, see the ITL | |
| `nginx` | `check_nginx_status.pl` | `nginx-status` | |
| `pass_alive` | `check_pass_alive` | `pass-alive` | yes |
| `pgactivity` | `check_pgactivity.pl` | `pgactivity` | |
| `phpfpm` | `check_phpfpm_status.pl` | `php-fpm-status` | |
| `printer_snmp` | `check_printer_snmp.py` | `printer_snmp` | |
| `pushover` | `pushover.sh` | `push-host-notification`, `push-service-notification` | |
| `raid` | link to `check_raid` | `raid` | `dmsetup` |
| `reboot` | `check_reboot` | `reboot` | |
| `rocketchat` | `notify_rocketchat` (amd64, arm64, arm) | `rocketchat` | |
| `running_kernel` | link to `check_running_kernel` | none, see the ITL | |
| `smart` | `check_smart.pl` of `monitoring-plugins-check-smart` | `sudo-smartpl` | `check_smart.pl`, `smartctl` |
| `systemd` | link to `check_systemd` | none, see the ITL | |
| `tls_cert` | `check_tls_cert.py` | `tls_cert` | |

The role fails before it changes anything if `monitoring_plugins` contains an unknown plugin.
The plugins, their files, configurations and sudoers entries are listed in `vars/main.yml`, the packages in `vars/Debian-13.yml`.

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

Plugins for MariaDB or MySQL of the Debian packages read `~nagios/.my.cnf`, the role writes it if `monitoring_plugins_mysql_credentials` is set:

```yaml
monitoring_plugins_mysql_credentials:
  user: 'monitoring'
  password: 'secret'
```

All credential files belong to the Icinga user and have mode `0400`.

### Pruning

With `monitoring_plugins_prune: true` (default) the role removes the plugins, links, configurations and sudoers entries of all plugins of the role
that are not in `monitoring_plugins`, the credential files that are not configured and files of earlier versions of the role
(`check_ide_smart.conf`, `check_smartpl.conf`, `notifiy_rocketchat.conf`, `check_tls_cert`, `pushover.pl`, sudoers `icinga-run-ide-smart` and `icinga-run-podman`).
Packages are never removed.
Files of other roles or plugins not known to the role are not touched.

### Migration

| Before | Now |
|---|---|
| `monitoring_check_<name>: true` | `<name>` in `monitoring_plugins` |
| `monitoring_check_docker`, `monitoring_check_podman` | `container_stats_docker`, `container_stats_podman` |
| `monitoring_check_ide_smart` | `smart`, only `check_smart.pl` (`sudo-smartpl`), Debian 13 does not ship `check_ide_smart` anymore, `sudo-smart` is gone |
| `monitoring_check_phpfpm`, `monitoring_check_nginx` | `phpfpm`, `nginx` |
| `monitoring_pushover`, `monitoring_rocketchat` | `pushover`, `rocketchat` |
| `monitoring_credentials_mariadb*`, `monitoring_credentials_mysql*` | `monitoring_plugins_mysql_credentials` with `user` and `password` |
| `monitoring_credentials_postgresql_*` | `monitoring_plugins_postgresql_credentials` with `host`, `port`, `user` and `password` |

Fixed errors of the old role:

- `tls_cert` was never installed, the package list overwrote the switch, the plugin is now installed as `check_tls_cert.py` as the `CheckCommand` expects,
- `pushover` installed `pushover.pl`, the `NotificationCommand` runs `pushover.sh`,
- the configuration of `rocketchat` was written to `notifiy_rocketchat.conf`, now `rocketchat.conf`,
- sudoers entries use the Icinga user (`icinga_user`) instead of a fixed `nagios`, the entry of the podman plugin is now `icinga-run-container-stats-podman`.

### Tests

The molecule scenario `default` uses tart with two VMs, both with Icinga 2 installed in `prepare`:

- `molecule-plugins-default` runs the role without variables, only the directories are created,
- `molecule-plugins` installs all plugins with credentials, `side_effect` removes `pushover` and `reboot` again.

`verify` checks that exactly the expected files, links, configurations and sudoers entries exist, the credential files, `visudo -c`,
the sudo commands of the Icinga user, the syntax and dependencies of the plugins (`perl -c`, `bash -n`, `--help`),
runs `check_mem.pl` and `check_systemd` as the Icinga user,
runs `check_printer_snmp.py` as the Icinga user against `127.0.0.1` without SNMP agent, it has to return UNKNOWN with an SNMP error,
which shows that `snmpwalk` is installed, and validates the Icinga configuration with `icinga2 daemon -C`.

```
cd monitoring_plugins
MOLECULE_TART_IMAGE='debian' molecule test
```
