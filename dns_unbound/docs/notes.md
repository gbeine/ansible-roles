Unbound runs in the distroless container image [klutchell/unbound](https://github.com/klutchell/unbound-docker).
The role generates `unbound.conf` in `unbound_home` and mounts it read-only to `/etc/unbound/unbound.conf`, the configuration of the image is replaced completely.
The defaults of the role are the configuration of the image: a validating, recursive and caching resolver listening on port 53 (UDP and TCP)
of the IPv4 address of the container, answering queries from `127.0.0.0/8`, `10.0.0.0/8`, `172.16.0.0/12` and `192.168.0.0/16` only.
It does not listen on the IPv6 address of the container, even if `unbound_ipv6` is set; add `interface: [ '0.0.0.0', '::0' ]` to `unbound_config` for that.

Use `unbound_publish` to publish the port on the host, e.g. `[ '53:53/udp', '53:53/tcp' ]`.

### Configuration

`unbound_config` is a dictionary of [unbound.conf](https://unbound.docs.nlnetlabs.nl/en/latest/manpages/unbound.conf.html) clauses,
the keys are the clause names (`server`, `forward-zone`, `stub-zone`, ...), the values the options of the clause.
It is merged recursively into the defaults of the role (`dns_unbound__config_default`, the configuration of the image):
an option set in `unbound_config` replaces the option of the defaults, a list replaces the list as a whole,
`null` removes the option or the clause.
A clause given as a dictionary is written once, a clause given as a list of dictionaries once per element.

* `true` writes `option: yes`, `false` writes `option: no`
* a string or number writes `option: value`, the value is written as it is: options with several arguments
  like `access-control: 10.0.0.0/8 allow` are one string, values that Unbound wants quoted like `local-data`
  carry their quotes in the string
* a list writes one line `option: value` per element in the order of the list

Clauses and options are written sorted by name, `name` first.
Only section clauses are supported, the `include` directive is not.
Without `unbound_config` the file equals the configuration of the image.

With a `forward-zone` for `.` Unbound sends every query to the forwarders instead of resolving recursively from the root hints,
with `forward-tls-upstream: true` over TLS; the name of the certificate after `#` is required then,
Unbound does not verify the certificate of the forwarder without it.

```yaml
unbound_home: '/srv/unbound'
unbound_config:
  server:
    verbosity: 0
    serve-expired: ~
    private-domain: [ 'home.arpa' ]
    local-zone: [ 'home.arpa. transparent' ]
    local-data: [ '"printer.home.arpa. A 192.168.1.20"' ]
  forward-zone:
    - name: '.'
      forward-tls-upstream: true
      forward-addr: [ '9.9.9.9@853#dns.quad9.net', '149.112.112.112@853#dns.quad9.net' ]
  stub-zone:
    - name: 'lab.example.org'
      stub-addr: '192.168.2.53'
```

### Validation

The role checks before any change that `unbound_config` is a dictionary of clauses with valid names,
each a dictionary, a list of dictionaries or `null`, with valid option names and booleans, strings, numbers, lists of strings and numbers or `null` as values,
and that every `forward-addr` of a TLS forward zone carries the name of the certificate after `#`.
Strings must not contain line breaks.
The failure message names only the failing checks.
`unbound-checkconf` of the image checks the generated file in a throwaway container before it is replaced.

### Changes and restarts

A running container is restarted when the quadlet unit or the configuration changed,
e.g. after changing `unbound_config`, `unbound_container` or `unbound_version`.
The first start of the container does not trigger an additional restart.

### Migration

Former versions of the role used the image `docker.io/mvance/unbound`, which is available for `amd64` only and not maintained anymore.
The role now uses `docker.io/klutchell/unbound`, which is available for `amd64`, `arm64` and `arm`.
Set `unbound_container.image` to keep the former image.
The former image forwarded every query to Cloudflare over TLS out of the box, the defaults of the role resolve recursively,
set a `forward-zone` for `.` with `forward-tls-upstream: true` and
`forward-addr: [ '1.1.1.1@853#cloudflare-dns.com', '1.0.0.1@853#cloudflare-dns.com' ]` in `unbound_config` to keep that.

`unbound_home` is required since the role generates the configuration, former versions ran with the configuration of the image.

`unbound_use_podman` was removed, the role only supports podman.

### Tests

The molecule scenario `default` runs the role in three [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The base VM is cloned for every platform and the clones are deleted afterwards, the base VM itself is never changed.
The playbooks creating and destroying the VMs are shared by all tart scenarios and live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-unbound-ipv4-only` | Container with IPv4 address only and the default configuration |
| `molecule-unbound-ipv6` | Container with IPv4 and IPv6 address and the default configuration |
| `molecule-unbound-config` | Container with `unbound_config`, forwarding over TLS, `side_effect` switches the forwarders and overrides and removes server options |

`prepare` sets up podman and the network `podman-molecule` with the role `container_podman`, installs `dig` and pulls the image.
`side_effect` runs the role with invalid variables on every platform and checks that it fails before any change,
and switches the forwarders of `molecule-unbound-config` from Cloudflare to Quad9, which has to restart the service.
`verify` checks the quadlet unit, the service and the container addresses and resolves `example.org` with `dig` from the VM;
it checks the generated file and the mount, on `molecule-unbound-config` it also looks into the network namespace
of the container for the TLS session to Quad9 after a query.
The VMs need access to Docker Hub, to the DNS root servers and to the forwarders.

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
