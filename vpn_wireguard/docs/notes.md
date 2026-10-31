The role installs WireGuard and configures one `wg-quick` interface for every entry in `wireguard_networks`.
Every interface gets the configuration file `/etc/wireguard/<interface>.conf` and is started and enabled as `wg-quick@<interface>`.

### Networks

| Attribute | Required | Description |
|---|---|---|
| `interface` | yes | Name of the interface, e.g. `wg0` |
| `address` | yes | Addresses of the interface, comma separated, e.g. `10.90.0.1/24, fd00:90::1/64` |
| `private_key` | yes | Private key of the interface |
| `peers` | yes | List of peers, may be empty |
| `listen_port` | no | UDP port the interface listens on, required if peers connect to this host |
| `mtu` | no | MTU of the interface |
| `postup` | no | Command run after the interface is up, e.g. firewall rules |
| `postdown` | no | Command run after the interface is down |

### Peers

| Attribute | Required | Description |
|---|---|---|
| `public_key` | yes | Public key of the peer |
| `allowed_ips` | yes | Addresses routed to the peer, comma separated |
| `preshared_key` | no | Preshared key, has to be the same on both sides |
| `endpoint` | no | `host:port` of the peer, required on the side that initiates the connection |
| `persistent_keepalive` | no | Keepalive interval in seconds, useful behind NAT |

Optional attributes that are not set do not appear in the configuration file.
The role checks the required attributes before it changes anything.

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

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The base VM is cloned for every platform and the clones are deleted afterwards, the base VM itself is never changed.
The playbooks creating and destroying the VMs are shared by all tart scenarios and live in `.molecule/tart/` in the repository root.

| Platform | Role in the test |
|---|---|
| `molecule-vpn-wireguard-a` | Server with `listen_port`, a peer with preshared key and a peer without preshared key and endpoint. `prepare` creates the interface `wgold` that has to be removed. |
| `molecule-vpn-wireguard-b` | Client with `endpoint` pointing to a and `persistent_keepalive` |

`verify` checks the configuration files, the services and the removal of `wgold`.
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
