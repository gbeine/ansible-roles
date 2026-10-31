PowerDNS Recursor runs in the official container images `docker.io/powerdns/pdns-recursor-<release>`, available for `amd64` and `arm64`.
The role supports the releases 5.3, 5.4 and 5.5, selected with `recursor_release`:

| `recursor_release` | Image |
|---|---|
| `'53'` (default) | `docker.io/powerdns/pdns-recursor-53` |
| `'54'` | `docker.io/powerdns/pdns-recursor-54` |
| `'55'` | `docker.io/powerdns/pdns-recursor-55` |

`recursor_version` sets the tag of the image, `latest` by default.

### Settings

The role writes `recursor.yml` in the [YAML format](https://doc.powerdns.com/recursor/yamlsettings.html) of the recursor.
The file contains the active settings only, all other settings keep the default of the release.
The settings are taken from `recursor_settings`, a mapping of sections to settings, merged recursively over the defaults of the role:

```yaml
recursor_release: '55'
recursor_settings:
  incoming:
    allow_from: [ '192.168.99.0/24', '127.0.0.0/8', '::1/128' ]
  recursor:
    forward_zones:
      - zone: 'example.org'
        forwarders: [ '192.168.99.53' ]
  webservice:
    webserver: true
    address: '0.0.0.0'
    allow_from: [ '192.168.99.0/24' ]
    api_key: "{{ vault_recursor_api_key }}"
```

The defaults of the role:

- `incoming.listen` is `[ '0.0.0.0', '::' ]`, the default of the recursor listens on localhost only,
- `recursor.include_dir` is `/etc/powerdns/recursor.d`,
- `recursor.security_poll_suffix` is empty, the security polling is disabled like in former versions of the role.

Lists replace the lists of the defaults, e.g. `incoming.listen` in `recursor_settings` replaces both addresses.

All settings of every release with their description and default are in `vars/settings-<release>.yml`, generated from `pdns_recursor --config=default` of the image.
The role fails before it changes anything if `recursor_settings` contains a section or setting unknown to the selected release, e.g. `outgoing.cookies` with release 5.3.

`recursor.yml` is readable for root and the group `953` of the container only, because it may contain the API key and the password of the webserver.

### Differences between the releases

Settings added in 5.4:
`outgoing.any_to_tcp`, `outgoing.cookies`, `outgoing.cookies_unsupported`, `recursor.tls_configurations`, `webservice.listen`.

Settings added in 5.5:
`dnssec.nta_extended_error`, `logging.opentelemetry_trace_conditions`, `recordcache.keepwarm`, `recursor.serve_rfc6761`, `recursor.taskthreads`, `webservice.cross_origin_request_header`.

| Setting | 5.3 | 5.4 | 5.5 |
|---|---|---|---|
| `recursor.any_to_tcp` | `false` | `true` | `true` |

### Container

The recursor runs as user `pdns` (`953`) in the container.
The role sets `net.ipv4.ip_unprivileged_port_start` in the container to `incoming.port` (default `53`), so the recursor can bind to it without root privileges.
Docker does this by default, podman does not.
The configuration directory is mounted read-only to `/etc/powerdns`, the control socket lives in `run` below `recursor_home`.

### Changes and restarts

A running container is restarted when `recursor.yml` or the quadlet unit changed, e.g. after changing `recursor_settings` or `recursor_release`.
The first start of the container does not trigger an additional restart.

### Migration

Former versions of the role installed the Debian package `pdns-recursor` and wrote `recursor.conf` in the old format and `recursor.lua`.
The role now runs the recursor as podman quadlet and requires `recursor_home`, `recursor_ip`, `recursor_network`, `recursor_hostname` and `recursor_timezone`.
The role does not remove the Debian package, stop and remove it before, it listens on port 53 of the host.

| Former variable | Now |
|---|---|
| `recursor_allow_from` | `recursor_settings.incoming.allow_from` |
| `recursor_local_address` | `recursor_settings.incoming.listen` |
| `recursor_quiet` | `recursor_settings.logging.quiet` |
| `recursor_security_poll_suffix` | `recursor_settings.recursor.security_poll_suffix` |
| `recursor_exports_etc_hosts` | `recursor_settings.recursor.export_etc_hosts` |
| `recursor_etc_hosts_file` | `recursor_settings.recursor.etc_hosts_file`, the path inside the container |
| `recursor_config_dir`, `recursor_include_dir` | removed, fixed paths in the container |
| `recursor_hint_file`, `recursor_public_suffix_list_file` | removed, paths of Debian packages, the recursor has built-in defaults |
| `recursor_lua_config_file` | removed, the trust anchors are built into the recursor |
| `recursor_setuid`, `recursor_setgid` | removed, the container runs as user `pdns` |

### Tests

The molecule scenario `default` runs the role in three [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The base VM is cloned for every platform and the clones are deleted afterwards, the base VM itself is never changed.
The playbooks creating and destroying the VMs are shared by all tart scenarios and live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-recursor-53` | Release 5.3 with webserver and API |
| `molecule-recursor-54` | Release 5.4 with webserver and API |
| `molecule-recursor-55` | Release 5.5 with webserver and API |

`prepare` sets up podman and the network `podman-molecule` with the role `container_podman`, installs `dig` and pulls the image.
`side_effect` changes `recordcache.max_ttl` and checks that the running service is restarted.
`verify` checks that `recursor.yml` contains exactly the active settings and its mode, the quadlet unit and the service,
checks the version with the API and resolves `example.org` with `dig`.
The VMs need access to Docker Hub and to the DNS root servers.

Requirements on the controller: `tart`, `sshpass` (`brew install hudochenkov/sshpass/sshpass`), `molecule` and the collection `containers.podman`.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd dns_powerdns_recursor
MOLECULE_TART_IMAGE='debian' molecule test
```
