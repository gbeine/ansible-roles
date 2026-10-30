### Installing additional packages

```yaml
openwrt_packages:
  - htop
  - ip-full
  - tcpdump
```

### Configuring wireless radios

The wireles radio devices can be configured using the UCI options.

On a Zyxel NWA50AX the configuration would look like:

```yaml
openwrt_wireless:
  - type: 'wifi-device'
    name: 'radio0'
    find: { path: '1e140000.pcie/pci0000:00/0000:00:01.0/0000:02:00.0' }
    options:
      type: 'mac80211'
      path: '1e140000.pcie/pci0000:00/0000:00:01.0/0000:02:00.0'
      cell_density: '0'
      band: '2g'
      htmode: 'HT40'
      channel: 'auto'
      legacy_rates: '1'
      txpower: '20'

  - type: 'wifi-device'
    name: 'radio1'
    find: { path: '1e140000.pcie/pci0000:00/0000:00:01.0/0000:02:00.0+1' }
    options:
      type: 'mac80211'
      path: '1e140000.pcie/pci0000:00/0000:00:01.0/0000:02:00.0+1'
      cell_density: '0'
      country: 'DE'
      band: '5g'
      htmode: 'VHT80'
      channel: 'auto'
      txpower: '23'
```

On a TP-Link Archer C7 v5 the configuration would look like:

```yaml
openwrt_wireless:
  - type: 'wifi-device'
    name: 'radio0'
    find: { path: 'pci0000:00/0000:00:00.0' }
    options:
      type: 'mac80211'
      path: 'pci0000:00/0000:00:00.0'
      band: '5g'
      htmode: 'VHT80'
      channel: 'auto'
      cell_density: '0'

  - type: 'wifi-device'
    name: 'radio1'
    find: { path: 'platform/ahb/18100000.wmac' }
    options:
      type: 'mac80211'
      path: 'platform/ahb/18100000.wmac'
      band: '2g'
      htmode: 'HT20'
      channel: 'auto'
      cell_density: '0'
```

For each radio a number of wireless networks can be configured:

```yaml
openwrt_wireless:
# ... here goes the radio configuration, see above

  - type: 'wifi-iface'
    name: 'wifinet0'
    find: { device: 'radio0', ssid: 'EXAMPLE.ORG' }
    options: { device: 'radio0', mode: 'ap', ssid: 'EXAMPLE.ORG', encryption: 'sae-mixed', key: "{{ vault___openwrt_secret_wifi_key }}", ocv: '0', network: 'network1' }
  - type: 'wifi-iface'
    name: 'wifinet1'
    find: { device: 'radio1', ssid: 'EXAMPLE.ORG' }
    options: { device: 'radio1', mode: 'ap', ssid: 'EXAMPLE.ORG', encryption: 'sae-mixed', key: "{{ vault___openwrt_secret_wifi_key }}", ocv: '0', network: 'network1' }

  - type: 'wifi-iface'
    name: 'wifinet2'
    find: { device: 'radio0', ssid: 'EXAMPLE.NET' }
    options: { device: 'radio0', mode: 'ap', ssid: 'EXAMPLE.NET', encryption: 'sae-mixed', key: "{{ vault___openwrt_secret_wifi_key2 }}", ocv: '0', network: 'network2' }
  - type: 'wifi-iface'
    name: 'wifinet3'
    find: { device: 'radio1', ssid: 'EXAMPLE.NET' }
    options: { device: 'radio1', mode: 'ap', ssid: 'EXAMPLE.NET', encryption: 'sae-mixed', key: "{{ vault___openwrt_secret_wifi_key2 }}", ocv: '0', network: 'network2' }
```
