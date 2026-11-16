The role installs [strongSwan](https://strongswan.org/) with `swanctl` on Debian and OpenWrt, writes the configuration of `swanctl`
and deploys the certificate of the host. It detects OpenWrt with `raw` (`/etc/openwrt_release`), plays for OpenWrt need `gather_facts: false`.

| Platform | Packages | Service |
|---|---|---|
| Debian 13 | `charon-systemd`, `strongswan-swanctl` | `strongswan` |
| OpenWrt | `strongswan-charon`, `strongswan-swanctl`, the plugins `openssl`, `random`, `x509`, `pem`, `pkcs1`, `pkcs8`, `pubkey`, `constraints`, `kernel-netlink`, `socket-default`, the kernel modules `kmod-ipsec4`, `kmod-ipsec6`, `kmod-crypto-gcm` | `swanctl` |

The openssl plugin provides AES-GCM, x25519 and ECDSA on both platforms.

### Configuration

`strongswan_config` is merged over the default of the role, every key replaces the key of the default completely.
It is written to `/etc/swanctl/conf.d/ansible.conf` (mode `0640`), the `swanctl.conf` of the packages includes `conf.d/*.conf` and stays unchanged.
The sections `connections`, `authorities` and `pools` of [swanctl.conf](https://docs.strongswan.org/docs/latest/swanctl/swanctlConf.html) are allowed.
The section `secrets` is not, passwords and pre-shared keys must not be part of the configuration in plain text, keys are files.

The values follow `time_chrony`, adapted to the syntax of `swanctl.conf`:

| Value | Written as |
|---|---|
| Dictionary | Section `name { … }` |
| String or number | `key = value` |
| List | `key = a, b`, swanctl separates lists with commas, a repeated key would replace the former one |
| `true` / `false` | `key = yes` / `key = no`, swanctl needs explicit booleans, e.g. `mobike = no` |
| `null` | The option is removed |

`enabled` is an option of the role and not written: `true` (default) starts and enables strongSwan, `false` stops and disables it.

A mesh of the hosts of a network in transport mode, every host connects to the others on demand (`start_action = trap`)
and authenticates with its certificate, the peers are accepted with a certificate of the CA:

```yaml
strongswan_config:
  connections:
    mesh:
      version: 2
      local_addrs: '192.168.10.11'
      remote_addrs: '192.168.10.0/24'
      proposals: 'aes256gcm16-prfsha384-x25519'
      local:
        auth: 'pubkey'
        certs: 'host.pem'
        id: '192.168.10.11'
      remote:
        auth: 'pubkey'
        cacerts: 'stepca-root.pem'
      children:
        mesh:
          mode: 'transport'
          start_action: 'trap'
          remote_ts: '192.168.10.0/24'
          esp_proposals: 'aes256gcm16-x25519'
```

The trap catches all traffic to `remote_ts`, also to hosts without strongSwan, e.g. the gateway, a management host or the controller of Ansible.
Their traffic is dropped while the IKE negotiation fails, exclude them with a connection with `mode = pass` (`start_action = trap`)
or narrow `remote_ts`. The identity `id` has to be part of the certificate, e.g. the address as `subjectAltName` of type IP.

### Certificates

`strongswan_certificate` deploys the certificate of the host to `/etc/swanctl/x509/host.pem` (`0644`), its key to `/etc/swanctl/private/host.key` (`0600`),
the intermediate certificates to `/etc/swanctl/x509ca/chain.pem` and the root of the CA to `/etc/swanctl/x509ca/<ca_name>` (default `ca.pem`).
The configuration references them with `certs = host.pem` and `cacerts = <ca_name>`. Without `strongswan_certificate` the role does not manage certificates.

| Source | Platform | Keys | Files |
|---|---|---|---|
| `files` | Debian, OpenWrt | `cert`, `key`, `ca`, optional `chain`, `ca_name` | Files on the controller |
| `certbot` | Debian | `realm`, `ca`, optional `home` (default `/opt/certbot`), `ca_name` | `<home>/etc/live/<realm>/cert.pem`, `chain.pem`, `privkey.pem` of `pki_certbot` |
| `acme` | OpenWrt | `domain`, `ca`, optional `ca_name` | `/etc/ssl/acme/<domain>.crt`, `.chain.crt`, `.key` of acme of `bootstrap_openwrt` |
| `realm` | Debian | `realm`, optional `ca_name` | `<realms_dir>/<realm>/public/<realm>.crt`, `public/ca.crt`, `public/crl.pem`, `private/<realm>.key` of `pki_easyrsa_deploy` |

`ca` is a file on the controller, the files of certbot and acme only contain the intermediate certificates.
A realm of `pki_easyrsa_deploy` contains the CA, `ca` is not allowed with the source `realm`.
`<realms_dir>` is `common_globals__pki_realms_dir` (default `/etc/pki/realms`).
`pki_certbot`, `pki_easyrsa_deploy` and `bootstrap_openwrt` issue or deploy the certificates on their own, the role only deploys them and fails if they do not exist yet.

```yaml
strongswan_certificate:
  source: 'certbot'
  realm: 'host.example.org'
  ca: "{{ playbook_dir }}/files/stepca-root.pem"
  ca_name: 'stepca-root.pem'
```

The certificate of a realm of Easy-RSA, the identity `id` of the connection has to be a subjectAltName of `easyrsa_san`:

```yaml
easyrsa_realms:
  - name: 'vpn.example.org'
    easyrsa: true
    easyrsa_type: 'cs'
    easyrsa_san: [ 'DNS:vpn.example.org', 'IP:192.168.10.11' ]

strongswan_certificate:
  source: 'realm'
  realm: 'vpn.example.org'
  ca_name: 'example-ca.pem'
```

```yaml
- hosts: 'vpn'
  roles:
    - 'pki_easyrsa_ca'
    - 'pki_easyrsa_cert'
    - 'pki_easyrsa_deploy'
    - 'security_strongswan'
```

The source `realm` copies the files of the realm in every run, `pki_easyrsa_deploy` changes them only in a run of Ansible.
A certificate renewed or built again by `pki_easyrsa_cert` is loaded by the next run of the role after `pki_easyrsa_deploy`.

With the source `realm` the role copies the CRL of the realm to `/etc/swanctl/x509crl/crl.pem`, strongSwan rejects revoked certificates of the peers.
`pki_easyrsa_ca` renews the CRL before it expires, a play has to run the roles at least every `EASYRSA_CRL_DAYS / 2` days.

The role owns `/etc/swanctl/x509ca/` and `/etc/swanctl/x509crl/`: it removes every file there that does not belong to the current source,
e.g. the CA of a former `ca_name` or `chain.pem` of a former source, swanctl would load them as trusted CAs and CRLs otherwise.
After a removal the role loads the credentials with `swanctl --load-all --clear`, so charon forgets the removed files.
Without `strongswan_certificate` the role does not touch the directories.

The renewal of certbot and acme is deployed without Ansible:

- `certbot`: the path unit `strongswan-certificate.path` watches the directory `live/<realm>/`, certbot replaces its symlinks after a renewal.
  A watch on `cert.pem` would follow the symlink to the former file in `archive/`, which never changes.
  `strongswan-certificate.service` runs `/usr/local/libexec/strongswan-certbot-deploy`, which waits 5 seconds until certbot replaced all symlinks,
  copies the files and runs `swanctl --load-creds`.
  Without the source `certbot` the role removes the units and the script.
- `acme`: acme calls the hotplug scripts with `ACTION` `issued` and `renewed`,
  `/etc/hotplug.d/acme/50-strongswan` copies the files and runs `swanctl --load-creds`. Without the source `acme` the role removes the script.

### OpenWrt

`enabled` is written to `ipsec.globals.enabled` of `/etc/config/ipsec` and controls the service, the role creates the section `globals` if the package delivers none,
the other options of the UCI configuration stay with the package.
The init script generates `/var/swanctl/swanctl.conf` from the UCI configuration, `/etc/swanctl/swanctl.conf` includes it besides `conf.d/*.conf`.
Before a change the role stores `ansible.conf` and `/etc/config/ipsec` on the controller in `<playbook_dir>/backups/<inventory_hostname>/`,
a run without changes writes no backup. In check mode the role stops after the installation if strongSwan is missing.
The firewall has to accept IKE (UDP 500 and 4500) and ESP from the peers, e.g. in the zone `lan`.

### Validation

The role checks before any change:

- `strongswan_config` only contains `connections`, `authorities` and `pools` besides `enabled`
- the names of the sections and options match `^[A-Za-z0-9_.-]+$`
- the values are strings, numbers, booleans or lists of them without line breaks, braces, quotes and `#`
- `enabled` is a boolean
- `strongswan_certificate` has a source of the platform, its mandatory keys and no unknown keys, `ca_name` is a file name
- the files of the certificate exist on the controller
- with the source `realm` the name of the realm consists of letters, digits, `_`, `.` and `-`
  and the certificate, the key, the CA and the CRL of the realm exist on the host

If `strongswan_config` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.
`swanctl` has no check without loading a configuration, the options themselves are checked by `swanctl --load-all` after the configuration was written,
the role fails with the messages of `swanctl` then.

### Restart and reload

strongSwan is started and enabled, or stopped and disabled with `enabled: false`.
A changed configuration or certificate is loaded with `swanctl --load-all` without a restart, established security associations stay.
If the role removed files of `x509ca/` or `x509crl/`, it adds `--clear`, the credentials are loaded again from the files.

### Migration

The role is new, there are no former variables.

- The source `realm` deploys the certificates and the CRL of `pki_easyrsa_deploy`, the role depends on `common_globals` for the directory of the realms.
- Files of former sources and names in `x509ca/` and `x509crl/` are removed, before they stayed trusted.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs with Debian 13, the scenario `openwrt` in two clones of the tart VM `openwrt-base`.
In both scenarios the VMs form a mesh of the example, limited to the address of the other VM:
a trap on the network of tart would catch the SSH connection of the controller too.
`prepare` creates a CA and two certificates for every VM with `openssl` on the controller, the identity is the address of the VM.
On `molecule-strongswan-default` it creates the realm `molecule-strongswan-default` in `/etc/pki/realms` like `pki_easyrsa_deploy`
with the second certificate and a CRL of the CA created with `openssl ca -gencrl`.
The NAT of tart isolates the VMs from each other, `prepare` routes the address of the other VM through the host and ignores ICMP redirects,
the host forwards the packets unchanged. Then `prepare` pings the other VM without IPsec and fails if the VMs cannot reach each other.

| Platform | Test case |
|---|---|
| `molecule-strongswan-default` | The mesh with the certificate from the controller and an own name of the CA, `side_effect` switches to the realm of `pki_easyrsa_deploy` |
| `molecule-strongswan` | The mesh with the certificate of `pki_certbot` (files of `prepare` like certbot), two proposals, `mobike = no`, `rekey_time` |
| `molecule-strongswan-openwrt-default` | The mesh with the certificate from the controller |
| `molecule-strongswan-openwrt` | The mesh with the certificate of acme (files of `prepare` like acme) |

`prepare` of `openwrt` allows IKE and ESP in the firewall.
`side_effect` runs the role with `strongswan_config` not a dictionary, `secrets`, `include`, an invalid name, a brace and a line break in a value,
an invalid boolean, an unknown source, the source of the other platform, a source without its mandatory keys and a missing file on the controller,
on Debian the source `realm` with `ca`, with an invalid name and with a realm missing on the host,
and checks that it fails with the expected message and `ansible.conf` is unchanged (tasks marked `expect ERROR`).
On `molecule-strongswan-default` it switches to the source `realm` with another `ca_name`, the certificate and the CRL of the realm are copied,
the former CA is removed and the credentials are loaded with `--clear`.
In the scenario `openwrt` it writes a CA certificate of a former source to `x509ca/`, the role removes it and loads with `--clear`.
Then it renews the certificate (the symlink of certbot, the symlink of acme and `ACTION=renewed hotplug-call acme`),
the hook has to deploy it, and changes `rekey_time`, the configuration is loaded.
`verify` checks the service, the files with their modes, the deployed certificate, the lines of `ansible.conf` and the connection of `swanctl`,
the files of `x509ca/` and `x509crl/` and the CRL loaded by charon, pings the other VM, the trap has to establish the IKE and the ESP security association in transport mode, and on Debian the path unit of the deployment.
If the ping fails, `verify` shows the negotiation of `swanctl --initiate`, the certificates, policies and security associations and the log of charon.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image of the scenario `default` |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM of the scenario `default` |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |
| `MOLECULE_TART_OPENWRT_IMAGE` | `openwrt-base` | Base VM of the scenario `openwrt` |
| `MOLECULE_TART_OPENWRT_PASSWORD` | `OpenWRT` | Password of `root` of the base VM of the scenario `openwrt` |

```shell
cd security_strongswan
MOLECULE_TART_IMAGE='debian' molecule test
molecule test -s openwrt
```
