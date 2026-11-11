The role installs and configures the TURN/STUN server [coturn](https://github.com/coturn/coturn) on Debian (package `coturn`)
and on OpenWrt (package `coturn` of the feed `telephony`), see [OpenWrt](#openwrt).
The role detects OpenWrt itself with `raw` (`/etc/openwrt_release`), plays for OpenWrt need `gather_facts: false`.
On both platforms coturn reads `/etc/turnserver.conf`, the role writes the file completely.

### Configuration

`coturn_config` is a dictionary of options of [turnserver.conf](https://github.com/coturn/coturn/blob/master/examples/etc/turnserver.conf):

* a string or a number writes `option=value`
* a list writes one line per element, e.g. for `listening-ip`, `relay-ip`, `allowed-peer-ip` or `denied-peer-ip`
* `true` writes the option without value, e.g. `fingerprint`
* `false` or `null` removes the option

Every key replaces the key of the default completely. The default is the delivered configuration of the package,
its active options are `syslog`, `no-rfc5780`, `no-stun-backward-compatibility` and `response-origin-only-with-rfc5780`.
Everything else uses the defaults of turnserver, e.g. `listening-port` 3478 and `tls-listening-port` 5349.

```yaml
coturn_config:
  realm: 'turn.example.org'
  use-auth-secret: true
  static-auth-secret: "{{ vault_coturn_static_auth_secret }}"
  listening-ip: [ '192.0.2.10', '2001:db8::10' ]
  external-ip: '192.0.2.10'
  fingerprint: true
  no-multicast-peers: true
  denied-peer-ip:
    - '10.0.0.0-10.255.255.255'
    - '172.16.0.0-172.31.255.255'
    - '192.168.0.0-192.168.255.255'
  cert: '/etc/ssl/turn.example.org/fullchain.pem'
  pkey: '/etc/ssl/turn.example.org/privkey.pem'
```

A TURN server relays traffic to any address. Deny the private networks of the site with `denied-peer-ip` and set `no-multicast-peers`,
otherwise clients can reach internal services through the relay.
`static-auth-secret` is written to the file, take it from the vault. The role does not show the file in diffs.
Certificates and keys have to be readable by the user `turnserver`.

`enabled` (default `true`) switches the service, `false` writes the configuration and stops and disables coturn.
It is no option of turnserver and not written to the file.

### Debian

The role writes `/etc/turnserver.conf` with owner `root`, group `turnserver` and mode `0640`, like the package sets it with `dpkg-statoverride`.
The service `coturn` runs as user `turnserver` and restarts when the file changed.
turnserver has no check of the configuration, an option turnserver does not know lets the service fail at the restart.

### OpenWrt

The package `coturn` is part of the feed `telephony`, the role installs it with `apk` or `opkg` if `/usr/bin/turnserver` is missing.
In check mode the role stops after the installation then.

The role writes `/etc/turnserver.conf` with owner `root` and mode `0600`, turnserver reads it as `root` and changes to the user `turnserver` afterwards.
The init script `/etc/init.d/turnserver` starts turnserver only with `enabled '1'` in the section `general` of `/etc/config/turnserver`,
the role sets it from `enabled`. `log_stderr`, `log_stdout` and `options` stay with the package,
`options` starts turnserver with `--log-file syslog --no-cli --proc-user turnserver --proc-group turnserver`.

- Before the role changes `/etc/turnserver.conf` it stores the file before the change on the controller in `<playbook_dir>/backups/<inventory_hostname>/turnserver.conf`,
  before a commit of the UCI configuration in `<playbook_dir>/backups/<inventory_hostname>/turnserver`.
- After a change of the file, the UCI configuration or the installation the role stops `turnserver`, waits until the process has ended and starts it again,
  `/etc/init.d/turnserver restart` starts the new process while the former one still holds the ports.

### Validation

The role checks before any change that the options of `coturn_config` consist of lowercase letters, digits and dashes
with strings, numbers, booleans or lists of them as values without line breaks and that `enabled` is a boolean.
If `coturn_config` is no dictionary, merging it with the default of the platform (`vars/Debian.yml`, `vars/OpenWrt.yml`) fails before anything changes.
The failure message names only the failing checks.

### Migration

The single variables of former versions are replaced by options in `coturn_config`:

- `coturn_port` and `coturn_tls_port` are `listening-port` and `tls-listening-port`
- `coturn_ip` is `listening-ip` as list
- `coturn_fingerprint: true` is `fingerprint: true`
- `coturn_static_auth_secret` is `use-auth-secret: true` and `static-auth-secret`
- `coturn_realm` is `realm`
- `coturn_user_quota`, `coturn_total_quota`, `coturn_bps_capacity` and `coturn_stale_nonce` are `user-quota`, `total-quota`, `bps-capacity` and `stale-nonce`
- `coturn_udp`, `coturn_tcp`, `coturn_tls`, `coturn_dtls`, `coturn_udp_relay` and `coturn_tcp_relay` set to `false`
  are `no-udp`, `no-tcp`, `no-tls`, `no-dtls`, `no-udp-relay` and `no-tcp-relay` set to `true`
- `coturn_multicast_peers` was read from `coturn_dtls`, so `no-multicast-peers` was always written, set `no-multicast-peers: true` to keep it

The former template always wrote `listening-port=3478`, `tls-listening-port=5349`, the quotas `0` and `stale-nonce=600`,
these are the defaults of turnserver and not written anymore.
The file belonged to `root:root` with mode `0640` on Debian, the service running as `turnserver` could not read it, now it belongs to `root:turnserver`.
The handler `Restart coturn` and the tag `coturn` are gone, the tags are `app` and `app_coturn`.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-coturn-default` | Without variables, the configuration of the package on port 3478 |
| `molecule-coturn` | Port 3479, `realm`, `use-auth-secret` with `static-auth-secret`, `no-multicast-peers`, `denied-peer-ip` as list and `syslog` removed |

`prepare` updates the package cache.
`side_effect` runs the role with `coturn_config` not a dictionary, an invalid option name, a dictionary as value, a line break and an invalid boolean
and checks that it fails with the expected message and `turnserver.conf` is unchanged (tasks marked `expect ERROR`),
then it changes `realm` on `molecule-coturn`, coturn has to restart.
`verify` checks the lines, owner, group and mode of `turnserver.conf`, the service, the UDP and TCP sockets on the port
and sends a STUN binding request with `turnutils_stunclient`.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd app_coturn
MOLECULE_TART_IMAGE='debian' molecule test
```

The molecule scenario `openwrt` runs the role in two clones of the tart VM `openwrt-base` (OpenWrt with `apk`, SSH login as `root` with password),
the VMs need access to the package feeds including `telephony`.

| Platform | Test case |
|---|---|
| `molecule-coturn-openwrt-default` | Without variables, the role installs coturn and enables it in UCI |
| `molecule-coturn-openwrt` | The same options as `molecule-coturn` |

`side_effect` runs the same invalid configurations and checks that `/etc/turnserver.conf` and `/etc/config/turnserver` are unchanged,
then it changes `realm` on `molecule-coturn-openwrt`, `turnserver` has to run with a new process.
`verify` checks the lines and the mode of `/etc/turnserver.conf`, `enabled` in UCI, the running and enabled service, the sockets on the port,
a STUN binding request and the backup of `turnserver.conf` on the controller with the former realm.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_OPENWRT_IMAGE` | `openwrt-base` | Base VM that is cloned |
| `MOLECULE_TART_OPENWRT_PASSWORD` | `OpenWRT` | Password of `root`, used to install the SSH key |

```shell
cd app_coturn
molecule test -s openwrt
```
