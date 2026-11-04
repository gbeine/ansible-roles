dnsmasq runs in the container image [4km3/dnsmasq](https://github.com/4km3/docker-dnsmasq), an Alpine Linux with the package `dnsmasq-dnssec`.
The image starts `dnsmasq --keep-in-foreground`, dnsmasq reads its compiled in default configuration file `/etc/dnsmasq.conf`.
The role generates this file as `dnsmasq.conf` in `dnsmasq_home` and mounts it read-only to `/etc/dnsmasq.conf`, the entrypoint is not changed.
The configuration of the image (`local-service` and `conf-dir=/etc/dnsmasq.d/,*.conf`) is replaced completely.

Use `dnsmasq_publish` to publish the port on the host, e.g. `[ '53:53/udp', '53:53/tcp' ]`.

### Configuration

`dnsmasq_config` is a dictionary of dnsmasq options, the keys are the long option names without `--`
as described in the [man page](https://thekelleys.org.uk/dnsmasq/docs/dnsmasq-man.html).

* `true` writes the option without value, `false` omits it
* a string or number writes `option=value`
* a list writes one line `option=value` per element in the order of the list

The options are written sorted by name.
Without `dnsmasq_config` the file is empty and dnsmasq runs with its built-in defaults, forwarding to the resolvers of the container.

```yaml
dnsmasq_config:
  domain-needed: true
  bogus-priv: true
  no-resolv: true
  server: [ '9.9.9.9', '149.112.112.112' ]
  address: [ '/router.example.org/192.168.1.1' ]
  dhcp-range: '192.168.1.100,192.168.1.200,12h'
```

The configuration is checked with `dnsmasq --test` in a throwaway container of the image before it replaces the existing file,
an invalid configuration never reaches the running container.

### DHCP

`dnsmasq_enable_dhcp` adds the capabilities `NET_ADMIN` and `NET_RAW` to the container.
dnsmasq needs `NET_ADMIN` to change the ARP cache and `NET_RAW` to check a free address with an ICMP ping before it offers it.
As soon as a `dhcp-range` is configured, dnsmasq requests both capabilities when it drops root and exits if they are missing.
Without the flag the container gets no additional capabilities.
DHCP only reaches clients in the same layer 2 network as the container, e.g. with a macvlan network,
not through a podman bridge network or published ports.

### Validation

The role checks before any change that `dnsmasq_enable_dhcp` is a boolean, `dnsmasq_publish` is a list,
`dnsmasq_labels` is a dictionary if set and `dnsmasq_config` is a dictionary of valid option names
with booleans, strings, numbers or lists of strings and numbers as values.
Strings must not contain line breaks.
The failure message names only the failing checks.

### Changes and restarts

A running container is restarted when the quadlet unit or the configuration changed,
e.g. after changing `dnsmasq_config`, `dnsmasq_enable_dhcp`, `dnsmasq_container` or `dnsmasq_version`.
The first start of the container does not trigger an additional restart.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The base VM is cloned for every platform and the clones are deleted afterwards, the base VM itself is never changed.
The playbooks creating and destroying the VMs are shared by all tart scenarios and live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-dnsmasq-dns` | Container with IPv4 address only, without DHCP and labels, `side_effect` enables DHCP |
| `molecule-dnsmasq-dhcp` | Container with IPv4 and IPv6 address, DHCP, a DHCP range and labels, `side_effect` adds an address to the configuration |

`prepare` sets up podman and the network `podman-molecule` with the role `container_podman`, installs `dig` and pulls the image.
`side_effect` runs the role with an invalid `dnsmasq_enable_dhcp`, `dnsmasq_publish`, `dnsmasq_labels` and `dnsmasq_config`
and with an unknown dnsmasq option, which is rejected by `dnsmasq --test`.
It checks that every run fails with exactly the expected message without changing the quadlet unit or the configuration.
The invalid values are passed as include parameters, so they are gone after each run.
Afterwards it enables DHCP on `molecule-dnsmasq-dns`, which changes the quadlet unit only,
and adds an address on `molecule-dnsmasq-dhcp`, which changes the configuration only,
and checks that the running service is restarted.
`verify` checks the quadlet unit including `AddCapability` (`NET_ADMIN` and `NET_RAW` with DHCP), `Label` and the volume of the configuration, the options in the configuration,
the service, the addresses, capabilities and labels of the container,
resolves `example.org` and the addresses of the configuration with `dig` from the VM.
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
