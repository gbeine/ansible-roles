### Default for `openwrt_system`

```yaml
bootstrap_openwrt__system_default:
  - type: 'system'
    find: { compat_version: '1.1' }
    options:
      hostname: 'OpenWrt'
      timezone: 'GMT0'
      zonename: 'UTC'
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
      server:
        - '0.openwrt.pool.ntp.org'
        - '1.openwrt.pool.ntp.org'
        - '2.openwrt.pool.ntp.org'
        - '3.openwrt.pool.ntp.org'
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
