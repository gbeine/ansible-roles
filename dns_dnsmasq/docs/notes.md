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

### Static leases

`dhcp-host` is the only option with another structure, it is a list of dictionaries with the options of the UCI section `host` of OpenWrt
on all platforms, strings are rejected.

```yaml
dnsmasq_config:
  domain: 'lan'
  dhcp-host:
    - mac: '3C:1A:CC:1D:FE:46'
      duid: '00010001c792bc873c1acc1dfe46'
      ip: '192.168.1.42'
      name: 'wallbox'
      dns: '1'
```

| Option | Value | Line in `dnsmasq.conf` |
|---|---|---|
| `mac` | MAC address or list of MAC addresses | `<mac>[,<mac>...]` |
| `duid` | DUID in hex, with or without `:` | `id:<duid>` with `:` between the bytes |
| `ip` | IPv4 address or `ignore` | `<ip>` |
| `hostid` | IPv6 interface identifier in hex, up to 32 bits | `[::<hostid>]` |
| `name` | host name | `<name>`, without `mac` and `duid` it identifies the host |
| `leasetime` | e.g. `12h` or `infinite` | `<leasetime>` |
| `tag` | tag or list of tags | `set:<tag>` |
| `match_tag` | tag or list of tags | `tag:<tag>` in front |
| `broadcast` | boolean, `'0'` or `'1'` | `set:needs-broadcast` |
| `dns` | boolean, `'0'` or `'1'` | an additional `host-record=<name>[,<name>.<domain>],<ip>` with `domain` of the configuration |
| `instance` | dnsmasq instance of OpenWrt | ignored with a warning |

The line is built like `dhcp_host_add` in `dnsmasq.init` of OpenWrt:
`dhcp-host=[tag:<match_tag>,]<mac>|<name>[,id:<duid>][,set:<tag>][,set:needs-broadcast][,<ip>][,[::<hostid>]][,<name>][,<leasetime>]`.
The example gives `dhcp-host=3C:1A:CC:1D:FE:46,id:00:01:00:01:c7:92:bc:87:3c:1a:cc:1d:fe:46,192.168.1.42,wallbox`
and `host-record=wallbox,wallbox.lan,192.168.1.42`.
Every entry needs `mac`, `duid` or `name` and `ip` or `hostid`, the init script of OpenWrt skips entries without address.
`dns` needs `name` and an IPv4 address in `ip`.

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
with booleans, strings, numbers or lists of strings and numbers as values, `dhcp-host` a list of valid static leases.
Strings must not contain line breaks.
The failure message names only the failing checks.

### Changes and restarts

A running container is restarted when the quadlet unit or the configuration changed,
e.g. after changing `dnsmasq_config`, `dnsmasq_enable_dhcp`, `dnsmasq_container` or `dnsmasq_version`.
The first start of the container does not trigger an additional restart.

### OpenWrt

On OpenWrt the init script of dnsmasq creates the command line of dnsmasq from the UCI configuration `/etc/config/dhcp`.
The role uses the same variable as on Debian, `dnsmasq_config` with options of dnsmasq, and translates it to UCI sections.
Every key of `dnsmasq_config` replaces the key of the default completely, `false` disables an option of the default.

Without variables the role keeps the delivered configuration of dnsmasq in OpenWrt (`dhcp.conf` of the package `dnsmasq`):

- `domain-needed`, `bogus-priv`, `localise-queries`, `stop-dns-rebind`, `rebind-localhost-ok`, `expand-hosts`, `dhcp-authoritative`, `read-ethers`, `bind-dynamic` and `local-service`,
- `filterwin2k`, `no-negcache`, `filter-AAAA` and `filter-A` disabled,
- `local=/lan/`, `domain=lan`, `cache-size=1000`, `edns-packet-max=1232`, `dhcp-leasefile=/tmp/dhcp.leases`, `resolv-file=/tmp/resolv.conf.d/resolv.conf.auto`,
- the pool `lan,192.168.1.100,192.168.1.249,255.255.255.0,12h` and no DHCP on `wan`.

The options of the section `dnsmasq` are mapped by the tables in `vars/OpenWrt.yml`, taken from `dnsmasq.init` of OpenWrt,
e.g. `domain-needed` to `domainneeded`, `stop-dns-rebind` to `rebind_protection`, `bind-dynamic` to `nonwildcard` and `server` to the list `server`.
The init script enables `boguspriv`, `rebind_protection` and `nonwildcard` if they are missing, without the option of dnsmasq the role writes `0`.

| Option of dnsmasq | UCI section | Name | find |
|---|---|---|---|
| options of the tables in `vars/OpenWrt.yml` | `dnsmasq` | unnamed | the first section |
| `dhcp-range=<interface>,<start>,<end>,<netmask>[,<leasetime>]` | `dhcp` (`interface`, `start`, `limit`, `leasetime`) | interface | `interface` |
| `dhcp-range=<interface>,<start>,static,<netmask>[,<leasetime>]` | `dhcp` (`interface`, `start`, `dynamicdhcp 0`, `leasetime`) | interface | `interface` |
| `no-dhcp-interface=<interface>` | `dhcp` (`interface`, `ignore 1`) | interface | `interface` |
| `dhcp-option=tag:<interface>,<option>` for an interface with a pool | list `dhcp_option` of the pool | | |
| `dhcp-option=tag:<tag>,<option>` | `tag` (list `dhcp_option`) | tag | |
| `dhcp-host` (dictionaries, see static leases) | `host` with the options of the entry, `mac` and `duid` always and other lists as UCI list like LuCI, booleans as `0`/`1` | unnamed | `mac`, without MAC `duid`, without both `name` |
| `host-record=<name>[,<name>...],<address>[,<address>]` | `domain` (`name`, `ip`) like the hostnames of LuCI, one section per address | unnamed | `name`, `ip` |
| `cname=<cname>,<target>` | `cname` | unnamed | `cname` |
| `srv-host=<srv>,<target>,<port>[,<priority>[,<weight>]]` | `srvhost` (`srv`, `target`, `port`, `class`, `weight`) | unnamed | `srv`, `target` |
| `mx-host=<domain>,<relay>[,<preference>]` | `mxhost` (`domain`, `relay`, `pref`) | unnamed | `domain` |

