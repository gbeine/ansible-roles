PowerDNS Authoritative Server runs in the official container images `docker.io/powerdns/pdns-auth-<release>`.
The role supports the releases 4.9, 5.0 and 5.1, selected with `powerdns_release`:

| `powerdns_release` | Image | Architectures |
|---|---|---|
| `'49'` (default) | `docker.io/powerdns/pdns-auth-49` | `amd64` |
| `'50'` | `docker.io/powerdns/pdns-auth-50` | `amd64`, `arm64` |
| `'51'` | `docker.io/powerdns/pdns-auth-51` | `amd64`, `arm64` |

`powerdns_version` sets the tag of the image, `latest` by default.

### Settings

The role writes `pdns.conf` with all settings of the selected release, see the [settings](https://doc.powerdns.com/authoritative/settings.html).
Every setting is written with the default of the release, settings without a default are commented out.
`launch` is always written, even without value, because `launch+=gpgsql` in `pdns.d` fails without it.
The settings in `powerdns_settings` replace the defaults, the names are the names of the settings in `pdns.conf`:

```yaml
powerdns_release: '51'
powerdns_settings:
  api: true
  api-key: "{{ vault_powerdns_api_key }}"
  webserver-address: '0.0.0.0'
  webserver-allow-from: [ '192.168.99.0/24', '127.0.0.1', '::1' ]
  default-soa-content: 'ns1.example.org hostmaster.example.org 0 10800 3600 604800 3600'
```

`true` and `false` are written as `yes` and `no`, lists are joined with commas, `null` keeps the default of the release.
The role sets `include-dir` to `/etc/powerdns/pdns.d`, the directory of `gpgsql.conf`.

The defaults and the known settings of every release are in `vars/settings-<release>.yml`, generated from `pdns_server --config=default --launch=gpgsql` of the image.
The role fails before it changes anything if `powerdns_settings` contains a setting unknown to the selected release, e.g. `views` with release 4.9.

### PostgreSQL backend

With `powerdns_gpgsql_enabled: true` the role writes `pdns.d/gpgsql.conf` with `launch+=gpgsql` and the settings in `powerdns_gpgsql_settings`, see the [generic PostgreSQL backend](https://doc.powerdns.com/authoritative/backends/generic-postgresql.html).
`gpgsql-host` and `gpgsql-password` are required, `launch` must not be set in `powerdns_settings`.
The file contains the connection settings with the defaults of the role (`gpgsql-dbname` and `gpgsql-user` are `powerdns`, `gpgsql-dnssec` is `true`) or of the release.
Other `gpgsql-*` settings, e.g. own queries, are written only when set.
Without the backend the file is removed.

```yaml
powerdns_gpgsql_enabled: true
powerdns_gpgsql_settings:
  gpgsql-host: '192.168.99.10'
  gpgsql-password: "{{ vault_powerdns_db_password }}"
```

The role does not create the database schema.
The schema of the release is part of the image:

```shell
podman run --rm --entrypoint cat docker.io/powerdns/pdns-auth-51 /usr/local/share/doc/pdns/schema.pgsql.sql \
  | psql -h 192.168.99.10 -U powerdns powerdns
```

`pdns.conf` and `gpgsql.conf` are readable for root and the group `953` of the container only, because they contain the API key and the database password.

### Differences between the releases

Settings added in 5.0:
`direct-dnskey-signature`, `dnsproxy-udp-port-range`, `dnsupdate-require-tsig`, `lua-global-include-dir`, `max-pointers-per-name`, `max-pointers-per-packet-byte`, `max-pointers-to-pointers`, `resolve-across-zones`, `views`.

Settings added in 5.1:
`default-soa-edit-api`, `enable-lua-record-updates`, `logging-structured`, `member-catalog-group`, `naptr-additional-processing`, `protobuf-servers`, `rrsig-expiry-extend`, `soa-edit-spread`, `webserver-cross-origin-request-header`, `webserver-max-concurrent-connections`.

| Setting | 4.9 | 5.0 | 5.1 |
|---|---|---|---|
| `lua-records-insert-whitespace` | `yes` | `no` | `no` |
| `entropy-source` | `/dev/urandom` | `/dev/urandom` | no default and no description, probably without effect |
| `rng` | `auto` | `auto` | no default and no description, probably without effect |

The settings of the PostgreSQL backend are taken from release 4.9 for all releases.

### Container

PowerDNS runs as user `pdns` (`953`) in the container.
The role sets `net.ipv4.ip_unprivileged_port_start` in the container to `local-port` (default `53`), so PowerDNS can bind to it without root privileges.
Docker does this by default, podman does not.

### Changes and restarts

A running container is restarted when `pdns.conf`, `gpgsql.conf` or the quadlet unit changed, e.g. after changing `powerdns_settings` or `powerdns_release`.
The first start of the container does not trigger an additional restart.

### Migration

Former versions of the role had a variable for every setting.
The variables were replaced by `powerdns_settings`, the name of the setting is the name of the variable without `powerdns_` and with `-` instead of `_`,
e.g. `powerdns_webserver_allow_from` is now `webserver-allow-from` and `powerdns_8bit_dns` is now `8bit-dns`.

| Former variable | Now |
|---|---|
| `powerdns_backend_gpgsql` | `powerdns_gpgsql_enabled` |
| `powerdns_backend_gpgsql_<name>` | `powerdns_gpgsql_settings['gpgsql-<name>']` |
| `powerdns_backend_gpgsqlextra_connection_parameters` | `powerdns_gpgsql_settings['gpgsql-extra-connection-parameters']` |
| `powerdns_server_id` | `server-id`, the former default `dns_hostname` was never defined |
| `powerdns_use_podman` | removed, the role only supports podman |

The former role wrote `lua-records-insert-whitespace=yes`, the default of 4.9.
Release 5.0 changed the default to `no`, set it in `powerdns_settings` to keep the former behavior after switching the release.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The base VM is cloned for every platform and the clones are deleted afterwards, the base VM itself is never changed.
The playbooks creating and destroying the VMs are shared by all tart scenarios and live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-powerdns-50` | Release 5.0 with PostgreSQL backend and API |
| `molecule-powerdns-51` | Release 5.1 with PostgreSQL backend and API |

Release 4.9 is not tested with molecule, the image is available for `amd64` only and the tart VMs on Apple silicon are `arm64`.

`prepare` sets up podman and the network `podman-molecule` with the role `container_podman`, installs `dig`, pulls the images,
starts a PostgreSQL container and imports the schema from the PowerDNS image.
`side_effect` changes `default-ttl` and checks that the running service is restarted.
`verify` checks `pdns.conf` (set values, defaults and settings of the release, settings without value commented out), `gpgsql.conf`, the modes of both files,
the quadlet unit and the service, checks the version with the API, creates a zone with the API and queries it with `dig`.
The VMs need access to Docker Hub.

Requirements on the controller: `tart`, `sshpass` (`brew install hudochenkov/sshpass/sshpass`), `molecule` and the collection `containers.podman`.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd dns_powerdns
MOLECULE_TART_IMAGE='debian' molecule test
```
