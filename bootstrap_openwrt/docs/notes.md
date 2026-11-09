### Time zone

The role depends on `common_globals` and takes the time zone of the site from `site_timezone` (IANA name, default `Etc/UTC`), `openwrt_timezone` overrides it for a host.
OpenWrt needs the time zone as POSIX string as well (option `timezone`, `zonename` is the IANA name),
the role knows the POSIX strings of `Etc/UTC` (`GMT0`, zonename `UTC`), the time zones of Central, Western and Eastern Europe
(e.g. `Europe/Berlin`, `Europe/London`, `Europe/Lisbon`, `Europe/Helsinki`), `America/New_York`, `America/Chicago`, `America/Denver`, `America/Los_Angeles`, `Asia/Tokyo` and `Australia/Sydney`, see `vars/main.yml`.
For other time zones set the POSIX string with `openwrt_timezone_posix`, e.g. the last line of `/usr/share/zoneinfo/<zone>`, the role fails before it changes anything otherwise.

```yaml
site_timezone: 'America/Sao_Paulo'
openwrt_timezone_posix: '<-03>3'
```

Without `site_timezone` the system section gets `timezone: 'GMT0'` and `zonename: 'UTC'` as before.

### NTP

The time sources are `site_ntp_sources` of `common_globals`, `openwrt_ntp_sources` overrides them for a device.
They become the list `server` of the section `timeserver` `ntp` of the default of `openwrt_system`.
`sysntpd` knows no pools, so the list contains the addresses of the entries with `type: 'server'` first, then those with `type: 'pool'`, `options` are not used.
The role validates the sources before it changes anything, every entry needs `type` (`server` or `pool`) and `address`.

```yaml
openwrt_ntp_sources:
  - type: 'server'
    address: '192.168.1.1'
  - type: 'pool'
    address: '0.openwrt.pool.ntp.org'
```

Without `site_ntp_sources` the defaults of the site are used (`ptbtime1.ptb.de` to `ptbtime3.ptb.de`, then `0.de.pool.ntp.org` to `3.de.pool.ntp.org`), before the role used `0.openwrt.pool.ntp.org` to `3.openwrt.pool.ntp.org`.
With `openwrt_system` the sections are taken as they are, the sources are not used then.

### Default for `openwrt_system`

```yaml
bootstrap_openwrt__system_default:
  - type: 'system'
    find: { compat_version: '1.1' }
    options:
      hostname: 'OpenWrt'
      timezone: "{{ bootstrap_openwrt__timezone_posix }}"
      zonename: "{{ bootstrap_openwrt__timezone_zonename }}"
      ttylogin: '0'
      log_size: '128'
      urandom_seed: '0'
      compat_version: '1.1'

  - type: 'timeserver'
    name: 'ntp'
    find: { enabled: '1' }
    options:
      enabled: '1'
      enable_server: '0'
      server: "{{ bootstrap_openwrt__ntp_servers }}"
```

### Default for `openwrt_network`

```yaml
bootstrap_openwrt__network_default:
  - type: 'interface'
    name: 'loopback'
    find: { device: 'lo' }
    options:
      device: 'lo'
      proto: 'static'
      ipaddr: ['127.0.0.1/8']

  - type: 'device'
    find: { name: 'br-lan' }
    options:
      name: 'br-lan'
      type: 'bridge'
      ports: ['lan']

  - type: 'interface'
    name: 'lan'
    find: { device: 'br-lan' }
    options:
      device: 'br-lan'
      proto: 'static'
      ipaddr: ['192.168.1.1/24']
      ip6assign: '60'
```

### Protected network sections

`openwrt_network_protect` lists sections of `/etc/config/network` that are managed elsewhere, e.g. by another role or by hand.
The role neither changes nor removes them, `openwrt_network_prune` skips them.
An entry is a name or a pattern with the shell wildcards `*` and `?`, it matches a section by

- its name, e.g. `wg0` for `config interface 'wg0'`,
- its type, e.g. `wireguard_wg0` for the unnamed peers of the WireGuard interface `wg0`,
- its option `name`, e.g. `br-guest` for an unnamed `config device` with `option name 'br-guest'`.

```yaml
openwrt_network_protect: [ 'wg*', 'wireguard_*' ]
```

protects all WireGuard interfaces starting with `wg` and all their peers.
The role fails before any change if `openwrt_network_protect` is not a list of non-empty strings
or if an entry of `openwrt_network` matches a pattern by `name`, `type`, `find.name` or `options.name`,
a protected section must not be declared.
The firewall zones of the protected interfaces are not affected, the role does not manage `/etc/config/firewall`.

### Default for `openwrt_odhcpd`

The default is the configuration written by `odhcpd.defaults` of OpenWrt with dnsmasq.

