The role installs and configures [mdns-repeater](https://github.com/geekman/mdns-repeater) on OpenWrt,
it repeats multicast DNS (mDNS, UDP port 5353) between networks, e.g. to find printers or media devices of another VLAN.
It supports OpenWrt only, the role detects OpenWrt with `raw` (`/etc/openwrt_release`) and fails on other systems; plays need `gather_facts: false`.

The role writes the section `mdns_repeater 'main'` of `/etc/config/mdns_repeater`, the init script of the package passes its devices to `mdns-repeater`.

### Configuration

`mdns_repeater_config` is a dictionary of the options of the section `main`.
Every key replaces the key of the default completely, `null` removes an option.
The default is the delivered configuration of the package, the devices `br-lan` and `eth0.2`, and `enabled`.

| Option | UCI | Description |
|---|---|---|
| `enabled` | `enabled` | Boolean, default `true`; `false` stops and disables mdns-repeater |
| `interface` | `list interface` | Linux devices mdns-repeater repeats between, a list or a string separated by commas and spaces, at least two |

```yaml
mdns_repeater_config:
  enabled: true
  interface: [ 'br-lan', 'br-iot' ]
```

The entries are Linux devices (`br-lan`, `eth1.20`), not networks of `/etc/config/network` (`lan`), the init script passes them to `mdns-repeater` as they are.
Every device needs an IPv4 address.
mdns-repeater can exclude or allow subnets (`-b`, `-w`), the init script of OpenWrt does not support these options.

The firewall has to accept mDNS (UDP port 5353) as input in the zones of the devices, the role does not manage the firewall.

### Validation

The role checks before any change that `mdns_repeater_config` is a dictionary of known options,
that `interface` is a list of at least two different device names of letters, digits, `_`, `.`, `@` and `-` with at most 15 characters.
The failure message names only the failing checks.
Devices missing on the host give a warning only, VLANs and bridges can be created later; mdns-repeater does not start without them.
The role enables mdns-repeater then without starting it, procd starts it with the interface triggers of the init script when the device appears,
otherwise the next run of the role starts it.

### Changes and restarts

- The role installs `mdns-repeater` with `apk` or `opkg` if `/usr/sbin/mdns-repeater` is missing; in check mode it stops after the installation then.
- The role writes the section `main` completely, options set by hand are removed, other sections of `/etc/config/mdns_repeater` are deleted.
- Before a commit the role stores the configuration before the change on the controller in `<playbook_dir>/backups/<inventory_hostname>/mdns_repeater`.
- After a change of the configuration or the installation the role restarts mdns-repeater, if all devices exist.
- With `enabled: false` the role writes the configuration and stops and disables mdns-repeater.

### Tests

The molecule scenario `default` runs the role in two clones of the tart VM `openwrt-base` (OpenWrt with `apk`, SSH login as `root` with password),
the VMs need access to the package feeds.

| Platform | Test case |
|---|---|
| `molecule-mdns-repeater-openwrt-default` | Without variables, the role installs mdns-repeater with the delivered devices, warns about the missing `eth0.2` and enables mdns-repeater without starting it |
| `molecule-mdns-repeater-openwrt` | `prepare` installs mdns-repeater, sets an option and a section the role has to remove and creates the bridge `br-molecule`; the devices `br-lan` and `br-molecule` |

`side_effect` runs the role with an unknown option, an invalid boolean, a single device, a device given twice, an invalid device name, no devices and a configuration that is no dictionary
and checks that it fails with the expected message and the configuration is unchanged (tasks marked `expect ERROR`),
then it changes the order of the devices on `molecule-mdns-repeater-openwrt`.
`verify` checks the UCI options, the removed option and section, the service and the command line of the running mdns-repeater with the changed order.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_OPENWRT_IMAGE` | `openwrt-base` | Base VM that is cloned |
| `MOLECULE_TART_OPENWRT_PASSWORD` | `OpenWRT` | Password of `root`, used to install the SSH key |

```shell
cd dns_mdns_repeater
molecule test
```
