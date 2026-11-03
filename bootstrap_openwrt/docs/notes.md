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

### Default for `openwrt_snmpd`

```yaml
bootstrap_openwrt__snmpd_default:
  - type: 'agent'
    find: { agentaddress: 'UDP:161,UDP6:161' }
    options: { agentaddress: 'UDP:161,UDP6:161' }

  - type: 'agentx'
    find: { agentxsocket: '/var/run/agentx.sock' }
    options: { agentxsocket: '/var/run/agentx.sock' }

  - type: 'com2sec'
    name: 'public'
    find: { secname: 'ro' }
    options: { secname: 'ro', source: 'default', community: 'public' }
  - type: 'com2sec'
    name: 'private'
    find: { secname: 'rw' }
    options: { secname: 'rw', source: 'localhost', community: 'private' }

  - type: 'com2sec6'
    name: 'public6'
    find: { secname: 'ro' }
    options: { secname: 'ro', source: 'default', community: 'public' }
  - type: 'com2sec6'
    name: 'private6'
    find: { secname: 'rw' }
    options: { secname: 'rw', source: 'localhost', community: 'private' }

  - type: 'group'
    name: 'public_v1'
    find: { group: 'public', version: 'v1' }
    options: { group: 'public', version: 'v1', secname: 'ro' }
  - type: 'group'
    name: 'public_v2c'
    find: { group: 'public', version: 'v2c' }
    options: { group: 'public', version: 'v2c', secname: 'ro' }
  - type: 'group'
    name: 'public_usm'
    find: { group: 'public', version: 'usm' }
    options: { group: 'public', version: 'usm', secname: 'ro' }
  - type: 'group'
    name: 'private_v1'
    find: { group: 'private', version: 'v1' }
    options: { group: 'private', version: 'v1', secname: 'rw' }
  - type: 'group'
    name: 'private_v2c'
    find: { group: 'private', version: 'v2c' }
    options: { group: 'private', version: 'v2c', secname: 'rw' }
  - type: 'group'
    name: 'private_usm'
    find: { group: 'private', version: 'usm' }
    options: { group: 'private', version: 'usm', secname: 'rw' }

  - type: 'view'
    name: 'all'
    find: { viewname: 'all' }
    options: { viewname: 'all', type: 'included', oid: '.1' }

  - type: 'access'
    name: 'public_access'
    find: { group: 'public' }
    options:
      group: 'public'
      context: 'none'
      version: 'any'
      level: 'noauth'
      prefix: 'exact'
      read: 'all'
      write: 'none'
      notify: 'none'
  - type: 'access'
    name: 'private_access'
    find: { group: 'private' }
    options:
      group: 'private'
      context: 'none'
      version: 'any'
      level: 'noauth'
      prefix: 'exact'
      read: 'all'
      write: 'all'
      notify: 'all'

  - type: 'system'
    find: { sysName: 'HeartOfGold' }
    options: { sysLocation: 'office', sysContact: 'bofh@example.com', sysName: 'HeartOfGold' }

  - type: 'exec'
    find: { name: 'filedescriptors' }
    options: { name: 'filedescriptors', prog: '/bin/cat', args: '/proc/sys/fs/file-nr' }

  - type: 'engineid'
    find: { engineidtype: '3' }
    options: { engineidtype: '3', engineidnic: 'eth0' }

  - type: 'snmpd'
    name: 'general'
    find: { enabled: '1' }
    options: { enabled: '1' }
```

### Backups

Before the role commits a change of a UCI configuration (`system`, `network`, `wireless`, `attendedsysupgrade`, `acme`, `uhttpd`, `snmpd`),
it stores the configuration before the change on the controller in `<playbook_dir>/backups/<inventory_hostname>/<config>`,
secrets of `wireless`, `acme` and `snmpd` are redacted. A run without changes writes no backup, the backup always contains the state before the last change.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs with OpenWrt on a macOS controller.
Every platform is a clone of the base VM `openwrt-base`, the clones are deleted afterwards, the base VM itself is never started or changed.
The playbooks creating and destroying the VMs are shared by all tart scenarios and live in `.molecule/tart/` in the repository root,
the platforms of this scenario set `image`, `user`, `password` and `authorized_keys` (`/etc/dropbear/authorized_keys`, dropbear does not read `~/.ssh`).

| Platform | Tested |
|---|---|
| `molecule-openwrt-minimal` | Network of the base VM (`br-lan` via DHCP), removal of an undeclared network section, time zone and NTP servers of the site settings (`site_timezone`, `site_ntp_sources`, servers before pools), attendedsysupgrade with defaults |
| `molecule-openwrt-full` | Additionally an own `openwrt_system` with hostname, `openwrt_timezone`, a package (`htop`), a disabled service (`dnsmasq`), uhttpd with HTTPS and snmpd with the defaults of the role, read via SNMP |

ACME is not tested, it needs a real DNS zone and CA, wireless is not tested, the VM has no radios.

The base VM needs OpenWrt with `apk`, `network.lan.proto` `dhcp` on `br-lan`, the DHCP server disabled and SSH login as `root` with password.
The tests use the network of the base VM, the default of `openwrt_network` (lan static `192.168.1.1/24`) would cut the connection to the VM.
`prepare` checks the base VM, updates the package lists, creates the network section `molecule_stale` and installs uhttpd and `px5g-mbedtls` on `molecule-openwrt-full`,
the init script of uhttpd generates certificate and key, the role does not install uhttpd and fails without them.
`converge` reads the ports of `br-lan` from the clone. The backups of the role are written to `molecule/default/backups/`, which is ignored by git.

Requirements on the controller: `tart`, `sshpass` (`brew install hudochenkov/sshpass/sshpass`), `molecule` and the collection `community.openwrt`.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_OPENWRT_IMAGE` | `openwrt-base` | Base VM that is cloned |
| `MOLECULE_TART_OPENWRT_PASSWORD` | `OpenWRT` | Password of `root`, used to install the SSH key |

```shell
cd bootstrap_openwrt
molecule test
```
