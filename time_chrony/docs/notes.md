The role installs and configures [chrony](https://chrony-project.org/) as NTP client and server on Debian (package `chrony`)
and on OpenWrt (package `chrony` or `chrony-nts`, UCI configuration `/etc/config/chrony`), see [OpenWrt](#openwrt).
The role detects OpenWrt itself with `raw` (`/etc/openwrt_release`), plays for OpenWrt need `gather_facts: false`.

chrony replaces the time service of the system: on Debian apt removes `systemd-timesyncd` (chrony provides `time-daemon`),
`debian_ntp_enable` of `bootstrap_debian` has to be off. On OpenWrt the role stops and disables `sysntpd`, the section `system.ntp` stays with `bootstrap_openwrt`.

### Configuration

`chrony_config` is a dictionary of directives of [chrony.conf](https://chrony-project.org/doc/latest/chrony.conf.html):

* a string or a number writes `directive value`
* a list writes one line per element, e.g. for `server`, `pool` or `allow`
* `true` writes the directive without value, e.g. `rtcsync`
* `false` or `null` removes the directive

Every key replaces the key of the default completely. The default is the delivered configuration of the platform,
the time sources come from `common_globals__ntp_sources` (`site_ntp_sources`, entries with `type` `server`, `pool` or `peer`, `address` and a list `options`),
they replace the sources of the delivery (`server`, `pool` and `peer`). Without sources there the source of the delivery stays.

```yaml
chrony_config:
  server: [ 'ptbtime1.ptb.de iburst', 'time.cloudflare.com iburst nts' ]
  pool: []
  allow: [ '192.168.0.0/16', 'fd00::/8' ]
  local: 'stratum 10'
```

`enabled` (default `true`) switches the service, `false` writes the configuration and stops and disables chrony.
It is no directive of chrony and not written to a file.

The options `allow_interface`, `dhcp_ntp_server` and `rtccheck` belong to the UCI configuration of OpenWrt, they are ignored with a warning on Debian.

### Debian

The role writes `/etc/chrony/chrony.conf` completely, the directives in the order of the default followed by the new ones.
The default is `chrony.conf` of the package of Debian 13: `pool 2.debian.pool.ntp.org iburst`, `sourcedir` for DHCP and `/etc/chrony/sources.d`,
`keyfile`, `driftfile`, `ntsdumpdir`, `logdir`, `maxupdateskew 100.0`, `rtcsync`, `makestep 1 3`, `leapseclist` and `confdir /etc/chrony/conf.d`.
`chronyd -p` checks the file before it is replaced, a directive chrony does not know lets the role fail.
The AppArmor profile of chronyd allows reading `/etc/chrony` only, `chronyd -p` checks a copy in `/etc/chrony/.chrony.conf.check` that is removed afterwards.
The service `chrony` restarts when the file changed.

### OpenWrt

On OpenWrt the init script `chronyd.init` writes `/var/etc/chrony.d/10-uci.conf` from `/etc/config/chrony`, the static `/etc/chrony/chrony.conf` of the package is not managed.
The role translates `chrony_config` to UCI sections:

| Directive of chrony | UCI section | Name | Options |
|---|---|---|---|
| `server`, `pool`, `peer` | `server`, `pool`, `peer` | unnamed, found by `hostname` | `hostname`, the flags `iburst`, `nts`, `prefer`, `xleave` and `minpoll`, `maxpoll`, `maxdelay`, `mindelay`, `maxsamples`, `minsamples`, `port`, `ntsport`, `maxsources` (pool only) with a number |
| `makestep <threshold> <limit>` | `makestep` | `makestep` | `threshold`, `limit` |
| `smoothtime <maxppm> <maxwander> [leaponly]` | `smoothtime` | `smoothtime` | `maxppm`, `maxwander`, `leaponly` |
| `clockprecision`, `leapsecmode` | `systemclock` | `systemclock` | `precision`, `leapsecmode` |
| `logchange` | `logging` | `logging` | `logchange` |
| `nosystemcert: true`, `ntstrustedcerts` | `nts` | `nts` | `systemcerts '0'`, `trustedcerts` |
| UCI only: `rtccheck` | `nts` | `nts` | `rtccheck`, `nocerttimecheck` without RTC |
| UCI only: `allow_interface` | `allow` | `allow` | `interface`, the networks of `/etc/config/network`, the subnets of their addresses are allowed, WAN allows all |
| UCI only: `dhcp_ntp_server: true` | `dhcp_ntp_server` | `dhcp_ntp_server` | `iburst '1'`, `disabled '0'`, sources from DHCP |

The default is the delivered configuration: `pool 2.openwrt.pool.ntp.org maxpoll 12 maxsources 4 iburst` (replaced by the sources of common_globals),
`dhcp_ntp_server`, `allow_interface: [ 'lan' ]`, `makestep 1.0 3` and `rtccheck`.

The role fails before it changes anything for directives without UCI counterpart, e.g. `local`,
for `allow` (use `allow_interface`), for the directives of the static configuration (`driftfile`, `rtcsync`, …)
and for unknown options of sources.

- The role installs `chrony-nts` if a source uses `nts`, otherwise `chrony`, if `/usr/sbin/chronyd` is missing; the variant is not changed later.
  In check mode the role stops after the installation then.
- The role removes the sections `server`, `pool`, `peer`, `allow`, `dhcp_ntp_server`, `makestep`, `nts`, `smoothtime`, `systemclock` and `logging` it does not declare.
- Before a commit the role stores the configuration before the change on the controller in `<playbook_dir>/backups/<inventory_hostname>/chrony`.
- After a change of the configuration or the installation the role restarts `chronyd`.

### Validation

The role checks before any change that the directives of `chrony_config` consist of lowercase letters, digits and underscores
with strings, numbers, booleans or lists of them as values without line breaks, that `enabled` is a boolean
and that the entries of `common_globals__ntp_sources` have `type` `server`, `pool` or `peer`, `address` and a list `options`.
If `chrony_config` is no dictionary, merging it with the default of the platform (`vars/Debian.yml`, `vars/OpenWrt.yml`) fails before anything changes.
The failure message names only the failing checks.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-chrony-default` | Without variables, the sources of common_globals replace the pool of Debian |
| `molecule-chrony` | Own server, no pool, `allow` and `local`, the OpenWrt option `dhcp_ntp_server` is ignored with a warning |

`prepare` installs `systemd-timesyncd`, chrony has to replace it.
`side_effect` runs the role with an invalid directive name, a dictionary as value, a line break, an invalid boolean
and a directive chrony does not know and checks that it fails with the expected message and `chrony.conf` is unchanged (tasks marked `expect ERROR`),
then it changes `makestep` on `molecule-chrony`, chrony has to restart.
`verify` checks the lines of `chrony.conf`, the service, the removal of `systemd-timesyncd`, the NTP port with `allow` and the sources with `chronyc`.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd time_chrony
MOLECULE_TART_IMAGE='debian' molecule test
```

The molecule scenario `openwrt` runs the role in two clones of the tart VM `openwrt-base` (OpenWrt with `apk`, SSH login as `root` with password),
the VMs need access to the package feeds.

| Platform | Test case |
|---|---|
| `molecule-chrony-openwrt-default` | Without variables, the role installs chrony, the sources of common_globals replace the pool of the delivery |
| `molecule-chrony-openwrt` | `prepare` installs chrony and adds a server the role has to remove; own server, no pool, `allow_interface`, `logchange` and `smoothtime` |

`side_effect` runs the role with `allow`, an unknown option of a server, `maxsources` for a server, `driftfile` and an invalid boolean
and checks that it fails with the expected message and `/etc/config/chrony` is unchanged, then it changes `makestep` on `molecule-chrony-openwrt`.
`verify` checks the UCI options, the configuration generated by `chronyd.init`, the running `chronyd` and the disabled `sysntpd`.

```shell
cd time_chrony
molecule test -s openwrt
```
