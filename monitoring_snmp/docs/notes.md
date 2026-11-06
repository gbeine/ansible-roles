The role installs the [Net-SNMP](https://www.net-snmp.org/) agent `snmpd` and the SNMP tools from the Debian packages `snmpd` and `snmp` (Net-SNMP 5.9 on Debian 13) or on OpenWrt, see [OpenWrt](#openwrt).
The role detects OpenWrt itself with `raw` (`/etc/openwrt_release`), OpenWrt has no Python, plays for OpenWrt need `gather_facts: false`. On other systems the role gathers the minimal facts if they are missing.

On Debian the role writes the configuration of `snmpd` to these files:

| File | Content |
|---|---|
| `/etc/snmp/snmpd.conf` | All settings of `snmpd.conf` of the Debian package with description and default, additional settings and `includeDir /etc/snmp/snmpd.conf.d` |
| `/etc/snmp/snmpd.conf.d/<name>.conf` | One file for every config in `snmpd_configs` |
| `/etc/snmp/snmp.conf` | The configuration of the SNMP tools of the Debian package (`mibs :`) |
| `/etc/systemd/system/snmpd.service.d/50-monitoring-snmp.conf` | Dependencies of `snmpd` on other units from `snmpd_unit` |

### Settings

`snmpd_config` sets directives of `snmpd.conf`, it is a mapping of the names of the directives to values.
A list writes the directive once per value, e.g. for `view` or `rocommunity`, an empty list or an empty string comments the directive out.
`snmpd.conf` contains all settings of `snmpd.conf` of the Debian package with their description and default, a setting replaces the default completely.

```yaml
snmpd_config:
  sysLocation: 'Rack 1'
  sysContact: 'admin@example.org'
  agentaddress: 'udp:192.168.99.10:161,udp6:[fd00::10]:161'
  view:
    - 'systemonly included .1.3.6.1.2.1.1'
    - 'systemonly included .1.3.6.1.2.1.25.1'
    - 'all included .1'
  rocommunity: []
  rocommunity6: []
  rouser: []
  sysName: 'host42'
```

Directives that are not in `snmpd.conf` of the package, e.g. `sysName`, are written to the end of `snmpd.conf` as additional settings.

The settings and directives of the release are in `vars/settings-<release>.yml`, the settings with their descriptions from `snmpd.conf` of the Debian package,
the directives from snmpd.conf(5) and the include directives of snmp_config(5) of Net-SNMP.
The role fails before it changes anything if `snmpd_config` or `snmpd_configs` contain a directive unknown to the release, directives are case-sensitive.
If `snmpd_config` is no mapping, merging it with the default of the platform (`vars/Debian.yml`, `vars/OpenWrt.yml`) fails before anything changes.

### Defaults of the role

Without variables the role creates the same configuration as a fresh installation of Net-SNMP on Debian 13:

- `snmpd` listens on `127.0.0.1` and `[::1]` and is AgentX master,
- the community `public` reads the view `systemonly` (system and hrSystem groups) via IPv4 and IPv6,
- the SNMPv3 user `authPrivUser` reads `systemonly`, it is not created,
- `sysLocation` is `Sitting on the Dock of the Bay`, `sysContact` is `Me <me@example.org>`, `sysServices` is `72`.

### Configs

Every config in `snmpd_configs` needs `name` (letters, digits, `.`, `_` and `-`) and `settings` in the same format as `snmpd_config`,
the role writes it to `/etc/snmp/snmpd.conf.d/<name>.conf`, `snmpd` reads the configs after `snmpd.conf`.

```yaml
snmpd_configs:
  - name: 'access'
    settings:
      rocommunity: 'monitoring 192.168.99.0/24 -V all'
      rocommunity6: 'monitoring fd00::/64 -V all'
  - name: 'users'
    settings:
      createUser: "monitoring SHA-512 \"{{ vault_snmpd_auth_pass }}\" AES \"{{ vault_snmpd_priv_pass }}\""
      rouser: 'monitoring priv -V all'
  - name: 'extend'
    settings:
      disk: '/ 10%'
      extend: 'uptime /bin/cat /proc/uptime'
```

`snmpd.conf` and the configs contain communities and passwords, they belong to `root:Debian-snmp` with mode `0640`, `snmpd` reads them as `Debian-snmp` on a reload.

### Removing configs

With `snmpd_prune` (default `true`) the role removes all `*.conf` files in `/etc/snmp/snmpd.conf.d` which are not defined in `snmpd_configs`.

### Dependencies on other units

`snmpd_unit` makes `snmpd` depend on other systemd units, e.g. when it listens on an address of a podman network or a VPN, which exists only after the unit started:

```yaml
snmpd_config:
  agentaddress: 'udp:10.90.99.1:161,udp:10.8.0.1:161'
snmpd_unit:
  # Network podman99 of container_podman, the quadlet file podman99.network becomes the unit podman99-network.service
  requires: [ 'podman99-network.service', 'wg-quick@wg0.service' ]
  # A restart or stop of the VPN restarts or stops snmpd as well
  part_of: [ 'wg-quick@wg0.service' ]
```

| Key | Directive in `[Unit]` |
|---|---|
| `after` | `After` |
| `wants` | `Wants` |
| `requires` | `Requires` |
| `binds_to` | `BindsTo` |
| `part_of` | `PartOf` |

The units of all keys are written to `After` as well, so `snmpd` starts after them, without `After` systemd starts the units in parallel.

- `requires`: `snmpd` does not start without the unit and is stopped when the unit is stopped,
- `binds_to`: like `requires`, `snmpd` is stopped as well when the unit stops on its own, e.g. a failing VPN,
- `part_of`: a stop or restart of the unit stops or restarts `snmpd` as well, use it together with `requires` or `binds_to`,
- `wants`: the unit is started with `snmpd`, `snmpd` starts without it as well,
- `after`: the order only.

The role writes the dependencies to `/etc/systemd/system/snmpd.service.d/50-monitoring-snmp.conf`, the unit of the package and other drop-ins stay unchanged,
without dependencies in `snmpd_unit` the role removes the drop-in.
The keys and their directives are `common_globals__systemd_unit_directives`, every key needs a list of unit names with a type of `common_globals__systemd_unit_types` (`.service`, `.target`, `.mount`, …),
the role fails before it changes anything otherwise, e.g. for `podman99.network` instead of `podman99-network.service`.
After a change of the drop-in the role reloads the configuration of systemd, the dependencies take effect on the next start of `snmpd`, a running `snmpd` is not restarted for them.

### Changes, reloads and restarts

After a change the role reloads a running `snmpd` (`systemctl reload snmpd`, SIGHUP).
`snmpd` applies some directives on a start only, `agentaddress`, `master`, `agentXSocket`, `agentXPerms`, `engineID`, `engineIDType`, `engineIDNic` and `createUser`.
If one of them changed, the role restarts `snmpd` instead.

`snmpd` writes the SNMPv3 users to `/var/lib/snmp/snmpd.conf` on shutdown, the role removes these `usmUser` lines while `snmpd` is stopped,
so changed passwords of `createUser` take effect. Users created with `snmpusm` are removed as well.

`snmpd` has no test of the configuration, after the reload or restart the role checks that `snmpd` is running
and that the journal contains no errors or warnings about lines of the configuration files.

### OpenWrt

On OpenWrt the init script of snmpd creates its configuration from the UCI configuration `/etc/config/snmpd`.
The role uses the same variables as on Debian, `snmpd_config` and `snmpd_configs` with directives of `snmpd.conf`, and translates them to UCI sections.
The settings of all configs are added to `snmpd_config`, lists are appended, every setting replaces the default of `vars/OpenWrt.yml` completely.

Without variables the role creates the configuration of the former default of the role `bootstrap_openwrt`:

- `snmpd` listens on `UDP:161,UDP6:161` and is AgentX master on `/var/run/agentx.sock`,
- the communities `public` (read-only, everywhere) and `private` (read-write, localhost) via IPv4 and IPv6 with the view `all` (`.1`),
- `sysLocation` is `office`, `sysContact` is `bofh@example.com`, `sysName` is `HeartOfGold`,
- `exec filedescriptors /bin/cat /proc/sys/fs/file-nr`, `engineIDType 3` with `engineIDNic eth0`.

The role transforms the settings into a list of UCI sections with the same structure as `bootstrap_openwrt__snmpd` of the role `bootstrap_openwrt`
(`type`, optional `name`, `find` and `options`) and processes it like `bootstrap_openwrt` did.
Names and `find` follow the default configuration of OpenWrt, without variables the list is identical to the former `bootstrap_openwrt__snmpd_default`.

| Directive | UCI section | Name | find |
|---|---|---|---|
| `agentaddress` (values joined with `,`) | `agent` | unnamed | all options |
| `master agentx`, `agentXSocket` (without `master agentx` no AgentX) | `agentx` | unnamed | all options |
| `sysLocation`, `sysContact`, `sysName`, `sysServices`, `sysDescr`, `sysObjectID` | `system` | unnamed | `sysName`, without it all options |
| `com2sec`, `com2sec6` | `com2sec`, `com2sec6` | community, with `6` for `com2sec6` | `secname` |
| `group` | `group` | `<group>_<version>` | `group`, `version` |
| `view` | `view` | viewname | `viewname` |
| `access` (a context `""` becomes `none`) | `access` | `<group>_access` | `group` |
| `rocommunity`, `rwcommunity`, `rocommunity6`, `rwcommunity6` `<community> [<source> [<oid>]]` | `access_default`, `access_HostIP` (source `address/mask`) or `access_HostName` | unnamed | all options |
| `createUser` with `rouser` or `rwuser` | `v3` | unnamed | `username` |
| `exec`, `extend` | `exec`, `extend` | unnamed | `name` |
| `pass`, `pass_persist` | `pass` | unnamed | `miboid` |
| `disk` | `disk` | unnamed | `partition` |
| `engineID`, `engineIDType`, `engineIDNic` | `engineid` | unnamed | `engineidtype`, without it all options |
| `trapsink`, `trap2sink`, `informsink` | same type | unnamed | `host` |
| `trapcommunity`, `authtrapenable`, `v1trapaddress`, `trapsess` | same type | unnamed | all options |
| always | `snmpd` | `general` | `enabled 1` |

The section `general` gets `enabled 1` and three options derived from the settings:
`ip_protocol` (`ipv4`, `ipv6` or `ipv4/ipv6` from the transports of `agentaddress`), `snmp_port` (the port of the first `agentaddress`, else `161`)
and `snmp_version` (`v3` with only `usm` groups or only SNMPv3 users, `v1/v2c/v3` with `usm` groups or SNMPv3 users besides v1 or v2c groups, else `v1/v2c`).

A name that is taken by an earlier section of the list or is no valid UCI name leaves the section unnamed, all its options find it
(e.g. a second `com2sec` with the community `public`). Unnamed sections of the same type need different values for `find`.

The init script of OpenWrt supports less than `snmpd.conf`, the role fails before it changes anything for other directives (e.g. `proc`, `load`, `includeDir`),
for options of directives (e.g. `rocommunity … -V view`, `rouser … -V view`, `createUser -e`), for `disk` without size,
for users of `createUser` without `rouser` or `rwuser` and the reverse, and for passwords with less than 8 characters.
Templates in the settings and configs (e.g. `{{ netmask | ipv4_netmask2prefixlength }}` of `common_filters`) are rendered completely
before the translation, a failing template (e.g. an unknown filter) stops the role at `Render the settings and configs`;
inside the translation ansible-core would drop such a directive silently and prune would delete its sections.
The default variant `nossl` is built without OpenSSL, it supports the auth types `MD5` and `SHA` without privacy (at most the level `auth`).
The auth types `SHA-224` to `SHA-512` and the privacy types `DES`, `AES`, `AES-192` and `AES-256` need `snmpd_ssl: true`, the role fails for other types.
`snmpd_unit` is not supported on OpenWrt, procd has no dependencies on other units.

```yaml
# SHA-512 and AES need the ssl variant
snmpd_ssl: true
snmpd_config:
  sysLocation: 'Rack 1'
  com2sec: [ 'ro 192.168.99.0/24 monitoring' ]
  com2sec6: []
  group: [ 'monitoring v2c ro' ]
  access: [ 'monitoring "" any noauth exact all none none' ]
snmpd_configs:
  - name: 'users'
    settings:
      createUser: "monitoring SHA-512 \"{{ vault_snmpd_auth_pass }}\" AES \"{{ vault_snmpd_priv_pass }}\""
      rouser: 'monitoring priv'
```

- The role installs `snmp-mibs`, `snmpd-nossl` and `snmp-utils-nossl`, with `snmpd_ssl: true` `snmpd-ssl` and `snmp-utils-ssl`, and removes the other variant.
- With `snmpd_prune` (default `true`) the role removes all sections of `/etc/config/snmpd` that are neither declared by name nor found by `find`.
- Before a commit the role stores the configuration before the change on the controller in `<playbook_dir>/backups/<inventory_hostname>/snmpd`, secrets are redacted.
- After a change of the configuration or the packages the role restarts snmpd.

### Migration

| Former variable | Now |
|---|---|
| `snmpd_sys_location`, `snmpd_sys_contact`, `snmpd_sys_services` | `sysLocation`, `sysContact`, `sysServices` in `snmpd_config` |
| `snmpd_master` | `master` in `snmpd_config` |
| `snmpd_agentaddress` (list) | `agentaddress` in `snmpd_config`, a string like `127.0.0.1,[::1]` |

The defaults of the former role are the defaults of Debian 13 as well.

The role `bootstrap_openwrt` does not configure snmpd any longer:

| Former variable of `bootstrap_openwrt` | Now |
|---|---|
| `openwrt_snmpd_enable: true` | run this role on the device |
| `openwrt_snmpd` (UCI sections) | `snmpd_config` and `snmpd_configs` with directives, see [OpenWrt](#openwrt) |
| `openwrt_snmpd_ssl` | `snmpd_ssl` |
| `openwrt_snmpd_prune` | `snmpd_prune` |
| `openwrt_snmpd_redact_keys` | removed, the secrets are always redacted |

Example, these settings create the sections `@agent[0]`, `@agentx[0]`, `public` (`com2sec`), `@com2sec[1]` (localhost), `public_v1`, `public_v2c`,
`all`, `public_access`, `@system[0]`, `@exec[0]`, `@engineid[0]` and `general` of a former `openwrt_snmpd`:

```yaml
snmpd_config:
  com2sec: [ 'ro 172.21.110.0/24 public', 'ro localhost public' ]
  com2sec6: []
  group: [ 'public v1 ro', 'public v2c ro' ]
  access: [ 'public "" any noauth exact all none none' ]
  sysContact: 'root@example.org'
  sysName: "{{ inventory_hostname }}"
```

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The base VM is cloned for every platform and the clones are deleted afterwards, the base VM itself is never changed.
The playbooks creating and destroying the VMs are shared by all tart scenarios and live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-snmp-default` | No variables, the effective settings of `snmpd.conf` match a fresh installation of Debian 13, `public` reads the view `systemonly` only |
| `molecule-snmp` | Own settings, the community `public` and the user `authPrivUser` removed, configs with a community, an SNMPv3 user and an extend command, `snmpd` requires and is part of the unit `molecule-vpn.service` |

`prepare` creates a config in `/etc/snmp/snmpd.conf.d` that is not managed by the role and the oneshot unit `molecule-vpn.service` standing in for a VPN.
`side_effect` changes the community and checks that `snmpd` is reloaded, not restarted, changes the passwords of the SNMPv3 user and checks that `snmpd` is restarted,
restarts `molecule-vpn.service` and checks that `snmpd` is restarted, stops it and checks that `snmpd` is stopped,
then runs the role with an unknown directive and with `podman99.network` as dependency and checks that the role fails at the validation and the configuration files and the drop-in are unchanged (tasks marked `expect ERROR`).
`verify` checks the generated files, their owner and mode, the removal of the unmanaged config, the dependencies of `snmpd` in `systemctl show`, the listening addresses, the AgentX socket
and reads objects with the communities and the SNMPv3 user, the former community and passwords are rejected.

Requirements on the controller: `tart`, `sshpass` (`brew install hudochenkov/sshpass/sshpass`) and `molecule`.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd monitoring_snmp
MOLECULE_TART_IMAGE='debian' molecule test
```

The molecule scenario `openwrt` runs the role in two clones of the tart VM `openwrt-base` (OpenWrt with `apk`, SSH login as `root` with password), the base VM is never changed.

| Platform | Test case |
|---|---|
| `molecule-snmp-openwrt-default` | No variables, the former default of `bootstrap_openwrt`: `public` and `private` read sysName and sysLocation, a wrong community gets no answer, the exec entry `filedescriptors`, the packages of the nossl variant |
| `molecule-snmp-openwrt` | Own settings with the community `molecule-ro`, `public` and `private` are rejected, `snmpd_ssl: true` with the packages of the ssl variant, an SNMPv3 user with authPriv (SHA-512, AES) reads the output of an extend command |

`side_effect` runs the role with `proc`, which OpenWrt does not support, with SHA-512 and AES without `snmpd_ssl` and with an unknown filter in `com2sec`, and checks that the role fails at the validation and `/etc/config/snmpd` is unchanged (tasks marked `expect ERROR`).
The collection `community.openwrt` is required on the controller.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_OPENWRT_IMAGE` | `openwrt-base` | Base VM that is cloned |
| `MOLECULE_TART_OPENWRT_PASSWORD` | `OpenWRT` | Password of `root`, used to install the SSH key |

```shell
cd monitoring_snmp
molecule test -s openwrt
```
