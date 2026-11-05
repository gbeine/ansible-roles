The role installs WireGuard and configures one interface for every entry in `wireguard_networks`.
On Debian every interface gets the configuration file `/etc/wireguard/<interface>.conf` and is started and enabled as `wg-quick@<interface>`.
On OpenWrt every interface becomes a section `interface` with `proto 'wireguard'` in `/etc/config/network`, see [OpenWrt](#openwrt).
The role detects OpenWrt itself, the same variables apply to both platforms.

### Networks

| Attribute | Required | Debian | OpenWrt | Description |
|---|---|---|---|---|
| `interface` | yes | file name | section name | Name of the interface, e.g. `wg0`, on OpenWrt 1 to 15 letters, digits or underscores |
| `address` | yes | `Address` | `list addresses` | Addresses of the interface, comma separated or a list, e.g. `10.90.0.1/24, fd00:90::1/64` |
| `private_key` | yes | `PrivateKey` | `private_key` | Private key of the interface |
| `peers` | no | `[Peer]` | `wireguard_<interface>` | List of peers, may be missing or empty, e.g. for a server without peers yet |
| `listen_port` | no | `ListenPort` | `listen_port` | UDP port the interface listens on, required if peers connect to this host |
| `mtu` | no | `MTU` | `mtu` | MTU of the interface |
| `fwmark` | no | `FwMark` | `fwmark` | Firewall mark of the outgoing packets |
| `postup` | no | `PostUp` | not supported | Command run after the interface is up, e.g. firewall rules |
| `postdown` | no | `PostDown` | not supported | Command run after the interface is down |
| `metric` | no | ignored | `metric` | Metric of the routes of the interface |
| `ip6prefix` | no | ignored | `list ip6prefix` | IPv6 prefixes delegated through the interface, comma separated or a list |
| `nohostroute` | no | ignored | `nohostroute` | Boolean, `true` adds no route to the endpoints |
| `tunlink` | no | ignored | `tunlink` | Interface the endpoints are reached through |
| general interface options | no | ignored | option of the same name | Options of netifd and LuCI (tab Advanced): booleans `auto`, `defaultroute`, `peerdns`, `delegate`, `force_link`, numbers `dns_metric`, `ip6assign`, `ip6weight`, lists `dns`, `dns_search`, `ip6class`, strings `ip4table`, `ip6table`, `ip6hint`, `ip6ifaceid`, `multipath` |

### Peers

| Attribute | Required | Debian | OpenWrt | Description |
|---|---|---|---|---|
| `public_key` | yes | `PublicKey` | `public_key` | Public key of the peer, unique within the interface |
| `allowed_ips` | yes | `AllowedIPs` | `list allowed_ips` | Addresses routed to the peer, comma separated |
| `preshared_key` | no | `PresharedKey` | `preshared_key` | Preshared key, has to be the same on both sides |
| `endpoint` | no | `Endpoint` | `endpoint_host`, `endpoint_port` | `host:port` or `[address]:port` of the peer, required on the side that initiates the connection |
| `persistent_keepalive` | no | `PersistentKeepalive` | `persistent_keepalive` | Keepalive interval in seconds, useful behind NAT |
| `description` | no | comment above `[Peer]` | `description` | Name of the peer, shown by LuCI |
| `route_allowed_ips` | no | only `true` | `route_allowed_ips` | Boolean, `true` adds routes to `allowed_ips`. Not set: no option on OpenWrt (netifd adds no routes), on Debian `wg-quick` always adds them |
| `disabled` | no | peer omitted | `disabled '1'` | Boolean, `true` keeps the peer in the variables without using it |
| `private_key` | no | not written | `private_key` | Private key of the peer, used by LuCI to generate the configuration of the client, never needed by WireGuard itself |

Optional attributes that are not set do not appear in the configuration.
The role checks all attributes before it changes anything: required attributes, unknown attributes, numbers, booleans,
the form of `endpoint` and public keys used by more than one peer of an interface.
Attributes without counterpart in `wg-quick` and `route_allowed_ips: false` are ignored with a warning on Debian.

### Example

A server that accepts a client:

```yaml
wireguard_networks:
  - interface: 'wg0'
    address: '10.90.0.1/24, fd00:90::1/64'
    private_key: "{{ vault_wireguard_wg0_private_key }}"
    listen_port: 51820
    peers:
      - public_key: 'k1b0...='
        preshared_key: "{{ vault_wireguard_wg0_client_psk }}"
        allowed_ips: '10.90.0.2/32, fd00:90::2/128'
        route_allowed_ips: true
```

The matching client:

```yaml
wireguard_networks:
  - interface: 'wg0'
    address: '10.90.0.2/24, fd00:90::2/64'
    private_key: "{{ vault_wireguard_wg0_private_key }}"
    peers:
      - public_key: 'Js9X...='
        preshared_key: "{{ vault_wireguard_wg0_client_psk }}"
        allowed_ips: '10.90.0.0/24, fd00:90::/64'
        endpoint: 'vpn.example.org:51820'
        persistent_keepalive: 25
```

### Keys

Keys are generated with the WireGuard tools:

```shell
wg genkey | tee private.key | wg pubkey > public.key
wg genpsk > preshared.key
```

Private and preshared keys are secrets, store them with Ansible Vault.
The configuration files are written with mode `0640` and without diff output, so the keys do not show up in `--diff` runs.

### Changes and removed interfaces

An interface is restarted only when its configuration file changed.

Configuration files in `/etc/wireguard` that do not belong to an interface in `wireguard_networks` are removed, their `wg-quick@` service is stopped and disabled.
This also affects configuration files created manually.
Removing undeclared interfaces can be disabled with `wireguard_networks_prune: false`.

### OpenWrt

On OpenWrt the role writes `/etc/config/network` with UCI:

```
config interface 'wg0'
    option proto 'wireguard'
    option private_key '...'
    option listen_port '51820'
    list addresses '10.90.0.1/24'
    list addresses 'fd00:90::1/64'

config wireguard_wg0
    option public_key '...'
    option description 'notebook'
    list allowed_ips '10.90.0.2/32'
    option route_allowed_ips '1'
```

- The interface section has the name of the interface, the peers are unnamed sections `wireguard_<interface>` like the ones created by LuCI.
  A peer is found by its `public_key`, peers created with LuCI are updated instead of added a second time.
- The role replaces the options of its sections, options set by hand or with LuCI are removed.
- With `wireguard_networks_prune` (default `true`) the role removes interfaces with `proto 'wireguard'` that are not in `wireguard_networks`
  together with their peers, and peers of the declared interfaces that are not declared. Other sections of `/etc/config/network` stay untouched.
- The role installs `wireguard-tools` with `apk` or `opkg` if `/usr/bin/wg` is missing.
  netifd loads its protocol handlers only at its start, so after the installation the role restarts the network once (`/etc/init.d/network restart`),
  all interfaces restart shortly. Afterwards it waits for the connection, `wireguard_openwrt_wait_for_connection: false` skips waiting,
  `wireguard_openwrt_wait_for_connection_timeout` (default 600 seconds) limits it.
- `postup` and `postdown` let the role fail before any change, firewall rules belong to `/etc/config/firewall`.
  The role does not manage firewall zones and rules, an interface has to be added to a zone separately.
- Before a commit the role stores the configuration before the change in `<playbook_dir>/backups/<inventory_hostname>/network`,
  `private_key` and `preshared_key` are redacted. Keys do not appear in the diff.
- Otherwise netifd reloads the configuration after a commit (`ubus call network reload`) and sets up new and changed interface sections itself.
  netifd does not see changed peers: from OpenWrt 25.12 on the role takes them with `ubus call network.interface.<interface> renew`
  (`wg syncconf`, the tunnels of the other peers stay), older handlers without renew need `ifup` (down and up).
  Interfaces without changes keep their tunnels.
- After a change or an installation the role waits until every declared interface is up,
  otherwise it fails with `ifstatus` and the last lines of `logread` of netifd and WireGuard.

The role `bootstrap_openwrt` manages `/etc/config/network` too and removes undeclared sections.
The WireGuard interfaces and their peers have to be protected there, e.g. `openwrt_network_protect: [ 'wg*', 'wireguard_*' ]`.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The base VM is cloned for every platform and the clones are deleted afterwards, the base VM itself is never changed.
The playbooks creating and destroying the VMs are shared by all tart scenarios and live in `.molecule/tart/` in the repository root.

| Platform | Role in the test |
|---|---|
| `molecule-vpn-wireguard-a` | Server with `listen_port`, `delegate` (ignored with a warning), a peer with preshared key and `private_key` (not written), a peer with `description` and `route_allowed_ips: false` without preshared key and endpoint and a disabled peer. `prepare` creates the interface `wgold` that has to be removed. |
| `molecule-vpn-wireguard-b` | Client with `endpoint` pointing to a and `persistent_keepalive` |

`verify` checks the configuration files including the comment of the description and the missing disabled peer, the services and the removal of `wgold`.
A tunnel between the VMs is not tested, because whether tart VMs can reach each other depends on the network setup of the controller (e.g. softnet), not on the role.
The keys in `molecule/default/test_cases.yml` are test keys only.

Requirements on the controller: `tart`, `sshpass` (`brew install hudochenkov/sshpass/sshpass`) and `molecule`.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd vpn_wireguard
MOLECULE_TART_IMAGE='debian' molecule test
```

The molecule scenario `openwrt` runs the role in two clones of the tart VM `openwrt-base` (OpenWrt with `apk`, SSH login as `root` with password).

| Platform | Role in the test |
|---|---|
| `molecule-wireguard-openwrt-a` | Server with `listen_port`, `mtu`, `defaultroute`, `delegate`, `multipath`, a peer with preshared key, `private_key` (written, replaces the one set like LuCI) and `route_allowed_ips: true` and a peer with `description` and `route_allowed_ips: false`. `prepare` creates the interface `wgold` with a peer (removed), a peer of b like LuCI (updated, not added), a stranger peer in `wg0` (removed) and the interface `molecule_other` with `proto none` (kept). |
| `molecule-wireguard-openwrt-b` | Client with `endpoint` pointing to a and `persistent_keepalive` without `route_allowed_ips` (no option), the interface `wg1` without peers |

The role installs `wireguard-tools` in both VMs and restarts the network once.
`side_effect` runs the role with `postup`, an interface name with a dash, an endpoint without port and two peers with the same public key
and checks that the role fails with exactly the expected message and `/etc/config/network` is unchanged (tasks marked `expect ERROR`).
Afterwards it changes the allowed IPs of a peer on a.
`verify` checks the UCI options, the peer sections, the private key of the peer, the removed sections and the running interface with `wg show`, including the changed allowed IPs.
The collection `community.openwrt` is required on the controller.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_OPENWRT_IMAGE` | `openwrt-base` | Base VM that is cloned |
| `MOLECULE_TART_OPENWRT_PASSWORD` | `OpenWRT` | Password of `root`, used to install the SSH key |

```shell
cd vpn_wireguard
molecule test -s openwrt
```
