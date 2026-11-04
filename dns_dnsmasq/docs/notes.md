dnsmasq runs in the container image [4km3/dnsmasq](https://github.com/4km3/docker-dnsmasq), an Alpine Linux with the package `dnsmasq-dnssec`.
The image starts `dnsmasq --keep-in-foreground` with the configuration `/etc/dnsmasq.conf` of the image,
the role passes neither a command nor a configuration yet.
dnsmasq answers DNS queries on port 53 (UDP and TCP) of the container and forwards them to the resolvers of the container.

Use `dnsmasq_publish` to publish the port on the host, e.g. `[ '53:53/udp', '53:53/tcp' ]`.

### DHCP

`dnsmasq_enable_dhcp` adds the capability `NET_ADMIN` to the container, dnsmasq needs it to serve DHCP.
Without the flag the container gets no additional capabilities.
DHCP only reaches clients in the same layer 2 network as the container, e.g. with a macvlan network,
not through a podman bridge network or published ports.
The container has no `NET_RAW`, so dnsmasq can not check a free address with an ICMP ping before it offers it.

### Validation

The role checks before any change that `dnsmasq_enable_dhcp` is a boolean, `dnsmasq_publish` is a list
and `dnsmasq_labels` is a dictionary if set.
The failure message names only the failing checks.

### Changes and restarts

A running container is restarted when the quadlet unit changed, e.g. after changing `dnsmasq_enable_dhcp`, `dnsmasq_container` or `dnsmasq_version`.
The first start of the container does not trigger an additional restart.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The base VM is cloned for every platform and the clones are deleted afterwards, the base VM itself is never changed.
The playbooks creating and destroying the VMs are shared by all tart scenarios and live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-dnsmasq-dns` | Container with IPv4 address only, without DHCP and labels, `side_effect` enables DHCP |
| `molecule-dnsmasq-dhcp` | Container with IPv4 and IPv6 address, DHCP and labels |

`prepare` sets up podman and the network `podman-molecule` with the role `container_podman`, installs `dig` and pulls the image.
`side_effect` runs the role with an invalid `dnsmasq_enable_dhcp`, `dnsmasq_publish` and `dnsmasq_labels`
and checks that it fails at the validation without changing the quadlet unit.
The invalid values are passed as include parameters, so they are gone after each run,
and the failure message has to name exactly the failing check.
On `molecule-dnsmasq-dns` it enables DHCP afterwards and checks that the running service is restarted.
`verify` checks the quadlet unit including `AddCapability` and `Label`, the service, the addresses, capabilities and labels of the container
and resolves `example.org` with `dig` from the VM.
The VMs need access to Docker Hub and to DNS resolvers.

Requirements on the controller: `tart`, `sshpass` (`brew install hudochenkov/sshpass/sshpass`), `molecule` and the collection `containers.podman`.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd dns_dnsmasq
MOLECULE_TART_IMAGE='debian' molecule test
```
