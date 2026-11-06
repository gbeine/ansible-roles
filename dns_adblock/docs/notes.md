The role installs and configures [adblock](https://github.com/openwrt/packages/blob/master/net/adblock/README.md) on OpenWrt,
the DNS based blocker of ad and abuse domains of the packages feed with the LuCI app `luci-app-adblock`.
It supports OpenWrt only, the role detects OpenWrt with `raw` (`/etc/openwrt_release`) and fails on other systems; plays need `gather_facts: false`.

| File | Content |
|---|---|
| `/etc/config/adblock` | The section `adblock 'global'` from `adblock_config` |
| `/etc/adblock/adblock.allowlist` | The domains of `adblock_allowlist`, one per line |
| `/etc/adblock/adblock.blocklist` | The domains of `adblock_blocklist`, one per line |

### Configuration

`adblock_config` is a dictionary of the options of the section `global` without the prefix `adb_`, e.g. `feed` for `adb_feed`.
Every key replaces the key of the default completely, `null` removes an option.
The default is the delivered configuration of the package: `enabled`, no `debug`, `nftforce`, `dnsshift`, `safesearch`, `mail` and `report`
and the feeds `adguard`, `adguard_tracking` and `certpl`.

```yaml
adblock_config:
  feed: [ 'adguard', 'certpl', 'hagezi' ]
  hag_feed: [ 'pro' ]
  dns: 'unbound'
  trigger: [ 'wan' ]
  safesearch: true
adblock_allowlist: [ 'example.org' ]
adblock_blocklist: [ 'ads.example.com' ]
```

The options are taken from the README of adblock and `luci-app-adblock`:

| Type | Options | UCI |
|---|---|---|
| Boolean | `enabled`, `debug`, `dnsflush`, `dnsshift`, `fetchinsecure`, `jail`, `mail`, `map`, `nftallow`, `nftblock`, `nftbridge`, `nftforce`, `nftremote`, `report`, `represolve`, `safesearch`, `tld` | `0` or `1` |
| Number | `cores`, `fetchretry`, `nicelimit` (0 to 19), `dnsinstance`, `dnstimeout`, `nftremotetimeout`, `repchunkcnt`, `repchunksize`, `triggerdelay` | number |
| List | `feed`, `safesearchlist`, `hag_feed`, `hst_feed`, `ipf_feed`, `stb_feed`, `utc_feed`, `nftmacallow`, `nftmacblock`, `nftmacremote`, `nftdevallow`, `nftdevblock`, `nftdevforce`, `nftportforce`, `repport`, `trigger` | `list`, a string is split at commas and spaces |
| Choice | `dns` (`dnsmasq`, `unbound`, `named`, `kresd`, `smartdns`, `raw`), `fetchcmd` (`uclient-fetch`, `wget`, `curl`) | string |
| String | `allowdnsv4`, `allowdnsv6`, `blockdnsv4`, `blockdnsv6`, `bridgednsv4`, `bridgednsv6`, `remotednsv4`, `remotednsv6`, `backupdir`, `basedir`, `dnsdir`, `reportdir`, `feedfile`, `customfeedfile`, `fetchparm`, `lookupdomain`, `repfilter`, `repiface`, `mailprofile`, `mailreceiver`, `mailsender`, `mailtopic` | string |

The names in `feed` have to be feeds of the feed file (`/etc/adblock/adblock.feeds`, or `feedfile`) or the custom feed file (`/etc/adblock/adblock.custom.feeds`, or `customfeedfile`) on the host.
The feeds `1hosts`, `hagezi`, `ipfire_dbl`, `stevenblack` and `utcapitole` need their categories in `hst_feed`, `hag_feed`, `ipf_feed`, `stb_feed` and `utc_feed`.

adblock detects the DNS backend itself, dnsmasq of OpenWrt or unbound of the role `dns_unbound`; `dns` selects it.

### Lists

`adblock_allowlist` and `adblock_blocklist` are lists of domains, the role writes them to the local lists of adblock, one domain per line.
Domains of the allowlist are never blocked, domains of the blocklist always.
Empty lists give empty files like the delivery, domains added in LuCI are removed.

### Validation

`adblock_config` has to be a dictionary, otherwise merging it with the default fails.
The role checks before any change that the options of `adblock_config` are known options with values of their type,
booleans, numbers in range, the values of a choice, lists of strings and no line breaks,
that the lists are lists of domains of letters, digits, `_`, `*`, `.` and `-` and that no domain is in both lists.
The feeds are checked against the feed files on the host after the installation of the package, also before any change.
The categories of `hag_feed`, `hst_feed`, `ipf_feed`, `stb_feed` and `utc_feed` are checked against `/etc/adblock/adblock.categories` on the host,
the value is the last column of a line, e.g. `wildcard/native.xiaomi-onlydomains.txt` of `hag;tracker.xiaomi;wildcard/native.xiaomi-onlydomains.txt`;
without the file the categories are not checked.
Empty entries of lists are errors, a comment in a YAML list is written without `-`.
The failure message names only the failing checks.

### Changes and restarts

- The role installs `adblock` with `apk` or `opkg` if `/usr/bin/adblock.sh` is missing; in check mode it stops after the installation then.
- The role writes the section `global` completely, options set in LuCI and not declared are removed, other sections of `/etc/config/adblock` are deleted.
  adblock detects the DNS backend, the download tool and the interface of the report itself if they are missing and stores them as `adb_dns`, `adb_fetchcmd` and `adb_repiface`;
  the role keeps these options if `dns`, `fetchcmd` or `repiface` are not declared and sets them otherwise.
- Before a commit the role stores the configuration before the change on the controller in `<playbook_dir>/backups/<inventory_hostname>/adblock`.
- After a change of the configuration or the lists or the installation the role restarts adblock, adblock downloads the feeds in the background then.
  The init script of adblock refuses the restart while a processing runs, e.g. right after the installation,
  the role waits for it at most `adblock_wait_timeout` seconds (default 600) and fails afterwards.

### Tests

The molecule scenario `default` runs the role in two clones of the tart VM `openwrt-base` (OpenWrt with `apk`, SSH login as `root` with password),
the VMs need access to the package feeds and to the sources of the feeds.

| Platform | Test case |
|---|---|
| `molecule-adblock-openwrt-default` | Without variables, the role installs adblock, `example.com` is resolved |
| `molecule-adblock-openwrt` | `prepare` installs adblock and sets an option and a section the role has to remove; `feed`, `dns`, `trigger`, `tld`, an allowlist and `example.com` in the blocklist |

`side_effect` runs the role with an unknown option, an invalid boolean, a number out of range, an unknown DNS backend, an unknown feed,
an unknown category, an invalid domain, an empty entry in the allowlist, a domain in both lists and a configuration that is no dictionary and checks that it fails with the expected message
and the configuration and the lists are unchanged (tasks marked `expect ERROR`), then it adds `example.net` to the blocklist on `molecule-adblock-openwrt`.
`verify` checks the UCI options, the removed option and section, the lists and the service and waits until adblock reports `enabled`
and the blocked domains are not resolved anymore.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_OPENWRT_IMAGE` | `openwrt-base` | Base VM that is cloned |
| `MOLECULE_TART_OPENWRT_PASSWORD` | `OpenWRT` | Password of `root`, used to install the SSH key |

```shell
cd dns_adblock
molecule test
```
