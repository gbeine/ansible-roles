The role requires Debian 13 or later, because podman networks are managed as quadlets.
Debian 12 ships podman 4.3, which has no quadlet support.

The role needs the filters `ip_network_cidr` and `ip_address_normalize` from `common_filters`, so add `common_filters` to the play before `container_podman`:

```yaml
- name: 'Configure host42.example.org'
  become: 'yes'
  hosts: 'host42'
  roles:
    - 'common_filters'
    - 'container_podman'
```

### podman networks

Every network is written as quadlet `/etc/containers/systemd/<name>.network` and created by `<name>-network.service`.

The list of networks requires at least four attributes for every network:
- the `name` of the network
- the networks IPv4 `address`
- the `gateway` IPv4 address
- the `netmask` as number

```yaml
podman_networks:
  - name: 'podman99'
    address: '192.168.99.0'
    gateway: '192.168.99.1'
    netmask: 24
```

The DNS configuration can be disabled by setting `disable_dns` to `true`.
Containers can be isolated from external networks by setting `internal` to `true`.
The name of the bridge interface defaults to the network name and can be changed with `interface_name`.

```yaml
podman_networks:
  - name: 'podman99'
    address: '192.168.99.0'
    gateway: '192.168.99.1'
    netmask: 24
    disable_dns: true
```

It is possible to specify optional IPv6 addresses
- setting `ipv6` to `true` is required
- the IPv6 gateway address: `ipv6_gateway`
- the prefix length for IPv6 addresses as number: `ipv6_prefixlength`
- optionally the IPv6 network address: `ipv6_address`, it defaults to the network of `ipv6_gateway`

```yaml
podman_networks:
  - name: 'podman99'
    address: '192.168.99.0'
    gateway: '192.168.99.1'
    netmask: 24
    ipv6: true
    ipv6_address: 'fd00::99:0'
    ipv6_gateway: 'fd00::99:1'
    ipv6_prefixlength: 112
```

### Changing network addresses

The role compares the declared networks with the existing ones (subnets, gateways, driver, interface name, IPv6, internal and DNS).
When a network differs, it is recreated:

1. all containers attached to the network are stopped via their systemd unit `<container>.service`
2. `<name>-network.service` is stopped and the network is removed
3. the network is created again from the quadlet
4. the containers are started again

Containers with a static IP address from the old subnet will not start again.
The role reports them; run their roles again with addresses from the new subnet.

### Removing networks

Networks not declared in `podman_networks` are removed, together with their quadlet files.
Networks listed in `podman_networks_protected` are kept, the default is `['podman']`.
Networks still used by containers are not removed, the role reports them instead.
Removing networks can be disabled with `podman_networks_prune: false`.

### podman API via TCP

Setting `podman_tcp_address` starts `podman-tcp.service`, which serves the podman API on `podman_tcp_address:podman_tcp_port` (default port `2376`).
The API is served **without authentication and with root privileges**, so bind it only to addresses reachable by trusted hosts.
Additional units required by the service can be set as list in `podman_tcp_requires`.
Setting `podman_tcp_address` to an empty value removes the service again.

### Image cleanup

A systemd timer removes unused images every night, see `podman_cleanup_on_calendar` (default `*-*-* 02:00:00`).
Setting `podman_cleanup_enabled` to `false` removes the timer.

### Migration from `bootstrap_podman`

- The role was renamed from `bootstrap_podman` to `container_podman`, the tags are `container` and `container_podman`.
- `podman_network`, `podman_environment` and `podman_containers` are no longer used.
- `podman___update_mode` is no longer evaluated by this role.

### Tests

The molecule scenario `default` runs the role in a [tart](https://tart.run) VM on a macOS controller, the base VM has to be Debian 13.
The base VM is cloned and the clone is deleted afterwards, the base VM itself is never changed.
The playbooks creating and destroying the VM are shared by all tart scenarios and live in `.molecule/tart/` in the repository root.

The scenario runs the role twice:

| Step | What happens |
|---|---|
| `prepare` | installs podman and creates the networks `molstale` (unused) and `molbusy` (used by a container) and the orphaned quadlet `molghost.network` |
| `converge`, `idempotence` | creates `molnet-a` (IPv4 and IPv6) and `molnet-b` (without DNS), enables socket, TCP service and image cleanup, prunes `molstale` and `molghost`, keeps `molbusy` |
| `side_effect` | checks the state after converge, starts the quadlet container `molapp` in `molnet-a`, then runs the role again: `molnet-a` is readdressed, `molnet-b` is no longer declared, socket, TCP service and image cleanup are disabled |
| `verify` | checks the state after the second run, `molapp` has to run with an address from the new subnet |

The containers use `docker.io/library/alpine:3`, so the VM needs access to Docker Hub. The image can be changed in `molecule/default/test_cases.yml`.

Requirements on the controller: `tart`, `sshpass` (`brew install hudochenkov/sshpass/sshpass`), `molecule` and the collection `containers.podman`.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd container_podman
MOLECULE_TART_IMAGE='debian' molecule test
```