```yaml
bootstrap_openwrt__odhcpd_default:
  - type: 'odhcpd'
    name: 'odhcpd'
    options:
      leasefile: '/tmp/odhcpd.leases'
      leasetrigger: '/usr/sbin/odhcpd-update'
      loglevel: '4'
      piodir: '/tmp/odhcpd-piodir'
      hostsdir: '/tmp/hosts'

  - type: 'dhcp'
    name: 'lan'
    options:
      dhcpv4: 'server'
      dhcpv6: 'server'
      ra: 'server'
      ra_slaac: '1'
      ra_flags: ['managed-config', 'other-config']
```

### odhcpd and dns_dnsmasq

`openwrt_odhcpd` is a list of sections of `/etc/config/dhcp` like the other lists of the role, every entry has `type`, `name` and `options`:

- at most one entry of type `odhcpd` with the name `odhcpd`, the role replaces `config odhcpd 'odhcpd'` with its options,
  without this entry the section stays untouched,
- one entry of type `dhcp` per interface with the name of the section `config dhcp '<name>'` and the options of odhcpd there.

`name` is required and unique, `find` is not supported, the sections `dhcp` are named after their interface and shared with `dns_dnsmasq`.
The values are strings, numbers, booleans (written as `'1'` and `'0'`) or lists (written as `list`).
The role fails before any change on an invalid entry and skips `openwrt_odhcpd` if `/usr/sbin/odhcpd` is missing.

The sections `dhcp` are shared with the role `dns_dnsmasq`:

- `dns_dnsmasq` manages `interface`, `start`, `limit`, `dynamicdhcp`, `leasetime`, `ignore` and `dhcp_option` (the pool of dnsmasq),
- this role manages all other options (`dhcpv4`, `dhcpv6*`, `ra*`, `ndp`, `dns`, `domain`, `ntp`, ...),
- each role keeps the options of the other, the entries of type `dhcp` in `openwrt_odhcpd` must not contain options of `dns_dnsmasq`.

A section that does not exist yet is created with `interface '<name>'` and `ignore '1'`, dnsmasq serves no DHCP there until `dns_dnsmasq` declares a `dhcp-range`.
With `openwrt_odhcpd_prune` (default `true`) the role removes the options of odhcpd from the sections `dhcp` that are not declared in `openwrt_odhcpd`,
the sections themselves are removed by `dns_dnsmasq` only.
`dns_dnsmasq` keeps undeclared sections `dhcp` with options of odhcpd and sets `ignore '1'` there.

dnsmasq of OpenWrt 24.10 and 25.12 serves its pool unless `dhcpv4` is `disabled`, the current development version of OpenWrt needs `dhcpv4 'server'` for the pool of dnsmasq,
`dhcpv4` belongs to this role.

The section `office` of an existing configuration

```
config dhcp 'office'
    option interface 'office'
    option start '128'
    option limit '64'
    option leasetime '12h'
    option dhcpv4 'server'
    option ra 'server'
    option ra_preference 'medium'
    option dhcpv6 'server'
    option dhcpv6_pd '1'
    option dhcpv6_pd_min_len '64'
    list ra_flags 'none'
```

is split into `dnsmasq_config` of `dns_dnsmasq` (`dhcp-range: [ 'office,<net>.128,<net>.191,<netmask>,12h' ]`) and

```yaml
openwrt_odhcpd:
  # ... the entry of type odhcpd and the other interfaces
  - type: 'dhcp'
    name: 'office'
    options:
      dhcpv4: 'server'
      ra: 'server'
      ra_preference: 'medium'
      dhcpv6: 'server'
      dhcpv6_pd: '1'
      dhcpv6_pd_min_len: '64'
      ra_flags: [ 'none' ]
```

The backup of `dhcp` is written to the same file as by `dns_dnsmasq`, it contains the state before the last change.

### Default for `openwrt_attendedsysupgrade`

```yaml
bootstrap_openwrt__attendedsysupgrade_default:
  - type: 'server'
    name: 'server'
    find: { url: 'https://sysupgrade.openwrt.org' }
    options:
      url: 'https://sysupgrade.openwrt.org'

  - type: 'client'
    name: 'client'
    find: { upgrade_packages: '1' }
    options:
      upgrade_packages: '1'
      auto_search: '0'
      advanced_mode: '0'

  # Section of owut without options
  - type: 'owut'
    name: 'owut'
    find: {}
    options: {}
```

### Default for `openwrt_uhttpd`

