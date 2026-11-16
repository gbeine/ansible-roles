The role creates the PKI of [Easy-RSA](https://github.com/OpenVPN/easy-rsa) and its CA on the Ansible controller.
Everything containing secrets stays on the controller: the private key of the CA is encrypted with `easyrsa_ca_password` and never copied to a host.
`pki_easyrsa_cert` creates the certificates of the realms in the same PKI, `pki_easyrsa_deploy` copies them to the hosts.

```yaml
- hosts: 'all'
  roles:
    - 'pki_easyrsa_ca'
    - 'pki_easyrsa_cert'
    - 'pki_easyrsa_deploy'
```

The CA and the options are the same for all hosts, the realms are set per host:

```yaml
# group_vars/all
easyrsa_ca_cn: 'Example CA'
easyrsa_ca_password: "{{ vault_easyrsa_ca_password }}"

# host_vars/www.example.org
easyrsa_realms:
  - name: 'www.example.org'
    easyrsa: true
```

The tasks run with `delegate_to: localhost` and `throttle: 1`.
Hosts sharing a PKI create it one after the other, the second host finds the CA and changes nothing.

### Configuration

The PKI is `easyrsa_pki_dir`, by default `<site_pki_secrets_dir>/pki`.
The role runs `easyrsa init-pki` only if the directory does not exist or is empty and `easyrsa build-ca` only if `ca.crt` does not exist.
An existing CA is never replaced, an existing PKI of the former role is used as it is.

```yaml
easyrsa_ca_cn: 'Example CA'
easyrsa_ca_password: "{{ vault_easyrsa_ca_password }}"
easyrsa_ca_config:
  EASYRSA_DN: 'org'
  EASYRSA_REQ_COUNTRY: 'DE'
  EASYRSA_REQ_ORG: 'Example'
  EASYRSA_ALGO: 'ec'
  EASYRSA_CURVE: 'secp384r1'
  EASYRSA_CA_EXPIRE: 3650
  EASYRSA_CRL_DAYS: 180
```

`easyrsa_ca_config` contains the options of Easy-RSA with the names of `vars.example`, merged over the default of the role
(`EASYRSA_DN: cn_only`, `EASYRSA_ALGO: rsa`, `EASYRSA_KEY_SIZE: 2048`, `EASYRSA_CA_EXPIRE: 3650`, `EASYRSA_CRL_DAYS: 180`, `EASYRSA_DIGEST: sha256`), `null` removes an option.
They are passed to `easyrsa` in the environment, they contain no secrets.
`easyrsa_path` is the command of Easy-RSA (default `easyrsa` from `PATH`), `easyrsa_openssl_path` the command of OpenSSL passed as `EASYRSA_OPENSSL`.

The controller needs Easy-RSA 3.2.3 or later, e.g. `brew install easy-rsa`, packages of older releases need `easyrsa_path` to a newer `easyrsa`.
`renew` is part of `easyrsa` since 3.2.3, before it needed `easyrsa-tools.lib`.
If a package does not set the version (`Version: ~VER~`), the role warns and continues.

### CRL

The role writes the CRL `<easyrsa_pki_dir>/crl.pem` with `easyrsa gen-crl` if it does not exist
or its `nextUpdate` is less than half of `EASYRSA_CRL_DAYS` away.
A play has to run the role at least every `EASYRSA_CRL_DAYS / 2` days, otherwise the CRL expires on the hosts.
`pki_easyrsa_cert` writes the CRL after every revocation with the same `EASYRSA_CRL_DAYS`, `pki_easyrsa_deploy` copies it to the realms.

### Secrets

The password of the CA is never part of the environment or of a command line.
The module `pki_easyrsa_ca_pki` writes it to two temporary files with mode `0600` in a temporary directory and passes
`--passin=file:<file>` and `--passout=file:<file>` to `easyrsa`, the directory is removed afterwards.
Two files are needed, OpenSSL reads the second line of the file if `-passin` and `-passout` name the same file.
Easy-RSA itself rejects passwords in a `vars` file, the role sets `EASYRSA_NO_VARS`, a `vars` file of the PKI is ignored.

### Allowed variables

The role only allows the options of `vars.example` of Easy-RSA v3.2.7 used by `build-ca` and `gen-crl` in `easyrsa_ca_config`.
This prevents unexpected behavior by accident, e.g. by a typo in an option or by `EASYRSA_PASSIN` with a password in the inventory.
`EASYRSA_PKI`, `EASYRSA_BATCH`, `EASYRSA_PASSIN`, `EASYRSA_PASSOUT`, `EASYRSA_NO_PASS` and `EASYRSA_OPENSSL` are set by the role,
`EASYRSA_REQ_CN` is `easyrsa_ca_cn`.

### Validation

The role checks before any change:

- `easyrsa_ca_cn` and `easyrsa_ca_password` are strings without line breaks
- `easyrsa_ca_config` only contains allowed options with strings or numbers without line breaks, `EASYRSA_DN` is `cn_only` or `org`, `EASYRSA_ALGO` is `rsa`, `ec` or `ed`,
  `EASYRSA_CRL_DAYS` is a positive number of days
- Easy-RSA can be run and is not older than 3.2.3
- the directory of the PKI is a PKI of Easy-RSA or empty, `ca.crt` has its private key
- the password opens an existing `private/ca.key`

The checks of Easy-RSA, the PKI and the password are done by the module in check mode.

### Migration

The roles `pki_easyrsa_ca`, `pki_easyrsa_cert` and `pki_easyrsa_deploy` replace the role `pki_easyrsa_common`.

| Before | Now |
|---|---|
| `pki_easyrsa_ca_cn` | `easyrsa_ca_cn` |
| `vault__pki_easyrsa_common__password` | `easyrsa_ca_password` |
| `pki_easyrsa_pki_dir` | `easyrsa_pki_dir` |
| `pki_easyrsa_path` | `easyrsa_path`, default `easyrsa` from `PATH` instead of `/usr/bin/easyrsa` |
| `pki_easyrsa_dn` | `EASYRSA_DN` in `easyrsa_ca_config` and `easyrsa_cert_config` |
| `pki_easyrsa_req_country`, `_province`, `_city`, `_org`, `_email`, `_ou` | `EASYRSA_REQ_*` in `easyrsa_ca_config` and `easyrsa_cert_config` |
| `pki_easyrsa_key_size`, `pki_easyrsa_algo`, `pki_easyrsa_curve`, `pki_easyrsa_digest` | `EASYRSA_KEY_SIZE`, `EASYRSA_ALGO`, `EASYRSA_CURVE`, `EASYRSA_DIGEST` |
| `pki_easyrsa_ca_expire` | `EASYRSA_CA_EXPIRE` in `easyrsa_ca_config` |
| `pki_easyrsa_crl_days` | `EASYRSA_CRL_DAYS` in `easyrsa_ca_config` |
| `pki_easyrsa_ca_certificates_dir` | `site_pki_ca_certificates_dir` of `common_globals` |
| `pki_realms` | `easyrsa_realms` of the host, see `pki_easyrsa_cert` |

- The password of the CA was passed as `EASYRSA_PASSIN` and `EASYRSA_PASSOUT` (`pass:…`) in the environment, it is passed in temporary files now.
- `EASYRSA_CURVE` was never passed, it is used now.
- The CRL is written when the CA is built and renewed before it expires, before it only existed after the first revocation and expired after `EASYRSA_CRL_DAYS`.
- The role does not create the `.gitkeep` files in the directories of the PKI anymore and does not remove `vars`, Easy-RSA ignores it.
- The tags are `pki` and `pki_easyrsa_ca`.

### Tests

The molecule scenario `default` of `pki_easyrsa_deploy` tests the three roles, see there.
