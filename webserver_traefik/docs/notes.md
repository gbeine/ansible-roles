`traefik_home` contains only two files: `traefik.yml` and `acme.json` and potentially the files in `./dynamic`.
Both will be mounted as volumes under `/etc/traefik` into the container.

A running container is restarted when `traefik.yml` or the quadlet unit changed, the first start of the container does not trigger an additional restart.


### Default `traefik_config`

```yaml
webserver_traefik__config_default:
  api:
    dashboard: false
    insecure: false
    debug: false
  entryPoints:
    web:
      address: ":80"
      http:
        redirections:
          entryPoint:
            to: "websecure"
            scheme: "https"
    websecure:
      address: ":443"
  serversTransport:
    insecureSkipVerify: false
  log:
    level: 'WARN'
  providers:
    docker:
      endpoint: "unix:///var/run/docker.sock"
      exposedByDefault: false
```

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The base VM is cloned for every platform and the clones are deleted afterwards, the base VM itself is never changed.
The playbooks creating and destroying the VMs are shared by all tart scenarios and live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-traefik-ipv4-only` | Container with IPv4 address only |
| `molecule-traefik-ipv6` | Container with IPv4 and IPv6 address |

`prepare` sets up podman and the network `podman-molecule` with the role `container_podman` and pulls the traefik image.
`verify` checks the quadlet unit, the service, the container addresses, the redirect from http to https on port 80 and the answer of traefik on port 443.
The VMs need access to Docker Hub for `docker.io/traefik:v3`.

Requirements on the controller: `tart`, `sshpass` (`brew install hudochenkov/sshpass/sshpass`), `molecule` and the collection `containers.podman`.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd webserver_traefik
MOLECULE_TART_IMAGE='debian' molecule test
```