```yaml
bootstrap_openwrt__uhttpd_default:
  - type: 'uhttpd'
    name: 'main'
    find: { home: '/www' }
    options:
      listen_http: ['0.0.0.0:80', '[::]:80']
      listen_https: ['0.0.0.0:443', '[::]:443']
      redirect_https: '0'
      home: '/www'
      rfc1918_filter: '1'
      max_requests: '3'
      max_connections: '100'
      cert: '/etc/uhttpd.crt'
      key: '/etc/uhttpd.key'
      cgi_prefix: '/cgi-bin'
      lua_prefix: ['/cgi-bin/luci=/usr/lib/lua/luci/sgi/uhttpd.lua']
      script_timeout: '60'
      network_timeout: '30'
      http_keepalive: '20'
      tcp_keepalive: '1'
      ubus_prefix: '/ubus'

  - type: 'cert'
    name: 'defaults'
    find: { commonname: 'OpenWrt' }
    options:
      days: '397'
      key_type: 'ec'
      bits: '2048'
      ec_curve: 'P-256'
      country: 'ZZ'
      state: 'Somewhere'
      location: 'Unknown'
      commonname: 'OpenWrt'
```

### SSH

The role always manages SSH: the section `dropbear` `main` of `/etc/config/dropbear`, the SFTP server and the authorized keys.
`openwrt_sshd` is merged recursively into the default, so only differing options have to be written:

```yaml
openwrt_sshd:
  dropbear:
    password_auth: false
    root_password_auth: false
    ssh_keep_alive: 60
    banner_file: '/etc/banner'
  sftp:
    enable: true
  authorized_keys:
    root:
      - 'ssh-ed25519 AAAAC3Nza... admin@example.org'
    backup:
      - 'ssh-ed25519 AAAAC3Nza... backup@example.org'
```

