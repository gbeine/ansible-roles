Pi-hole runs in the official container image [pihole/pihole](https://github.com/pi-hole/docker-pi-hole) and is configured with environment variables.
Pi-hole v6 accepts every setting of `pihole.toml` as environment variable `FTLCONF_<section>_<setting>`, see the [configuration documentation](https://docs.pi-hole.net/docker/configuration/).

DHCP is not supported by this role.

### Environment and secrets

All variables are set with `pihole_environment`, which is merged over the defaults of the role.
Variables carrying secrets are passed as podman secrets with `pihole_secrets` and must not be set in `pihole_environment`.
Every secret is created with `podman secret create` and passed into the container as environment variable `target`.

The role requires the following secret and checks it before it changes anything:

| Variable | Set with | Default of the role |
|---|---|---|
| `FTLCONF_webserver_api_password` | `pihole_secrets` | – |

The role sets `TZ` to `pihole_timezone` and `FTLCONF_dns_listeningMode` to `all`, so Pi-hole answers queries from all networks reaching the container.

```yaml
pihole_environment:
  FTLCONF_dns_upstreams: '192.168.99.53;9.9.9.9'
  FTLCONF_dns_domain_name: 'home.example.org'
pihole_secrets:
  - name: 'pihole_web_password'
    data: "{{ vault_pihole_web_password }}"
    target: 'FTLCONF_webserver_api_password'
```

### Ports

The container is reachable with its address in the podman network, port 53 (DNS) and port 80 (web interface and API).
Ports are published on the host only with `pihole_publish`:

```yaml
pihole_publish:
  - '53:53/tcp'
  - '53:53/udp'
  - '8080:80/tcp'
```

### Directories

The role creates `pihole` (`/etc/pihole`), `dnsmasq` (`/etc/dnsmasq.d`) and `log` (`/var/log/pihole`) below `pihole_home`.
The container sets owner and mode of `pihole` and `log` itself on every start, the role only creates them.

### Changes and restarts

A running container is restarted when a secret or the quadlet unit changed, e.g. after changing `pihole_environment`.
The first start of the container does not trigger an additional restart.

### Migration

| Former variable | Now |
|---|---|
| `pihole_password` | secret with target `FTLCONF_webserver_api_password` in `pihole_secrets` |

Former versions of the role created the podman secret `webserver_api_password`, use it as `name` of the secret or remove it with `podman secret rm webserver_api_password`.

Former versions of the role published the ports 53 (TCP and UDP) and 80 on the host, the role does not publish any port by default anymore.
Set `pihole_publish` to keep them.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The base VM is cloned for every platform and the clones are deleted afterwards, the base VM itself is never changed.
The playbooks creating and destroying the VMs are shared by all tart scenarios and live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-pihole-ipv4-only` | Container with IPv4 address only |
| `molecule-pihole-ipv6` | Container with IPv4 and IPv6 address |

`prepare` sets up podman and the network `podman-molecule` with the role `container_podman`, installs `dig` and pulls the image.
`side_effect` changes `FTLCONF_dns_upstreams` and checks that the running service is restarted.
`verify` checks the quadlet unit including the secret, the environment and no published ports, the podman secret, the service and the container addresses,
resolves `example.org` with `dig` and logs in to the API with the password of the secret.
The VMs need access to Docker Hub and to the upstream DNS servers.

Requirements on the controller: `tart`, `sshpass` (`brew install hudochenkov/sshpass/sshpass`), `molecule` and the collection `containers.podman`.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd dns_pihole
MOLECULE_TART_IMAGE='debian' molecule test
```
