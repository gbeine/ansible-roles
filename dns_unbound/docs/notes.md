On Debian Unbound runs in the distroless container image [klutchell/unbound](https://github.com/klutchell/unbound-docker),
on OpenWrt the role installs the package `unbound-daemon` and writes `/etc/config/unbound`, see [OpenWrt](#openwrt).
The role detects OpenWrt itself with `raw` (`/etc/openwrt_release`), plays for OpenWrt need `gather_facts: false`.

The role generates `unbound.conf` in `unbound_home` and mounts it read-only to `/etc/unbound/unbound.conf`, the configuration of the image is replaced completely.
The defaults of the role are the configuration of the image: a validating, recursive and caching resolver listening on port 53 (UDP and TCP)
of the IPv4 address of the container, answering queries from `127.0.0.0/8`, `10.0.0.0/8`, `172.16.0.0/12` and `192.168.0.0/16` only.
It does not listen on the IPv6 address of the container, even if `unbound_ipv6` is set; add `interface: [ '0.0.0.0', '::0' ]` to `unbound_config` for that.

Use `unbound_publish` to publish the port on the host, e.g. `[ '53:53/udp', '53:53/tcp' ]`.

### Configuration

`unbound_config` is a dictionary of [unbound.conf](https://unbound.docs.nlnetlabs.nl/en/latest/manpages/unbound.conf.html) clauses,
the keys are the clause names (`server`, `forward-zone`, `stub-zone`, ...), the values the options of the clause.
It is merged recursively into the default of the platform (`dns_unbound__config_default` of `vars/Debian.yml`, the configuration of the image, or of `vars/OpenWrt.yml`):
an option set in `unbound_config` replaces the option of the defaults, a list replaces the list as a whole,
`null` removes the option or the clause.
A clause given as a dictionary is written once, a clause given as a list of dictionaries once per element.
`name` of a `forward-zone`, `stub-zone` or `auth-zone` is one name or a list of names like `zone_name` of OpenWrt, the zone is written once per name.
The `url` of an `auth-zone` is the URL of the zone file or the directory of the zone files ending with `/`, then `root.zone` or `<name>.zone` is added for every name.
A zone with the UCI option `enabled: false` is not written, like on OpenWrt.

* `true` writes `option: yes`, `false` writes `option: no`
* a string or number writes `option: value`, the value is written as it is: options with several arguments
  like `access-control: 10.0.0.0/8 allow` are one string, values that Unbound wants quoted like `local-data`
  carry their quotes in the string
* a list writes one line `option: value` per element in the order of the list

Clauses and options are written sorted by name, `name` first.
Options of the UCI configuration of OpenWrt (see [OpenWrt](#openwrt)) are not written and ignored with a warning on Debian.
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

`unbound_config` has to be a dictionary, otherwise merging it with the default fails.
The role checks before any change that the clauses have valid names,
each a dictionary, a list of dictionaries or `null`, with valid option names and booleans, strings, numbers, lists of strings and numbers or `null` as values,
and that every `forward-addr` of a TLS forward zone carries the name of the certificate after `#`.
Option names consist of lowercase letters, digits and dashes, the UCI options of OpenWrt are allowed with their names in their clauses.
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

### OpenWrt

On OpenWrt the init script of unbound (`unbound.sh` of the package `unbound-daemon`) generates `/var/lib/unbound/unbound.conf` from the UCI configuration `/etc/config/unbound`.
The role uses the same variable as on Debian, `unbound_config` with clauses and options of `unbound.conf`, and translates it to UCI sections.
Clauses and options are merged recursively into the default of OpenWrt like on Debian, `null` removes an option or a clause.

Without variables the role writes the delivered configuration of OpenWrt (`unbound.uci` of the package):
port 53, `verbosity` 1, `edns-buffer-size` 1232, one thread, `cache-min-ttl` 120, `cache-max-negative-ttl` 1000, hidden identity and version,
`interface-automatic`, no QNAME minimisation and the UCI options `add_local_fqdn 1`, `dhcp_link none`, `domain lan`, `domain_type static`,
`localservice`, `rebind_protection 1`, `protocol`, `recursion` and `resource` `default`, `root_age 9`, `validator 0`, `validator_ntp 1`,
`iface_trig lan wan` and `iface_wan wan`.
The four disabled example zones of the delivery (`auth_icann`, `fwd_isp`, `fwd_google`, `fwd_cloudflare`) are not part of the default.

The clause `server` becomes the section `unbound 'ub_main'`, `manual_conf` is always `0`:

| Option of unbound | UCI option | Values on OpenWrt |
|---|---|---|
| `verbosity` | `verbosity` | 0 to 5 |
| `port` | `listen_port` | 53 or 1024 to 10240 |
| `edns-buffer-size` | `edns_size` | 512 to 4096 |
| `num-threads` | `num_threads` | 1 or 2 |
| `cache-min-ttl` | `ttl_min` | up to 1800 |
| `cache-max-negative-ttl` | `ttl_neg_max` | number |
| `ratelimit` | `rate_limit` | 0 (no rate limit) or 11 to 99999, `ip-ratelimit` is half of it |
| `extended-statistics` | `extended_stats` | boolean |
| `interface-automatic` | `interface_auto` | boolean, without it `0` (unbound.sh would enable it) |
| `qname-minimisation` | `query_minimize` | boolean |
| `qname-minimisation-strict` | `query_min_strict` | boolean, only with `qname-minimisation` |
| `hide-identity`, `hide-version` | `hide_binddata` | both the same boolean, without them `0` |
| `dns64-prefix` | `dns64 '1'`, `dns64_prefix` | without it `dns64 '0'` |
| `domain-insecure` | `list domain_insecure` | list |

unbound.sh replaces numbers outside these ranges without notice, the role fails instead.

Options of the UCI configuration without counterpart in `unbound.conf` are written with their UCI names into the clause `server`,
booleans as `0` and `1`: `enabled`, `add_extra_dns`, `add_local_fqdn`, `add_wan_fqdn`, `dhcp_link`, `dhcp4_slaac6`, `domain`, `domain_type`, `exclude_ipv6_ga`,
the lists `iface_lan`, `iface_trig` and `iface_wan`, `localservice`, `prefetch_root`, `protocol`, `rebind_localhost`, `rebind_protection`,
`recursion`, `resource`, `root_age`, `unbound_control`, `validator` and `validator_ntp`.
They select options unbound.sh writes itself, e.g. `localservice` and `iface_lan` the `access-control` lines, `rebind_protection` the `private-address` lines,
`resource` the cache sizes, `recursion` the prefetching and `validator` the DNSSEC validation.
`enabled` is the switch *Enable Unbound* of LuCI, unbound.sh does not read it; with `enabled: false` the role writes the configuration and stops and disables unbound like LuCI.

```yaml
unbound_config:
  server:
    port: 1053
    domain-insecure: [ 'home.arpa' ]
    resource: 'medium'
    dhcp_link: 'dnsmasq'
  forward-zone:
    - name: '.'
      forward-tls-upstream: true
      forward-addr: [ '9.9.9.9@853#dns.quad9.net', '149.112.112.112@853#dns.quad9.net' ]
```

Every zone becomes a section `zone` with all its names in `list zone_name`. The UCI option `section` names the section,
without it the name is `fwd_`, `stub_` or `auth_` followed by the first name with `_` instead of other characters (`fwd_root` for `.`, `stub_lab_example_org`):

| Clause | Options of unbound | UCI options |
|---|---|---|
| `forward-zone` | `name`, `forward-addr`, `forward-host`, `forward-first`, `forward-tls-upstream` | `zone_type forward_zone`, `zone_name`, `server` (addresses and hosts as written, with `@port#name`), `fallback`, `tls_upstream`, UCI only: `section`, `enabled`, `resolv_conf`, `dns_assist` |
| `stub-zone` | `name`, `stub-addr`, `stub-first` | `zone_type stub_zone`, `zone_name`, `server`, `fallback`, UCI only: `section`, `enabled` |
| `auth-zone` | `name`, `primary` or `master`, `url`, `fallback-enabled` | `zone_type auth_zone`, `zone_name`, `server`, `url_dir`, `fallback`, UCI only: `section`, `enabled` |

Every zone section gets `enabled '1'` or the UCI option `enabled` of the zone (`false` keeps the zone in UCI without writing it to the configuration of unbound), `forward-first`, `stub-first` and `fallback-enabled` are `0` without the option like in unbound.
unbound.sh decides between `forward-addr` and `forward-host` itself, an address has to be one it accepts; a forwarder on the loopback (e.g. dnsmasq on `127.0.0.1@1053`)
needs `dns_assist` in the zone, otherwise unbound.sh drops it.
An enabled `auth-zone` needs `validator_ntp: false` in `server`. `url` is the directory of the zone files ending with `/` (`url_dir`),
or for a single name the URL of the zone file ending with `/<name>.zone` (`/root.zone` for `.`);
unbound.sh writes `zonefile`, `for-downstream: no` and `for-upstream: yes` itself.
The zone `auth_icann` of the delivery of OpenWrt is:

```yaml
unbound_config:
  auth-zone:
    - section: 'auth_icann'
      name: [ '.', 'arpa.', 'in-addr.arpa.', 'ip6.arpa.' ]
      enabled: false
      fallback-enabled: true
      primary: [ 'lax.xfr.dns.icann.org', 'iad.xfr.dns.icann.org' ]
      url: 'https://www.internic.net/domain/'
```

The role fails before it changes anything for options and clauses without UCI counterpart (e.g. `access-control`, `private-address`, `module-config`, `remote-control`, `view`),
the message names the UCI option that writes the option if there is one, and for values unbound.sh would replace or drop.

- The variables of the container (`unbound_home`, `unbound_ip`, `unbound_network`, `unbound_publish`, `unbound_container`, …) are ignored on OpenWrt.
- The role installs `unbound-daemon` with `apk` or `opkg` if `/usr/sbin/unbound` is missing; in check mode it stops after the installation then.
  dnsmasq of OpenWrt listens on port 53 as well, move one of them, e.g. `port: 1053` in `unbound_config` and unbound as forwarder of dnsmasq,
  or `dhcp_link: 'dnsmasq'` (unbound.sh changes the configuration of dnsmasq, which conflicts with the role `dns_dnsmasq`).
- With `unbound_prune` (default `true`) the role removes the sections `unbound` and `zone` it does not declare, e.g. zones created in LuCI.
- Before a commit the role stores the configuration before the change on the controller in `<playbook_dir>/backups/<inventory_hostname>/unbound`.
- After a change of the configuration or the installation the role restarts unbound.

### Tests

The molecule scenario `default` runs the role in three [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The base VM is cloned for every platform and the clones are deleted afterwards, the base VM itself is never changed.
The playbooks creating and destroying the VMs are shared by all tart scenarios and live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-unbound-ipv4-only` | Container with IPv4 address only and the default configuration |
| `molecule-unbound-ipv6` | Container with IPv4 and IPv6 address and the default configuration |
| `molecule-unbound-config` | Container with `unbound_config`, forwarding over TLS and the UCI option `dhcp_link` of OpenWrt (ignored with a warning), `side_effect` switches the forwarders and overrides and removes server options |

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

The molecule scenario `openwrt` runs the role in two clones of the tart VM `openwrt-base` (OpenWrt with `apk`, SSH login as `root` with password),
the VMs need access to the package feeds.

| Platform | Test case |
|---|---|
| `molecule-unbound-openwrt-default` | Without variables, `prepare` disables the DNS of dnsmasq so unbound gets port 53 |
| `molecule-unbound-openwrt` | `unbound_config` with port 1053, `domain-insecure`, `resource`, `ratelimit: 0`, a forward zone over TLS and a disabled stub zone; `prepare` creates `/etc/config/unbound` with a zone the role has to remove and without the section `unbound` |

`prepare` installs `unbound-checkconf`, the role installs `unbound-daemon`.
`side_effect` runs the role with an option and a clause without UCI counterpart, different `hide-identity` and `hide-version`, a privileged port
and an `auth-zone` with a wrong `url` and checks that it fails with the expected message and `/etc/config/unbound` is unchanged (tasks marked `expect ERROR`),
then it changes the verbosity on `molecule-unbound-openwrt`.
`verify` checks the UCI options, the removed zones, the configuration generated by unbound.sh (including the changed verbosity), `unbound-checkconf`, the service and the port.

```shell
cd dns_unbound
molecule test -s openwrt
```