- `dropbear` holds the options of the section `dropbear` `main`, see [dropbear](https://openwrt.org/docs/guide-user/base-system/dropbear),
  in snake case, the role translates them to the names of `/etc/config/dropbear` (see below).
  Booleans become `'1'` and `'0'`, numbers strings, `null` removes an option of the default.
  The section is written completely, other sections of the type `dropbear` are removed (`openwrt_sshd_prune: false` keeps them).
  After a change dropbear is restarted, running sessions are kept.
- `sftp.enable: true` installs `openssh-sftp-server`, dropbear starts it for SFTP clients,
  see [SFTP server](https://openwrt.org/docs/guide-user/services/nas/sftp.server). `false` (default) removes the package.
- `authorized_keys` maps users to their keys, the file contains exactly these keys.
  The keys of `root` are written to `/etc/dropbear/authorized_keys`, the keys of other users to `~/.ssh/authorized_keys` of their home in `/etc/passwd`,
  owned by the user with mode `0600` (`.ssh` with `0700`). An empty list removes the file, users that are not listed are not changed.

The role fails before it changes anything for keys of `openwrt_sshd` other than `dropbear`, `sftp` and `authorized_keys`,
for unknown options of `dropbear` (e.g. the UCI name `PasswordAuth` instead of `password_auth`) and invalid values (booleans, strings, numbers or lists of them without line breaks),
for `sftp` without the boolean `enable`, for keys that are no list of strings in one line and for users missing in `/etc/passwd`.
If `openwrt_sshd` is no dictionary, merging it with the default fails before anything changes.
The variable is not called `openwrt_ssh`, `community.openwrt.init` defines `openwrt_ssh` as SSH command in its role defaults.

As the role always manages SSH, it resets the section `dropbear` of existing devices to the default and `openwrt_sshd`
and removes `openssh-sftp-server` without `sftp.enable: true`.
`enable: false`, `password_auth: false` without keys, a changed `port` or `interface` can lock out Ansible,
the connection of the next run has to match the new configuration.

| Option in `openwrt_sshd.dropbear` | Option of `/etc/config/dropbear` |
|---|---|
| `enable`, `verbose`, `mdns`, `vrf` | same name |
| `password_auth`, `root_password_auth`, `root_login` | `PasswordAuth`, `RootPasswordAuth`, `RootLogin` |
| `port`, `interface`, `direct_interface` | `Port`, `Interface`, `DirectInterface` |
| `gateway_ports`, `local_port_forward`, `remote_port_forward` | `GatewayPorts`, `LocalPortForward`, `RemotePortForward` |
| `force_command`, `banner_file` | `ForceCommand`, `BannerFile` |
| `rsa_key_file`, `key_file` (list) | `rsakeyfile`, `keyfile` |
| `ssh_keep_alive`, `idle_timeout`, `max_session_duration` | `SSHKeepAlive`, `IdleTimeout`, `MaxSessionDuration` |
| `max_auth_tries`, `recv_window_size` | `MaxAuthTries`, `RecvWindowSize` |

`verbose` is documented by OpenWrt, the current `dropbear.init` does not read it.

### Default for `openwrt_sshd`

```yaml
bootstrap_openwrt__sshd_default:
  dropbear:
    enable: '1'
    password_auth: 'on'
    root_password_auth: 'on'
    port: '22'
  sftp:
    enable: false
  authorized_keys: {}
```

### Backups

Before the role commits a change of a UCI configuration (`system`, `network`, `dhcp`, `wireless`, `attendedsysupgrade`, `acme`, `uhttpd`, `dropbear`),
it stores the configuration before the change on the controller in `<playbook_dir>/backups/<inventory_hostname>/<config>`,
secrets of `wireless` and `acme` are redacted. A run without changes writes no backup, the backup always contains the state before the last change.

### SNMP

The role does not configure snmpd any longer, the role `monitoring_snmp` configures snmpd on OpenWrt and Debian.

| Former variable | Now (role `monitoring_snmp`) |
|---|---|
| `openwrt_snmpd_enable: true` | run the role `monitoring_snmp` on the device |
| `openwrt_snmpd` (UCI sections) | `snmpd_config` and `snmpd_configs` with directives of `snmpd.conf`, the role translates them to UCI |
| `openwrt_snmpd_ssl` | `snmpd_ssl` |
| `openwrt_snmpd_prune` | `snmpd_prune` |
| `openwrt_snmpd_redact_keys` | removed, the secrets are always redacted |

Without variables `monitoring_snmp` creates the same configuration as the former default of `openwrt_snmpd`.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs with OpenWrt on a macOS controller.
Every platform is a clone of the base VM `openwrt-base`, the clones are deleted afterwards, the base VM itself is never started or changed.
The playbooks creating and destroying the VMs are shared by all tart scenarios and live in `.molecule/tart/` in the repository root,
the platforms of this scenario set `image`, `user`, `password` and `authorized_keys` (`/etc/dropbear/authorized_keys`, dropbear does not read `~/.ssh`).

| Platform | Tested |
|---|---|
| `molecule-openwrt-minimal` | Network of the base VM (`br-lan` via DHCP), removal of an undeclared network section, protected network sections (interface by name, peer by type, device by option `name`), time zone and NTP servers of the site settings (`site_timezone`, `site_ntp_sources`, servers before pools), attendedsysupgrade with defaults including the section `owut`, odhcpd with defaults, removal of an undeclared option of odhcpd (`dhcp.wan.ra`) |
| `molecule-openwrt-full` | Additionally an own `openwrt_system` with hostname, `openwrt_timezone`, a package (`htop`), a disabled service (`dnsmasq`), an enabled service (`uhttpd`, disabled and stopped in `prepare`) and uhttpd with HTTPS, own `openwrt_odhcpd` with numbers, booleans and lists, a new section `molecule6`, kept options of dns_dnsmasq (`dhcp.lan.start`) |

ACME is not tested, it needs a real DNS zone and CA, wireless is not tested, the VM has no radios.

The base VM needs OpenWrt with `apk`, `network.lan.proto` `dhcp` on `br-lan`, the DHCP server disabled and SSH login as `root` with password.
The tests use the network of the base VM, the default of `openwrt_network` (lan static `192.168.1.1/24`) would cut the connection to the VM.
`prepare` checks the base VM, updates the package lists, installs `odhcpd-ipv6only` if odhcpd is missing,
sets `dhcp.lan.start` and the undeclared option `dhcp.wan.ra`, creates the network section `molecule_stale`,
the protected sections `wg_molecule`, a section of the type `wireguard_wg_molecule` and the device `molecule-dev0` on `molecule-openwrt-minimal` and installs uhttpd and `px5g-mbedtls` on `molecule-openwrt-full`,
the init script of uhttpd generates certificate and key, the role does not install uhttpd and fails without them.
`converge` reads the ports of `br-lan` from the clone.
`side_effect` runs the role with a declared section that is protected, with a pattern instead of a list,
with `openwrt_odhcpd` as dictionary, with an option of dns_dnsmasq and with an unknown type in `openwrt_odhcpd`,
and checks that the role fails with exactly the expected message and `/etc/config/network` is unchanged (tasks marked `expect ERROR`).
`verify` checks that the protected sections still exist, `molecule_stale` is removed and the options of `/etc/config/dhcp`. The backups of the role are written to `molecule/default/backups/`, which is ignored by git.

Requirements on the controller: `tart`, `sshpass` (`brew install hudochenkov/sshpass/sshpass`), `molecule` and the collection `community.openwrt`.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_OPENWRT_IMAGE` | `openwrt-base` | Base VM that is cloned |
| `MOLECULE_TART_OPENWRT_PASSWORD` | `OpenWRT` | Password of `root`, used to install the SSH key |

```shell
cd bootstrap_openwrt
molecule test
```
