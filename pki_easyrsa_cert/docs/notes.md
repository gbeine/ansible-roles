The role creates, rebuilds and renews the certificates of the realms with [Easy-RSA](https://github.com/OpenVPN/easy-rsa) on the Ansible controller,
in the PKI created by `pki_easyrsa_ca`. The private keys of the realms and the CA stay on the controller, `pki_easyrsa_deploy` copies the certificates to the hosts.

The tasks run with `delegate_to: localhost` and `throttle: 1`.
Every host creates the certificates of its own realms, hosts sharing a realm create it one after the other.
A realm shared by several hosts has to be defined the same way on all of them, otherwise the certificate is built again on every run.

### Realms

The realms are `easyrsa_realms` of the host, set in `host_vars`, the role creates the certificates of the realms with `easyrsa: true`.
Other keys of a realm belong to other roles and are ignored.

```yaml
# host_vars/vpn.example.org
easyrsa_realms:
  - name: 'www.example.org'
    easyrsa: true
  - name: 'vpn.example.org'
    easyrsa: true
    easyrsa_type: 'cs'
    easyrsa_san: [ 'DNS:vpn.example.org', 'IP:192.0.2.10', 'IP:2001:db8::10' ]
  - name: 'backup-client'
    easyrsa: true
    easyrsa_type: 'client'
    easyrsa_config:
      EASYRSA_CERT_EXPIRE: 365
```

- `name` is the commonName and the file name of the certificate.
- `easyrsa_type` is `server` (default, `build-server-full`), `client` (`build-client-full`) or `cs`, a combined client and server certificate (`build-serverClient-full`).
- `easyrsa_san` are the subjectAltNames, `DNS:<name>` or `IP:<address>` (IPv4 and IPv6).
  Without them a server or `cs` certificate gets the commonName (`--auto-san`, `IP:` if the name is an address), a client certificate none.
- `easyrsa_config` are options of Easy-RSA for this realm, merged over `easyrsa_cert_config`.

The private keys of the realms have no password (`nopass`), the services read them on the hosts.

### Configuration

`easyrsa_cert_config` contains the options of Easy-RSA for the certificates with the names of `vars.example`, merged over the default of the role
(`EASYRSA_DN: cn_only`, `EASYRSA_ALGO: rsa`, `EASYRSA_KEY_SIZE: 2048`, `EASYRSA_CERT_EXPIRE: 825`, `EASYRSA_PRE_EXPIRY_WINDOW: 30`, `EASYRSA_DIGEST: sha256`),
`null` removes an option. `easyrsa_pki_dir`, `easyrsa_ca_password`, `easyrsa_path` and `easyrsa_openssl_path` are the same as for `pki_easyrsa_ca`.

```yaml
easyrsa_cert_config:
  EASYRSA_ALGO: 'ec'
  EASYRSA_CURVE: 'prime256v1'
  EASYRSA_CERT_EXPIRE: 397
  EASYRSA_PRE_EXPIRY_WINDOW: 30
```

### Build, rebuild and renewal

The module `pki_easyrsa_cert_realm` decides per realm:

- Without certificate it runs `build-server-full`, `build-client-full` or `build-serverClient-full` with `nopass` and the subjectAltNames.
  If the key or the request of the realm exist without certificate, it stops, Easy-RSA does not overwrite them.
- If the extended key usage (the type) or the subjectAltNames of the certificate differ, it revokes the certificate
  (`revoke <name> superseded`), builds it again with a new key and writes the CRL (`gen-crl`).
- If the certificate expires within `EASYRSA_PRE_EXPIRY_WINDOW` days, it renews it with `renew`, the key stays.
  Easy-RSA keeps one renewed certificate in `renewed/issued`, a certificate renewed before is revoked first
  (`revoke-renewed <name> superseded`) and the CRL is written.
- Otherwise nothing changes, the module only reports `changed` for real changes.

The CRL is `<easyrsa_pki_dir>/crl.pem` on the controller, the role does not deploy it.

### Secrets

The password of the CA is never part of the environment or of a command line.
The module writes it to a temporary file with mode `0600` in a temporary directory and passes `--passin=file:<file>` to `easyrsa`,
the directory is removed afterwards. The role sets `EASYRSA_NO_VARS`, a `vars` file of the PKI is ignored.

### Allowed variables

The role only allows the options of `vars.example` of Easy-RSA v3.2.7 used by `build-*-full`, `renew`, `revoke` and `gen-crl`
in `easyrsa_cert_config` and `easyrsa_config` of the realms, and only the keys `easyrsa`, `easyrsa_type`, `easyrsa_san` and `easyrsa_config` in the realms.
This prevents unexpected behavior by accident, e.g. by a typo in an option or by `EASYRSA_PASSIN` with a password in the inventory.

### Validation

The role checks before any change:

- the former variable `pki_realms` is not set
- `easyrsa_realms` is a list of dictionaries with a name, `easyrsa` is a boolean
- the names of the realms with `easyrsa: true` consist of letters, digits, `_`, `.` and `-` and are unique
- the realms have no unknown `easyrsa_*` keys and no `easyrsa_environment`, `easyrsa_type` is `server`, `client` or `cs`
- `easyrsa_san` is a list of `DNS:<name>` and `IP:<address>` with valid addresses
- `easyrsa_cert_config` and `easyrsa_config` of the realms only contain allowed options with strings or numbers without line breaks
- `EASYRSA_CERT_EXPIRE` is greater than `EASYRSA_PRE_EXPIRY_WINDOW`, otherwise the certificates would be renewed on every run
- Easy-RSA can be run and is not older than 3.2.3, the CA exists and the password opens its private key

The checks of Easy-RSA, the CA and the addresses are done by the module in check mode.

### Migration

| Before | Now |
|---|---|
| `pki_realms` | `easyrsa_realms` of the host, the role rejects `pki_realms` |
| `easyrsa_environment` of a realm | `easyrsa_config` of the realm and `easyrsa_san`, the role rejects `easyrsa_environment` |
| `pki_easyrsa_cert_expire` | `EASYRSA_CERT_EXPIRE` in `easyrsa_cert_config` |
| `pki_easyrsa_cert_renew` | `EASYRSA_PRE_EXPIRY_WINDOW` in `easyrsa_cert_config` |
| `pki_easyrsa_crl_days`, `pki_easyrsa_rand_sn`, `pki_easyrsa_ns_support`, `pki_easyrsa_ns_comment` | `EASYRSA_CRL_DAYS`, `EASYRSA_RAND_SN`, `EASYRSA_NS_SUPPORT`, `EASYRSA_NS_COMMENT` in `easyrsa_cert_config` |
| `pki_easyrsa_renew` | removed, certificates are renewed within `EASYRSA_PRE_EXPIRY_WINDOW` |

The variables of the CA and of Easy-RSA are mapped in the migration of `pki_easyrsa_ca`.

- The password of the CA was passed as `EASYRSA_PASSIN` (`pass:…`) in the environment, it is passed in a temporary file now.
- `easyrsa_type` defaults to `server`, a realm with `easyrsa: true` and without type got no certificate before.
- Changed subjectAltNames or types build the certificate again, before they were ignored for existing certificates.
- Renewed certificates are revoked before the next renewal and the CRL is written, `renew` of Easy-RSA 3.2 refused the second renewal before.
- `pki_easyrsa_deploy` does not depend on the role anymore, the certificates are created by the role in the play.
- The tags are `pki` and `pki_easyrsa_cert`.

### Tests

The molecule scenario `default` of `pki_easyrsa_deploy` tests the three roles, see there.