`find` compares the values exactly, a static lease created in LuCI (`list mac`) is found and updated if the MAC addresses are written
in the same case and order as in `/etc/config/dhcp`.

`start` and `limit` of a pool are relative to the network of the interface like in OpenWrt,
the role calculates them from `<start>`, `<end>` and `<netmask>` (`192.168.1.100` to `192.168.1.249` in `/24` gives `start 100`, `limit 150`).
`static` gives a pool with static leases only (`dynamicdhcp 0`), `limit` is not used then.
The role manages `dynamicdhcp`, a pool written with `<start>,<end>` is dynamic, an existing `dynamicdhcp 0` is removed.

The init script supports less than `dnsmasq.conf`, the role fails before it changes anything
for options without UCI counterpart (e.g. `txt-record`, `ptr-record`, `dhcp-boot`, `conf-file`),
for `dhcp-range` without interface, end address or `static` or netmask or with start and end in different networks, for `dhcp-option` without exactly one `tag:`,
for more than one value of a single value option
and for entries of the same kind that would update the same section (e.g. two `dhcp-host` with the same MAC).
Templates in `dnsmasq_config` are rendered completely before the translation, a failing template stops the role at `Render the configuration`.

- `dnsmasq_enable_dhcp` and the variables of the container (`dnsmasq_home`, `dnsmasq_ip`, `dnsmasq_network`, `dnsmasq_publish`, `dnsmasq_labels`, `dnsmasq_container`, …) are ignored on OpenWrt.
- The role does not install dnsmasq, it fails if `/usr/sbin/dnsmasq` is missing.
- The sections `dhcp` keep the options the role does not manage, e.g. `dhcpv4`, `dhcpv6`, `ra` and `ndp` of odhcpd.
- With `dnsmasq_prune` (default `true`) the role removes the sections of the types `dnsmasq`, `dhcp`, `tag`, `host`, `domain`, `hostrecord`, `cname`, `srvhost` and `mxhost`
  that are neither declared by name nor found by `find`, sections of other types (e.g. `odhcpd`, `boot`) stay untouched.
  All hostnames of LuCI (`domain`) have to be declared as `host-record`, the role no longer creates sections `hostrecord`.
- Before a commit the role stores the configuration before the change on the controller in `<playbook_dir>/backups/<inventory_hostname>/dhcp`.
- After a change of the configuration the role restarts dnsmasq.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The base VM is cloned for every platform and the clones are deleted afterwards, the base VM itself is never changed.
The playbooks creating and destroying the VMs are shared by all tart scenarios and live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-dnsmasq-dns` | Container with IPv4 address only, without DHCP and labels, `side_effect` enables DHCP |
| `molecule-dnsmasq-dhcp` | Container with IPv4 and IPv6 address, DHCP, a DHCP range, static leases with MAC and with DUID, `dns`, `tag` and the ignored `instance`, and labels, `side_effect` adds an address to the configuration |

`prepare` sets up podman and the network `podman-molecule` with the role `container_podman`, installs `dig` and pulls the image.
`side_effect` runs the role with an invalid `dnsmasq_enable_dhcp`, `dnsmasq_publish`, `dnsmasq_labels` and `dnsmasq_config`,
with `dhcp-host` as string and with an unknown option of `dhcp-host`
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

The molecule scenario `openwrt` runs the role in two clones of the tart VM `openwrt-base` (OpenWrt with dnsmasq, SSH login as `root` with password), the base VM is never changed.

| Platform | Test case |
|---|---|
| `molecule-dnsmasq-openwrt-default` | No variables, the dhcp configuration stays in the delivered state |
| `molecule-dnsmasq-openwrt` | Own configuration with `server`, `address`, a pool, DHCP options for the pool and a tag, static leases with `tag`, `leasetime`, `duid` and `dns`, `host-record`, `cname`, `srv-host`, `mx-host` and `bogus-priv` disabled, `side_effect` changes `cache-size` |

`prepare` stores the delivered configuration (`uci show dhcp`) and creates a static lease like LuCI (`list mac`, `list duid`) on `molecule-dnsmasq-openwrt`, the role has to update it instead of adding another section.
`side_effect` runs the role with `txt-record`, a `dhcp-range` without netmask, a `dhcp-option` without tag and a `dhcp-host` as string,
and checks that the role fails with exactly the expected message and `/etc/config/dhcp` is unchanged (tasks marked `expect ERROR`).
Afterwards it changes `cache-size` and checks that the configuration is committed and dnsmasq is restarted.
`verify` checks that the configuration of `molecule-dnsmasq-openwrt-default` equals the delivered one,
the expected UCI options of `molecule-dnsmasq-openwrt`, that the options of odhcpd are kept, that dnsmasq runs and is enabled,
and resolves `address`, `host-record`, `cname` and the name of the `dhcp-host` with `dns` with `nslookup` via `127.0.0.1`.
The collection `community.openwrt` is required on the controller.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_OPENWRT_IMAGE` | `openwrt-base` | Base VM that is cloned |
| `MOLECULE_TART_OPENWRT_PASSWORD` | `OpenWRT` | Password of `root`, used to install the SSH key |

```shell
cd dns_dnsmasq
molecule test -s openwrt
```
