Unbound runs in the distroless container image [klutchell/unbound](https://github.com/klutchell/unbound-docker) with the configuration of the image.
It is a validating, recursive and caching resolver listening on port 53 (UDP and TCP) of the IPv4 address of the container.
The image allows queries from `127.0.0.0/8`, `10.0.0.0/8`, `172.16.0.0/12` and `192.168.0.0/16` only.
It does not listen on the IPv6 address of the container, even if `unbound_ipv6` is set.

Use `unbound_publish` to publish the port on the host, e.g. `[ '53:53/udp', '53:53/tcp' ]`.

### Changes and restarts

A running container is restarted when the quadlet unit changed, e.g. after changing `unbound_container` or `unbound_version`.
The first start of the container does not trigger an additional restart.

### Migration

Former versions of the role used the image `docker.io/mvance/unbound`, which is available for `amd64` only and not maintained anymore.
The role now uses `docker.io/klutchell/unbound`, which is available for `amd64`, `arm64` and `arm`.
Set `unbound_container.image` to keep the former image.

`unbound_use_podman` was removed, the role only supports podman.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The base VM is cloned for every platform and the clones are deleted afterwards, the base VM itself is never changed.
The playbooks creating and destroying the VMs are shared by all tart scenarios and live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-unbound-ipv4-only` | Container with IPv4 address only |
| `molecule-unbound-ipv6` | Container with IPv4 and IPv6 address |

`prepare` sets up podman and the network `podman-molecule` with the role `container_podman`, installs `dig` and pulls the image.
`verify` checks the quadlet unit, the service and the container addresses and resolves `example.org` with `dig` from the VM.
The VMs need access to Docker Hub and to the DNS root servers.

Requirements on the controller: `tart`, `sshpass` (`brew install hudochenkov/sshpass/sshpass`), `molecule` and the collection `containers.podman`.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd dns_unbound
MOLECULE_TART_IMAGE='debian' molecule test
```
